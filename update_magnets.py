#!/usr/bin/env python3
"""
1TamilMV Magnet Dashboard Generator
"""
import os, re, time, datetime
import requests, cloudscraper, json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import base64

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MIRRORS = ["https://www.1tamilmv.fi",
          "https://1tamilmv.fi",
          "https://www.1tamilmv.moi",
          "https://www.1tamilmv.bike",
          "https://www.1tamilmv.app"]
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
                    
                    # Extract more info if possible
                    img_src = None
                    for img in topic_soup.find_all("img"):
                        src = img.get("src", "")
                        if src and not src.endswith(('.gif', '.png')) and not 'avatar' in src.lower():
                            img_src = urljoin(dom, src)
                            break
                    
                    category = ""
                    for breadcrumb in topic_soup.select(".ipsBreadcrumb li a"):
                        if "forum" in breadcrumb.get("href", ""):
                            category = breadcrumb.text.strip()
                            break
                    
                    results.append({
                        "title": title,
                        "magnet": magnet,
                        "link": link,
                        "image": img_src,
                        "category": category,
                        "date": datetime.datetime.now().strftime("%Y-%m-%d")
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
        .no-image { background-color: #e9ecef; display: flex; align-items: center; justify-content: center; color: #6c757d; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="#">Magnet Dashboard</a>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="filter-bar">
            <div class="row g-3">
                <div class="col-md-6">
                    <input type="text" class="form-control" id="searchInput" placeholder="Search titles...">
                </div>
                <div class="col-md-3">
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
                <div class="col-md-3">
                    <select class="form-select" id="qualityFilter">
                        <option value="">All Qualities</option>
                        <option value="1080p">1080p</option>
                        <option value="720p">720p</option>
                        <option value="4K">4K</option>
                        <option value="UHD">UHD</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row" id="magnetCards">
"""

    for item in items:
        title = item['title']
        magnet = item['magnet']
        category = item['category'] or "Uncategorized"
        img_src = item['image'] or ""
        
        # Create badges for quality markers
        badges = ""
        if "1080p" in title:
            badges += '<span class="badge bg-info">1080p</span>'
        if "720p" in title:
            badges += '<span class="badge bg-secondary">720p</span>'
        if "4K" in title or "2160p" in title:
            badges += '<span class="badge bg-danger">4K</span>'
        if "UHD" in title:
            badges += '<span class="badge bg-warning text-dark">UHD</span>'
            
        html += f"""
            <div class="col-md-4 col-lg-3 magnet-item" data-category="{category}" data-title="{title.lower()}">
                <div class="card h-100">
                    <div class="{"card-img-top no-image" if not img_src else ""}" style="height: 200px;">
                        {"<span>No Image</span>" if not img_src else f'<img src="{img_src}" class="card-img-top" alt="{title}">'}
                    </div>
                    <div class="card-body">
                        <h5 class="card-title">{title}</h5>
                        <div class="mb-2">
                            {badges}
                            <span class="badge bg-primary">{category}</span>
                        </div>
                        <div class="d-grid gap-2">
                            <button class="btn btn-magnet text-white btn-sm" onclick="copyToClipboard('{magnet}', this)">Copy Magnet</button>
                            <a href="{magnet}" class="btn btn-dark btn-sm">Open Magnet</a>
                            <a href="https://real-debrid.com/torrents" target="_blank" class="btn btn-realdebrid text-white btn-sm">Go to Real-Debrid</a>
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
                const originalText = button.textContent;
                button.textContent = "Copied!";
                button.classList.add('btn-success');
                button.classList.remove('btn-magnet');
                setTimeout(() => {
                    button.textContent = originalText;
                    button.classList.add('btn-magnet');
                    button.classList.remove('btn-success');
                }, 2000);
            });
        }

        document.getElementById('searchInput').addEventListener('input', filterItems);
        document.getElementById('categoryFilter').addEventListener('change', filterItems);
        document.getElementById('qualityFilter').addEventListener('change', filterItems);

        function filterItems() {
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const categoryFilter = document.getElementById('categoryFilter').value;
            const qualityFilter = document.getElementById('qualityFilter').value;
            
            document.querySelectorAll('.magnet-item').forEach(item => {
                const title = item.getAttribute('data-title');
                const category = item.getAttribute('data-category');
                const titleMatch = title.includes(searchTerm);
                const categoryMatch = !categoryFilter || category === categoryFilter;
                const qualityMatch = !qualityFilter || title.includes(qualityFilter.toLowerCase());
                
                if (titleMatch && categoryMatch && qualityMatch) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
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
