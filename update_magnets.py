#!/usr/bin/env python3
"""
1TamilMV Magnet Dashboard Generator
Enhanced version with better title extraction and TV show support
"""
import os, re, time, datetime
import requests, cloudscraper, json
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse


# ─── CONFIG ────────────────────────────────────────────────────────────────────
MIRRORS = ["https://www.1tamilmv.fi",
          "https://1tamilmv.fi",
          "https://www.1tamilmv.moi",
          "https://www.1tamilmv.bike",
          "https://www.1tamilmv.app",
          "https://www.1tamilmv.tel",
          "https://www.1tamilmv.legal"]
MAX_ENTRIES = 200  # Increased for more content
DEEP_CRAWL_TV = True  # Set to True to crawl TV show sections deeper

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
def extract_proper_title(full_title, soup=None, page_url=""):
    """Enhanced title extraction with better UI element filtering"""
    # Skip known UI elements and site branding
    ui_elements = [
        "Sign In", "J.A.R.V.I.S.", "JARVIS", "By J.A.R.V.I.S.", "By Olan",
        "Login", "Register", "TamilMV Official Telegram Channel",
        "TamilMV Official", "1TamilMV.com"
    ]
    
    # Check if this is a UI element rather than a content title
    if any(ui in full_title for ui in ui_elements):
        # Try to extract the real title from page elements instead
        if soup:
            # Look for topic titles in the standard forum layout
            topic_title = soup.select_one(".ipsType_pagetitle") or soup.select_one(".ipsDataItem_title a")
            if topic_title and len(topic_title.text.strip()) > 5:
                return topic_title.text.strip()
            
            # Look for page titles with year pattern (very reliable for movies)
            for element in soup.select("h1, h2, .ipsType_break"):
                text = element.text.strip()
                movie_year = re.search(r'([^(]+)\s*\((\d{4})\)', text)
                if movie_year and len(movie_year.group(1).strip()) > 3:
                    return movie_year.group(0).strip()
                    
            # Try page title (remove site name)
            if soup.title:
                title_text = soup.title.text.strip()
                title_text = re.sub(r'\s*[-|]\s*(?:1TamilMV|TamilMV).*$', '', title_text)
                if len(title_text) > 5:
                    return title_text
        
        # Extract from URL as last resort
        if page_url:
            try:
                path = urlparse(page_url).path
                if "topic" in path or "forums" in path:
                    parts = path.split('-')
                    if len(parts) > 1:
                        if parts[0].endswith(('0', '/')):  # Skip ID numbers
                            parts = parts[1:]
                        title = ' '.join(parts).replace('-', ' ').title()
                        if len(title) > 5:
                            return title
            except:
                pass
                
        # If we still can't extract a good title
        return "Unknown Title (See Details)"
    
    # For legitimate titles, clean up common prefixes
    common_prefixes = [
        "TamilMV Official Telegram Channel :-",
        "TamilMV Official Telegram Channel:",
        "1TamilMV.com -"
    ]
    
    for prefix in common_prefixes:
        if full_title.startswith(prefix):
            full_title = full_title[len(prefix):].strip()
            break
    
    # Special TV show episode pattern: Office (2025) S01 EP (37-40)
    tv_match = re.search(r'([^(]+)\s*\((\d{4})\)\s+S(\d+)\s+EP\s*\(?(\d+(?:-\d+)?)\)?', full_title, re.IGNORECASE)
    if tv_match:
        show_name = tv_match.group(1).strip()
        year = tv_match.group(2)
        season = tv_match.group(3)
        episode = tv_match.group(4)
        return f"{show_name} (S{season}E{episode})"
    
    # Handle movie titles with year in parentheses - very common pattern
    movie_year_match = re.search(r'([^(]+)\s*\((\d{4})\)', full_title)
    if movie_year_match:
        movie_name = movie_year_match.group(1).strip()
        year = movie_year_match.group(2)
        if len(movie_name) > 3:  # Reasonable movie name length
            return f"{movie_name} ({year})"
    
    # Check if there's a title in the page HTML
    if soup:
        # Try page heading or title
        heading = soup.find('h1') or soup.find('h2')
        if heading:
            heading_text = heading.text.strip()
            # Look for movie name with year pattern
            movie_year = re.search(r'([^(]+)\s*\((\d{4})\)', heading_text)
            if movie_year:
                return movie_year.group(0)
            
        # Try meta title tag
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.text.strip()
            # Remove site name
            title_text = re.sub(r'\s*[-|]\s*1TamilMV.*$', '', title_text)
            title_text = re.sub(r'\s*[-|]\s*TamilMV.*$', '', title_text)
            if len(title_text) > 5:
                return title_text
    
    # Regular removal of technical specs
    patterns = [
        r'\[\d+p.*?\]',  # [1080p & 720p...]
        r'\(BluRay.*?\)',  # (BluRay...)
        r'\(WEB-DL.*?\)',  # (WEB-DL...)
        r'- \[.*?\]$',    # - [TAM + TEL...]
        r'\s+-\s+\d+(\.\d+)?GB.*',  # - 2.7GB...
        r'WEB-DL.*$',     # WEB-DL and after
        r'BluRay.*$',     # BluRay and after
        r'\s+\[.*?\]$',   # [anything] at the end
        r'AVC.*$',        # AVC and after
        r'HEVC.*$',       # HEVC and after
    ]
    
    title = full_title
    for pattern in patterns:
        title = re.sub(pattern, '', title).strip()
    
    # If title is empty or still looks like a channel name
    if not title or len(title) < 5 or title in common_prefixes:
        # Try to extract from URL if provided
        if page_url:
            try:
                path = urlparse(page_url).path
                # Extract the topic title from URL
                parts = path.split('/')[-1].split('-')
                if len(parts) > 1:
                    # Skip numeric ID at beginning
                    if parts[0].isdigit():
                        parts = parts[1:]
                    possible_title = ' '.join(parts).replace('-', ' ')
                    if len(possible_title) > 5:
                        return possible_title.capitalize()
            except:
                pass
        
        # If we got here and title is still a channel name, use a placeholder
        if any(prefix in title for prefix in common_prefixes):
            return "Movie Title (See Details)"
        
        # Last resort: use original title
        return full_title
        
    return title


def find_better_image(soup, title, dom):
    """Find a better image for the content"""
    # Look for poster-sized images first (movie posters are usually larger)
    for img in soup.find_all("img"):
        src = img.get("src", "")
        width = img.get("width", "0")
        height = img.get("height", "0")
        
        # Skip small images, icons, avatars
        if (src and 
            not src.endswith(('.gif')) and 
            not 'avatar' in src.lower() and 
            not 'icon' in src.lower() and
            not 'logo' in src.lower()):
            
            # Check if image has decent dimensions if specified
            if width.isdigit() and height.isdigit():
                if int(width) >= 200 and int(height) >= 200:
                    return urljoin(dom, src)
                    
            # Also check image filename for keywords
            if 'poster' in src.lower() or 'cover' in src.lower() or 'movie' in src.lower():
                return urljoin(dom, src)
    
    # Fallback to any larger image
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and not src.endswith(('.gif')) and not 'avatar' in src.lower():
            return urljoin(dom, src)
            
    # Placeholder if no image found
    return "https://via.placeholder.com/300x450?text=No+Image"

def extract_languages(title):
    """Extract language information from the title"""
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

def extract_tv_info(title):
    """Extract season and episode information"""
    info = {
        "is_tv_show": False,
        "show_name": "",
        "season": "",
        "episode": "",
        "year": ""
    }
    
    # Look for standard TV pattern: Show Name (YYYY) SxxEPyy
    tv_match = re.search(r'([^(]+)\s*\((\d{4})\)\s+S(\d+)\s+EP\s*\(?(\d+(?:-\d+)?)\)?', title, re.IGNORECASE)
    if tv_match:
        info["is_tv_show"] = True
        info["show_name"] = tv_match.group(1).strip()
        info["year"] = tv_match.group(2)
        info["season"] = f"S{int(tv_match.group(3)):02d}"
        info["episode"] = f"EP{tv_match.group(4)}"
        return info
    
    # Alternative format: Show Name SxxEyy
    alt_match = re.search(r'(.+?)(?:\s*\(\d{4}\))?\s+S(\d+)[Ee](\d+)', title, re.IGNORECASE)
    if alt_match:
        info["is_tv_show"] = True
        info["show_name"] = alt_match.group(1).strip()
        info["season"] = f"S{int(alt_match.group(2)):02d}"
        info["episode"] = f"E{int(alt_match.group(3)):02d}"
        
        # Try to find year if not in the standard place
        year_match = re.search(r'\((\d{4})\)', title)
        if year_match:
            info["year"] = year_match.group(1)
        return info
    
    return info

def extract_quality(title):
    """Extract quality information from title"""
    qualities = []
    if "1080p" in title:
        qualities.append("1080p")
    if "720p" in title:
        qualities.append("720p")
    if "480p" in title:
        qualities.append("480p") 
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
        
        # Process regular topic links
        for topic in potential_topics[:MAX_ENTRIES]:
            title = topic.text.strip()
            print(f"Processing: {title}")
            link = urljoin(dom, topic.get("href"))
            
            try:
                topic_page = scraper.get(link, timeout=15).text
                topic_soup = BeautifulSoup(topic_page, "html.parser")
                
                # Process the page and extract content
                process_topic_page(topic_soup, title, link, dom, results)
                    
            except Exception as e:
                print(f"Error processing topic {title}: {e}")
        
        # Special TV show handling if enabled
        if DEEP_CRAWL_TV:
            # Look for TV categories
            tv_results = find_tv_show_pages(dom)
            
            # Process each TV topic link
            for tv_topic in tv_results:
                try:
                    print(f"Processing TV show link: {tv_topic['title']}")
                    tv_page = scraper.get(tv_topic['link'], timeout=15).text
                    tv_soup = BeautifulSoup(tv_page, "html.parser")
                    
                    # Process the page and extract content
                    process_topic_page(tv_soup, tv_topic['title'], tv_topic['link'], dom, results)
                        
                except Exception as e:
                    print(f"Error processing TV topic: {e}")
                
    except Exception as e:
        print(f"Error fetching homepage: {e}")
    
    return results

def process_topic_page(soup, title, link, dom, results):
    """Process a topic page and extract all content"""
    # Look for magnet links
    magnets = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("magnet:?"):
            magnets.append(href)
    
    # If there are multiple magnet links, need to associate each with its title
    if len(magnets) > 1:
        # Look for section titles that might indicate different qualities
        quality_sections = soup.find_all(['h3', 'h4', 'strong'])
        
        # If there are multiple quality sections, match them with magnets
        if len(quality_sections) >= len(magnets):
            for i, magnet in enumerate(magnets):
                if i < len(quality_sections):
                    section_title = quality_sections[i].text.strip()
                    if section_title and len(section_title) > 5:
                        # Create entry with the section title
                        create_content_entry(soup, section_title, magnet, link, dom, results)
                else:
                    # Fallback for additional magnets
                    create_content_entry(soup, title, magnet, link, dom, results)
        else:
            # Fallback: just use the same title for all magnets
            for magnet in magnets:
                create_content_entry(soup, title, magnet, link, dom, results)
    elif len(magnets) == 1:
        # Single magnet link - use the page title
        create_content_entry(soup, title, magnets[0], link, dom, results)

def create_content_entry(soup, title, magnet, link, dom, results):
    """Create a content entry with all metadata"""
    # Extract better title
    clean_title = extract_proper_title(title, soup, link)
    
    # Get better image
    img_src = find_better_image(soup, clean_title, dom)
    
    # Extract TV show info
    tv_info = extract_tv_info(title)
    
    # Extract languages
    languages = extract_languages(title)
    
    # Extract quality
    qualities = extract_quality(title)
    
    # Extract date
    release_date = tv_info.get("year", "") or extract_date(title)
    
    # Extract category
    category = extract_category(soup, dom)
    
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
        "added": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_tv_show": tv_info["is_tv_show"],
        "show_name": tv_info["show_name"],
        "season": tv_info["season"],
        "episode": tv_info["episode"]
    })
    print(f"Added content: {clean_title}")

def find_tv_show_pages(dom):
    """Find TV show pages by browsing categories"""
    results = []
    try:
        # Look for categories like "TV Shows" or "Tamil TV"
        homepage = scraper.get(dom, timeout=15).text
        home_soup = BeautifulSoup(homepage, "html.parser")
        
        # Look for forum links that might be TV categories
        for link in home_soup.find_all("a"):
            href = link.get("href", "")
            text = link.text.strip()
            
            if (href and ("tv" in href.lower() or "tv" in text.lower() or 
                         "series" in href.lower() or "series" in text.lower())):
                try:
                    category_url = urljoin(dom, href)
                    print(f"Found TV category: {text} at {category_url}")
                    
                    # Visit the category page
                    category_page = scraper.get(category_url, timeout=15).text
                    category_soup = BeautifulSoup(category_page, "html.parser")
                    
                    # Find topic links
                    for topic_link in category_soup.select(".ipsDataItem_title a") or category_soup.find_all("a", class_="title"):
                        topic_title = topic_link.text.strip()
                        topic_href = urljoin(dom, topic_link.get("href", ""))
                        
                        if topic_title and topic_href:
                            results.append({
                                "title": topic_title,
                                "link": topic_href
                            })
                except Exception as e:
                    print(f"Error processing TV category {text}: {e}")
    except Exception as e:
        print(f"Error finding TV show pages: {e}")
        
    return results

def extract_date(title, soup=None):
    """Extract release date from title or content"""
    # Look for year in title
    year_match = re.search(r'\((\d{4})\)', title)
    if year_match:
        return year_match.group(1)
        
    # Default to current year if not found
    return datetime.datetime.now().strftime("%Y")

# ─── Generate HTML page ──────────────────────────────────────────────────
def generate_html_page(items):
    # Add categories dynamically
    categories = sorted(set([item['category'] for item in items if item['category']]))
    category_options = ""
    for category in categories:
        category_options += f'<option value="{category}">{category}</option>\n'
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>1TamilMV Magnet Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background-color: #f8f9fa; }
        .navbar { background-color: #343a40 !important; }
        .card { transition: transform 0.2s; margin-bottom: 20px; height: 100%; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
        .card-img-top { height: 200px; object-fit: cover; }
        .badge { margin-right: 5px; }
        .btn-magnet { background-color: #ff6700; border-color: #ff6700; }
        .btn-realdebrid { background-color: #3cb371; border-color: #3cb371; }
        .filter-bar { background-color: #fff; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .no-image { background-color: #e9ecef; display: flex; align-items: center; justify-content: center; color: #6c757d; height: 200px; }
        .card-title { min-height: 50px; overflow: hidden; }
        .language-badge { font-size: 0.7rem; }
        .tv-badge { background-color: #9c27b0; }
        .movie-badge { background-color: #2196f3; }
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
        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i> Found <span id="resultCount">""" + str(len(items)) + """</span> items. Use filters below to narrow results.
        </div>
        
        <div class="filter-bar">
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="input-group">
                        <input type="text" class="form-control" id="searchInput" placeholder="Search titles...">
                        <button class="btn btn-primary" type="button" id="searchButton">
                            <i class="fas fa-search"></i> Search
                        </button>
                    </div>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="contentTypeFilter">
                        <option value="">All Types</option>
                        <option value="tv">TV Shows</option>
                        <option value="movie">Movies</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="categoryFilter">
                        <option value="">All Categories</option>
                        """ + category_options + """
                    </select>
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="qualityFilter">
                        <option value="">All Qualities</option>
                        <option value="1080p">1080p</option>
                        <option value="720p">720p</option>
                        <option value="480p">480p</option>
                        <option value="4K">4K/UHD</option>
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
            </div>
            <div class="row mt-3">
                <div class="col-md-4">
                    <input type="text" class="form-control" id="showNameInput" placeholder="TV Show name (e.g., Office)">
                </div>
                <div class="col-md-2">
                    <select class="form-select" id="seasonFilter">
                        <option value="">All Seasons</option>
                        <option value="S01">Season 1</option>
                        <option value="S02">Season 2</option>
                        <option value="S03">Season 3</option>
                        <option value="S04">Season 4</option>
                        <option value="S05">Season 5</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <input type="text" class="form-control" id="episodeFilter" placeholder="Episode (e.g., EP01)">
                </div>
                <div class="col-md-2">
                    <input type="text" class="form-control" id="yearFilter" placeholder="Year (e.g., 2025)">
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

    # Add TV shows first
    for item in [i for i in items if i.get('is_tv_show')]:
        html = generate_item_card(item, html)
        
    # Then add movies
    for item in [i for i in items if not i.get('is_tv_show')]:
        html = generate_item_card(item, html)

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
        // Function to copy magnet link to clipboard
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

        // Wait for the DOM to be fully loaded
        document.addEventListener('DOMContentLoaded', function() {
            console.log("DOM loaded, initializing filters...");
            
            // Initialize event listeners
            document.getElementById('searchInput').addEventListener('input', debounce(filterItems, 300));
            document.getElementById('searchButton').addEventListener('click', function() {
                filterItems();
                const visibleResults = document.querySelectorAll('.magnet-item:not([style*="display: none"])').length;
                alert(`Found ${visibleResults} results matching your search criteria.`);
            });
            
            // Add Enter key support for search
            document.getElementById('searchInput').addEventListener('keyup', function(event) {
                if (event.key === "Enter") {
                    document.getElementById('searchButton').click();
                }
            });
            
            // Add other filter event listeners
            document.getElementById('contentTypeFilter').addEventListener('change', filterItems);
            document.getElementById('categoryFilter').addEventListener('change', filterItems);
            document.getElementById('qualityFilter').addEventListener('change', filterItems);
            document.getElementById('languageFilter').addEventListener('change', filterItems);
            document.getElementById('showNameInput').addEventListener('input', debounce(filterItems, 300));
            document.getElementById('seasonFilter').addEventListener('change', filterItems);
            document.getElementById('episodeFilter').addEventListener('input', debounce(filterItems, 300));
            document.getElementById('yearFilter').addEventListener('input', debounce(filterItems, 300));
            document.getElementById('sortOrder').addEventListener('change', sortItems);
            
            // Initial filter and sort
            filterItems();
            sortItems();
            
            console.log("Filters initialized");
        });

        // Debounce function to limit how often a function is called
        function debounce(func, wait) {
            let timeout;
            return function() {
                const context = this;
                const args = arguments;
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    func.apply(context, args);
                }, wait);
            };
        }

        // Main filtering function
        function filterItems() {
            console.log("Filtering items...");
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const contentType = document.getElementById('contentTypeFilter').value;
            const categoryFilter = document.getElementById('categoryFilter').value;
            const qualityFilter = document.getElementById('qualityFilter').value.toLowerCase();
            const languageFilter = document.getElementById('languageFilter').value;
            const showName = document.getElementById('showNameInput').value.toLowerCase();
            const seasonFilter = document.getElementById('seasonFilter').value;
            const episodeFilter = document.getElementById('episodeFilter').value.toLowerCase();
            const yearFilter = document.getElementById('yearFilter').value;
            
            console.log("Search term:", searchTerm);
            
            let visibleCount = 0;
            
            // Loop through all items and filter them
            document.querySelectorAll('.magnet-item').forEach(item => {
                try {
                    const title = (item.getAttribute('data-title') || "").toLowerCase();
                    const originalTitle = (item.getAttribute('data-original-title') || "").toLowerCase();
                    const category = item.getAttribute('data-category') || "";
                    const languages = (item.getAttribute('data-languages') || "").split(',');
                    const qualities = (item.getAttribute('data-qualities') || "").split(',');
                    const isTvShow = (item.getAttribute('data-tv-show') || "false") === 'true';
                    const showNameAttr = (item.getAttribute('data-show-name') || "").toLowerCase();
                    const season = item.getAttribute('data-season') || "";
                    const episode = (item.getAttribute('data-episode') || "").toLowerCase();
                    const year = item.getAttribute('data-year') || "";
                    
                    // Check if item matches all filters
                    const titleMatch = !searchTerm || title.includes(searchTerm) || originalTitle.includes(searchTerm);
                    const contentTypeMatch = !contentType || 
                        (contentType === 'tv' && isTvShow) || 
                        (contentType === 'movie' && !isTvShow);
                    const categoryMatch = !categoryFilter || category === categoryFilter;
                    const qualityMatch = !qualityFilter || qualities.some(q => q.toLowerCase().includes(qualityFilter));
                    const languageMatch = !languageFilter || languages.includes(languageFilter);
                    const showNameMatch = !showName || showNameAttr.includes(showName);
                    const seasonMatch = !seasonFilter || season.includes(seasonFilter);
                    const episodeMatch = !episodeFilter || episode.includes(episodeFilter);
                    const yearMatch = !yearFilter || year.includes(yearFilter);
                    
                    // Show or hide the item based on filter matches
                    if (titleMatch && contentTypeMatch && categoryMatch && qualityMatch && 
                        languageMatch && showNameMatch && seasonMatch && episodeMatch && yearMatch) {
                        item.style.display = '';
                        visibleCount++;
                    } else {
                        item.style.display = 'none';
                    }
                } catch (error) {
                    console.error("Error filtering item:", error);
                    item.style.display = ''; // Show item on error
                }
            });
            
            // Update the count display
            document.getElementById('resultCount').textContent = visibleCount;
            console.log(`Filtering complete. Showing ${visibleCount} items.`);
        }

        // Sorting function
        function sortItems() {
            console.log("Sorting items...");
            const container = document.getElementById('magnetCards');
            const sortOrder = document.getElementById('sortOrder').value;
            const items = Array.from(container.getElementsByClassName('magnet-item'));
            
            items.sort(function(a, b) {
                const aTitle = (a.getAttribute('data-title') || "").toLowerCase();
                const bTitle = (b.getAttribute('data-title') || "").toLowerCase(); 
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
                    default:
                        return 0;
                }
            });
            
            // Reappend sorted items to the container
            items.forEach(item => container.appendChild(item));
            console.log("Sorting complete");
        }
    </script>
</body>
</html>
"""
    return html


def generate_item_card(item, html_container):
    """Generate HTML for a single item card"""
    title = item['title']
    clean_title = item.get('clean_title', title) 
    magnet = urllib.parse.quote(item['magnet'])  # URL-encode the magnet link
    category = item.get('category', "Uncategorized")
    img_src = item.get('image', "")
    languages = item.get('languages', [])
    qualities = item.get('qualities', [])
    release_date = item.get('release_date', "")
    added_date = item.get('added', "")
    is_tv_show = item.get('is_tv_show', False)
    show_name = item.get('show_name', "")
    season = item.get('season', "")
    episode = item.get('episode', "")
    
    # Create badges for quality markers
    quality_badges = ""
    for quality in qualities:
        badge_class = "bg-info" if quality == "1080p" else "bg-secondary" if quality == "720p" else "bg-warning text-dark" if quality == "480p" else "bg-danger" if quality in ["4K", "2160p", "UHD"] else "bg-warning text-dark"
        quality_badges += f'<span class="badge {badge_class}">{quality}</span>'
        
    # Create badges for languages
    language_badges = ""
    for lang in languages:
        language_badges += f'<span class="badge bg-primary language-badge">{lang}</span>'
    
    # Content type badge
    content_type_badge = f'<span class="badge tv-badge">TV</span>' if is_tv_show else f'<span class="badge movie-badge">Movie</span>'
    
    # Season/Episode info
    season_episode = ""
    if is_tv_show:
        if season and episode:
            season_episode = f" • {season} {episode}"
    
    html_content = f"""
        <div class="col-md-3 magnet-item" 
            data-category="{category}"
            data-title="{clean_title.lower().replace('"', '&quot;')}" 
            data-original-title="{title.lower().replace('"', '&quot;')}"
            data-year="{release_date}"
            data-added="{added_date}"
            data-languages="{','.join(languages)}"
            data-qualities="{','.join(qualities)}"
            data-tv-show="{str(is_tv_show).lower()}"
            data-show-name="{show_name.replace('"', '&quot;')}"
            data-season="{season}"
            data-episode="{episode}">
            <div class="card h-100">
                <div class="card-img-top-container">
                    {f'<img src="{img_src}" class="card-img-top" alt="{clean_title}">' if img_src else '<div class="no-image"><span>No Image</span></div>'}
                </div>
                <div class="card-body">
                    <h5 class="card-title" title="{clean_title}">{clean_title}</h5>
                    <div class="mb-2">
                        {content_type_badge}
                        {quality_badges}
                        {language_badges}
                    </div>
                    <p class="card-text">
                        <small class="text-muted">{category}{season_episode} • {release_date}</small>
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
    html_container += html_content
    return html_container

def remove_duplicates(items):
    """Remove duplicate entries based on magnet links"""
    print("Removing duplicate entries...")
    
    # Use dictionary to track unique magnet links
    unique_items = {}
    duplicate_count = 0
    
    for item in items:
        magnet_link = item['magnet']
        
        # If we haven't seen this magnet link before, add it
        if magnet_link not in unique_items:
            unique_items[magnet_link] = item
        else:
            duplicate_count += 1
            # If this item has a better title than the existing one, replace it
            if len(item.get('clean_title', '')) > len(unique_items[magnet_link].get('clean_title', '')):
                unique_items[magnet_link] = item
    
    # Check for similar titles with different magnet links
    similar_titles = {}
    for magnet, item in unique_items.items():
        clean_title = item.get('clean_title', '').lower()
        if len(clean_title) > 5:
            title_key = clean_title[:10]  # First 10 chars as key
            if title_key in similar_titles:
                similar_titles[title_key].append(magnet)
            else:
                similar_titles[title_key] = [magnet]
    
    print(f"Removed {duplicate_count} duplicate entries")
    return list(unique_items.values())


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
    print(f"\nFound {len(items)} items with potential duplicates")
    
    # Remove duplicates
    items = remove_duplicates(items)
    print(f"Remaining unique items after deduplication: {len(items)}")
    
    save_data(items)
    print("Update completed successfully")


if __name__ == "__main__":
    main()
