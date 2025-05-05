#!/usr/bin/env python3
"""
1TamilMV Magnet Dashboard Generator
"""
import os, re, time, datetime
import requests, cloudscraper, json
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MIRRORS = ["https://www.1tamilmv.fi",
          "https://1tamilmv.fi",
          "https://www.1tamilmv.moi",
          "https://www.1tamilmv.bike",
          "https://www.1tamilmv.app",
          "https://www.1tamilmv.tel",
          "https://www.1tamilmv.legal"]
MAX_ENTRIES = 100  # Increased for more content

# ─── Initialize scraper with browser emulation ────────────────────────────────
scraper = cloudscraper.create_scraper(
    browser={
        'custom': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }
)

# ─── Find working domain ────────────────────────────────────────────────────
def get_domain():
    print("Attempting to find a working domain...")
    
    for d in MIRRORS:
        if check_domain(d): return d
            
    raise RuntimeError("no mirror alive")

def check_domain(url):
    try:
        print(f"\nTrying domain: {url}")
        r = scraper.get(url, timeout=15)
        print(f"Response: Status {r.status_code}")
        
        if r.status_code != 200:
            return False
            
        if "1TamilMV" in r.text or "Tamil Movie" in r.text:
            print("✓ Found valid homepage")
            return True
        
        print("✗ Not a valid homepage")
        return False
        
    except Exception as e:
        print(f"Error checking {url}: {str(e)}")
        return False

# ─── Helper functions for content extraction ────────────────────────────────
def extract_proper_title(full_title):
    """Extract the actual movie/show title from the technical description."""
    # Remove quality patterns like [1080p & 720p - AVC...]
    patterns = [
        r'\[\d+p.*?\]',  # [1080p & 720p...]
        r'\(BluRay.*?\)',  # (BluRay...)
        r'\(WEB-DL.*?\)',  # (WEB-DL...)
        r'\(.*?p.*?\)',   # (1080p...)
        r'- \[.*?\]$',    # - [TAM + TEL...]
        r'\s+-\s+\d+(\.\d+)?GB.*',  # - 2.7GB...
        r'WEB-DL.*$',     # WEB-DL and after
        r'BluRay.*$',     # BluRay and after
        r'\s+\[.*?\]$',   # [anything] at the end
    ]
    
    title = full_title
    for pattern in patterns:
        title = re.sub(pattern, '', title).strip()
    
    # If title became empty or too short, use the original
    if not title or len(title) < 10:
        # Try to extract year and movie name
        year_match = re.search(r'(.+?)(\(\d{4}\))', full_title)
        if year_match:
            return year_match.group(1).strip() + " " + year_match.group(2)
        return full_title
        
    return title

def find_better_image(soup, title, dom):
    """Find a better image for the content."""
    # Look for movie poster images
    for img in soup.find_all("img"):
        src = img.get("src", "")
        # Check if it's likely a poster (larger images, not small icons)
        if (src and not src.endswith(('.gif', '.png')) and 
            not 'avatar' in src.lower() and 
            not 'icon' in src.lower() and
            (img.get("width", "0").isdigit() and int(img.get("width", "0")) > 100)):
            return urljoin(dom, src)
            
    # If no good image found, use placeholder
    return "https://via.placeholder.com/300x450?text=No+Image"

def extract_languages(title):
    """Extract language information from the title."""
    languages = []
    lang_patterns = {
        "TAM": ["Tamil", "TAM"],
        "TEL": ["Telugu", "TEL"],
        "HIN": ["Hindi", "HIN"],
        "KAN": ["Kannada", "KAN"],
        "MAL": ["Malayalam", "MAL"],
        "ENG": ["English", "ENG"],
        "JAP": ["Japanese", "JAP"]
    }
    
    for lang_code, patterns in lang_patterns.items():
        for pattern in patterns:
            if pattern in title:
                languages.append(lang_code)
                
    return languages

def extract_date(title, soup=None):
    """Extract release date from title or content."""
    # Look for year in title
    year_match = re.search(r'\((\d{4})\)', title)
    if year_match:
        return year_match.group(1)
        
    # Default to current year if not found
    return datetime.datetime.now().strftime("%Y")

def extract_quality(title):
    """Extract quality information from title"""
    qualities = []
    if "1080p" in title:
        qualities.append("1080p")
    if "720p" in title:
        qualities.append("720p")
    if "2160p" in title or "4K" in title or "UHD" in title:
        qualities.append("4K")
    if "HDR" in title:
        qualities.append("HDR")
    
    return qualities

def extract_category(soup, dom):
    """Extract category from breadcrumb navigation"""
    category = "Uncategorized"
    try:
        breadcrumbs = soup.select(".ipsBreadcrumb li a")
        for crumb in breadcrumbs:
            href = crumb.get("href", "")
            if "forum" in href:
                return crumb.text.strip()
    except:
        pass
    return category

# ─── Get magnets from homepage ──────────────────────────────────────────────
def fetch_magnets():
    dom = get_domain()
    results = []
    
    try:
        print(f"\nFetching recent torrents from homepage: {dom}")
        page = scraper.get(dom, timeout=15).text
        soup = BeautifulSoup(page, "html.parser")
        
        all_links = soup.find_all('a')
        print(f"Found {len(all_links)} links on the page")
        
        potential_topics = []
        for link in all_links:
            href = link.get('href', '')
            text = link.text.strip()
            if text and href and not href.startswith('magnet:') and '/' in href and len(text) > 10:
                potential_topics.append(link)
        
        print(f"Found {len(potential_topics)} potential topic links")
        
        for topic in potential_topics[:MAX_ENTRIES]:
            title = topic.text.strip()
            print(f"Processing: {title}")
            link = urljoin(dom, topic.get("href"))
            
            try:
                topic_page = scraper.get(link, timeout=15).text
                topic_soup = BeautifulSoup(topic_page, "html.parser")
                
                magnet = None
                for a in topic_soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("magnet:?"):
                        magnet = href
                        break
                
                if magnet:
                    print(f"Found magnet link for: {title}")
                    
                    # Extract better title
                    clean_title = extract_proper_title(title)
                    
                    # Get better image
                    img_src = find_better_image(topic_soup, clean_title, dom)
                    
                    # Extract languages
                    languages = extract_languages(title)
                    
                    # Extract quality
                    qualities = extract_quality(title)
                    
                    # Extract date
                    release_date = extract_date(title, topic_soup)
                    
                    # Extract category
                    category = extract_category(topic_soup, dom)
                    
                    results.append({
                        "title": title,
                        "clean_title": clean_title,
                        "magnet": magnet,
                        "link": link,
                        "image": img_src,
                        "languages": languages,
                        "qualities": qualities,
                        "category": category,
                        "release_date": release_date,
                        "added": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
            except Exception as e:
                print(f"Error processing topic {title}: {e}")
                
    except Exception as e:
        print(f"Error fetching homepage: {e}")
    
    return results

# ─── Generate HTML page ──────────────────────────────────────────────────
def generate_html_page(items):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Magnet Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background-color: #f8f9fa; }
        .navbar { background-color: #343a40 !important; }
        .card { transition: transform 0.2s; margin-bottom: 20px; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
        .card-img-top { height: 200px; object-fit: cover; }
        .badge { margin-right: 5px; }
        .btn-magnet { background-color: #ff6700; border-color: #ff6700; }
        .btn-realdebrid { background-color: #3cb371; border-color: #3cb371; }
        .filter-bar { background-color: #fff; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .no-image { background-color: #e9ecef; display: flex; align-items: center; justify-content: center; color: #6c757d; height: 200px; }
        .card-title { height: 50px; overflow: hidden; }
        .language-badge { font-size: 0.7rem; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="#">1TamilMV Magnet Dashboard</a>
            <div class="ms-auto text-white">
                <small>Last updated: """ + time.strftime("%Y-%m-%d %H:%M:%S UTC") + """</small>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="filter-bar">
            <div class="row g-3">
                <div class="col-md-4">
                    <input type="text" class="form-control" id="searchInput" placeholder="Search titles...">
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="categoryFilter">
                        <option value="">All Categories</option>
"""

    # Add categories dynamically
    categories = sorted(set([item['category'] for item in items if item['category']]))
    for category in categories:
        html += f'                        <option value="{category}">{category}</option>\n'

    html += """
                    </select>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="qualityFilter">
                        <option value="">All Qualities</option>
                        <option value="1080p">1080p</option>
                        <option value="720p">720p</option>
                        <option value="4K">4K</option>
                        <option value="HDR">HDR</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="languageFilter">
                        <option value="">All Languages</option>
                        <option value="TAM">Tamil</option>
                        <option value="TEL">Telugu</option>
                        <option value="HIN">Hindi</option>
                        <option value="KAN">Kannada</option>
                        <option value="MAL">Malayalam</option>
                        <option value="ENG">English</option>
                        <option value="JAP">Japanese</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="sortOrder">
                        <option value="newest">Newest First</option>
                        <option value="oldest">Oldest First</option>
                        <option value="az">A-Z</option>
                        <option value="za">Z-A</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row" id="magnetCards">
"""

    for item in items:
        title = item['title']
        clean_title = item.get('clean_title', title)
        magnet = item['magnet']
        category = item.get('category', "Uncategorized")
        img_src = item.get('image', "")
        languages = item.get('languages', [])
        qualities = item.get('qualities', [])
        release_date = item.get('release_date', "")
        added_date = item.get('added', "")
        
        # Create badges for quality markers
        quality_badges = ""
        for quality in qualities:
            badge_class = "bg-info" if quality == "1080p" else "bg-secondary" if quality == "720p" else "bg-danger" if quality in ["4K", "2160p", "UHD"] else "bg-warning text-dark"
            quality_badges += f'<span class="badge {badge_class}">{quality}</span>'
            
        # Create badges for languages
        language_badges = ""
        for lang in languages:
            language_badges += f'<span class="badge bg-primary language-badge">{lang}</span>'
            
        html += f"""
            <div class="col-md-3 magnet-item" 
                data-category="{category}" 
                data-title="{clean_title.lower()}" 
                data-original-title="{title.lower()}"
                data-date="{release_date}"
                data-added="{added_date}"
                data-languages="{','.join(languages)}">
                <div class="card h-100">
                    <div class="card-img-top-container">
                        {f'<img src="{img_src}" class="card-img-top" alt="{clean_title}">' if img_src else '<div class="no-image"><span>No Image</span></div>'}
                    </div>
                    <div class="card-body">
                        <h5 class="card-title" title="{clean_title}">{clean_title}</h5>
                        <div class="mb-2">
                            {quality_badges}
                            {language_badges}
                        </div>
                        <p class="card-text">
                            <small class="text-muted">{category} • {release_date}</small>
                        </p>
                        <div class="d-grid gap-2">
                            <button class="btn btn-magnet text-white btn-sm" onclick="copyToClipboard('{magnet}', this)">
                                <i class="fas fa-copy me-1"></i> Copy Magnet
                            </button>
                            <a href="{magnet}" class="btn btn-dark btn-sm">
                                <i class="fas fa-magnet me-1"></i> Open Magnet
                            </a>
                            <a href="https://real-debrid.com/torrents" target="_blank" class="btn btn-realdebrid text-white btn-sm">
                                <i class="fas fa-cloud-download-alt me-1"></i> Go to Real-Debrid
                            </a>
                        </div>
                    </div>
                </div>
            </div>
"""

    html += """
        </div>
    </div>

    <footer class="bg-dark text-white text-center py-3 mt-5">
        <div class="container">
            <p class="mb-0">Last updated: """ + time.strftime("%Y-%m-%d %H:%M:%S UTC") + """</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function copyToClipboard(text, button) {
            navigator.clipboard.writeText(text).then(() => {
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';
                button.classList.add('btn-success');
                button.classList.remove('btn-magnet');
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.classList.add('btn-magnet');
                    button.classList.remove('btn-success');
                }, 2000);
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('searchInput').addEventListener('input', filterItems);
            document.getElementById('categoryFilter').addEventListener('change', filterItems);
            document.getElementById('qualityFilter').addEventListener('change', filterItems);
            document.getElementById('languageFilter').addEventListener('change', filterItems);
            document.getElementById('sortOrder').addEventListener('change', sortItems);
            
            // Initial sort
            sortItems();
        });

        function filterItems() {
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const categoryFilter = document.getElementById('categoryFilter').value;
            const qualityFilter = document.getElementById('qualityFilter').value.toLowerCase();
            const languageFilter = document.getElementById('languageFilter').value;
            
            document.querySelectorAll('.magnet-item').forEach(item => {
                const title = item.getAttribute('data-title');
                const originalTitle = item.getAttribute('data-original-title');
                const category = item.getAttribute('data-category');
                const languages = item.getAttribute('data-languages').split(',');
                
                const titleMatch = title.includes(searchTerm) || originalTitle.includes(searchTerm);
                const categoryMatch = !categoryFilter || category === categoryFilter;
                const qualityMatch = !qualityFilter || originalTitle.includes(qualityFilter);
                const languageMatch = !languageFilter || languages.includes(languageFilter);
                
                if (titleMatch && categoryMatch && qualityMatch && languageMatch) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        }

        function sortItems() {
            const container = document.getElementById('magnetCards');
            const sortOrder = document.getElementById('sortOrder').value;
            const items = Array.from(container.getElementsByClassName('magnet-item'));
            
            items.sort(function(a, b) {
                const aTitle = a.getAttribute('data-title');
                const bTitle = b.getAttribute('data-title');
                const aDate = a.getAttribute('data-added') || '2000-01-01';
                const bDate = b.getAttribute('data-added') || '2000-01-01';
                
                switch(sortOrder) {
                    case 'newest':
                        return bDate.localeCompare(aDate);
                    case 'oldest':
                        return aDate.localeCompare(bDate);
                    case 'az':
                        return aTitle.localeCompare(bTitle);
                    case 'za':
                        return bTitle.localeCompare(aTitle);
                }
            });
            
            items.forEach(item => container.appendChild(item));
        }
    </script>
</body>
</html>
"""
    return html

# ─── Save data to JSON and HTML ──────────────────────────────────────────────
def save_data(items):
    # Save JSON data
    with open("magnets.json", "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON data to magnets.json")
    
    # Generate and save HTML
    html = generate_html_page(items)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved HTML dashboard to index.html")

# ─── Main function ──────────────────────────────────────────────────────────
def main():
    print(f"Starting magnet dashboard update at {datetime.datetime.now()}")
    items = fetch_magnets()
    print(f"\nFound {len(items)} items")
    save_data(items)
    print("Update completed successfully")

if __name__ == "__main__":
    main()
