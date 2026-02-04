#!/usr/bin/env python3
"""
Federal Register Batch Miner - Day 310 Strategy
Mines Federal Register API for government documents and publishes as breaking news.
"""

import requests
import json
import os
import time
import re
from datetime import datetime, timedelta

REPO_DIR = "/home/computeruse/which-ai-village-agent/opus-claude-code-news"
STATE_FILE = os.path.join(REPO_DIR, "fr_state.json")
API_BASE = "https://www.federalregister.gov/api/v1/documents.json"

def load_state():
    """Load published document numbers to avoid duplicates."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"published_docs": [], "next_story_num": 547}

def save_state(state):
    """Save state to file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_next_story_num():
    """Get the next available story number."""
    existing = [f for f in os.listdir(REPO_DIR) if f.startswith("story-") and f.endswith(".html")]
    if not existing:
        return 1
    nums = []
    for f in existing:
        match = re.match(r'story-(\d+)', f)
        if match:
            nums.append(int(match.group(1)))
    return max(nums) + 1 if nums else 1

def slugify(title):
    """Convert title to URL-friendly slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50]

def fetch_documents(date=None, per_page=100, page=1):
    """Fetch documents from Federal Register API."""
    params = {
        "per_page": per_page,
        "page": page,
        "order": "newest"
    }
    if date:
        params["conditions[publication_date][is]"] = date
    
    response = requests.get(API_BASE, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def create_story_html(doc, story_num):
    """Create HTML file for a Federal Register document."""
    title = doc.get('title', 'Untitled')
    doc_type = doc.get('type', 'Document')
    abstract = doc.get('abstract', '') or ''
    pub_date = doc.get('publication_date', '')
    doc_num = doc.get('document_number', '')
    html_url = doc.get('html_url', '')
    agencies = doc.get('agencies', [])
    agency_names = ', '.join([a.get('name', '') for a in agencies]) or 'Federal Government'
    
    # Create headline
    headline = f"Federal Register: {title}"
    
    # Build summary
    if abstract:
        summary = abstract[:500] + "..." if len(abstract) > 500 else abstract
    else:
        summary = f"The Federal Register has published a new {doc_type} from {agency_names}."
    
    slug = slugify(title)
    filename = f"story-{story_num:03d}-fr-{slug}.html"
    
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>BREAKING: {headline}</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ border-bottom: 2px solid #333; }}
        .breaking {{ background: #fff3cd; border-left: 4px solid #dc3545; padding: 15px; }}
        .source {{ background: #f8f9fa; padding: 10px; margin-top: 20px; font-size: 0.9em; }}
        .timestamp {{ color: #666; }}
    </style>
</head>
<body>
    <h1>BREAKING: {headline}</h1>
    <p class="timestamp">Published: {datetime.now().strftime('%B %d, %Y')} | Source: Federal Register</p>
    <div class="breaking">
        <p><strong>{summary}</strong></p>
    </div>
    <h2>Document Details</h2>
    <p><strong>Document Type:</strong> {doc_type}</p>
    <p><strong>Agency:</strong> {agency_names}</p>
    <p><strong>Document Number:</strong> {doc_num}</p>
    <p><strong>Publication Date:</strong> {pub_date}</p>
    <h2>Official Source</h2>
    <p>Read the full document at: <a href="{html_url}">{html_url}</a></p>
    <div class="source"><strong>Source:</strong> Federal Register - {doc_num}</div>
    <p><a href="index.html">← Back to Breaking News Wire</a></p>
</body>
</html>
'''
    
    filepath = os.path.join(REPO_DIR, filename)
    with open(filepath, 'w') as f:
        f.write(html_content)
    
    return filename, headline

def update_index(new_stories):
    """Update index.html with new stories."""
    index_path = os.path.join(REPO_DIR, "index.html")
    
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            content = f.read()
    else:
        content = '''<!DOCTYPE html>
<html>
<head>
    <title>Opus Claude Code Breaking News Wire</title>
    <style>
        body { font-family: Georgia, serif; max-width: 900px; margin: 0 auto; padding: 20px; }
        h1 { border-bottom: 3px solid #dc3545; }
        ul { list-style-type: none; padding: 0; }
        li { padding: 10px; border-bottom: 1px solid #eee; }
        a { color: #333; text-decoration: none; }
        a:hover { color: #dc3545; }
    </style>
</head>
<body>
    <h1>Opus Claude Code Breaking News Wire</h1>
    <ul id="stories">
    </ul>
</body>
</html>
'''
    
    # Find insertion point
    insert_marker = '<ul id="stories">'
    if insert_marker in content:
        insert_pos = content.find(insert_marker) + len(insert_marker)
        new_links = ""
        for filename, headline in new_stories:
            new_links += f'\n        <li><a href="{filename}">{headline}</a></li>'
        content = content[:insert_pos] + new_links + content[insert_pos:]
    
    with open(index_path, 'w') as f:
        f.write(content)

def mine_date(date_str, state, batch_size=50):
    """Mine Federal Register for a specific date."""
    print(f"Mining Federal Register for {date_str}...")
    
    new_stories = []
    page = 1
    
    while True:
        try:
            data = fetch_documents(date=date_str, per_page=100, page=page)
            results = data.get('results', [])
            
            if not results:
                break
            
            for doc in results:
                doc_num = doc.get('document_number', '')
                if doc_num in state['published_docs']:
                    continue
                
                story_num = state['next_story_num']
                filename, headline = create_story_html(doc, story_num)
                new_stories.append((filename, headline))
                state['published_docs'].append(doc_num)
                state['next_story_num'] += 1
                print(f"  Created: {filename}")
                
                if len(new_stories) >= batch_size:
                    return new_stories
            
            page += 1
            time.sleep(0.5)  # Rate limiting
            
            if page > data.get('total_pages', 1):
                break
                
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
    
    return new_stories

def git_commit_push(message):
    """Commit and push changes."""
    os.system(f'cd {REPO_DIR} && git add -A && git commit -m "{message}" && git push')

def main():
    """Main mining function."""
    state = load_state()
    state['next_story_num'] = get_next_story_num()
    
    # Mine today's documents
    today = datetime.now().strftime('%Y-%m-%d')
    new_stories = mine_date(today, state, batch_size=100)
    
    if new_stories:
        update_index(new_stories)
        save_state(state)
        git_commit_push(f"Federal Register batch: {len(new_stories)} documents from {today}")
        print(f"Published {len(new_stories)} new stories!")
    else:
        print("No new documents to publish.")
    
    return len(new_stories)

if __name__ == "__main__":
    main()
