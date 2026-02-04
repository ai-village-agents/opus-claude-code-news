#!/usr/bin/env python3
"""
Historical Federal Register Batch Miner
Mines multiple dates of Federal Register documents.
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
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"published_docs": [], "next_story_num": 547}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_next_story_num():
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
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50]

def fetch_documents(date=None, per_page=100, page=1):
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
    title = doc.get('title', 'Untitled')
    doc_type = doc.get('type', 'Document')
    abstract = doc.get('abstract', '') or ''
    pub_date = doc.get('publication_date', '')
    doc_num = doc.get('document_number', '')
    html_url = doc.get('html_url', '')
    agencies = doc.get('agencies', [])
    agency_names = ', '.join([a.get('name', '') for a in agencies]) or 'Federal Government'
    
    headline = f"Federal Register: {title}"
    
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
    <p class="timestamp">Published: {pub_date} | Source: Federal Register</p>
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

def mine_date_all(date_str, state):
    """Mine ALL documents from a specific date."""
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
            
            page += 1
            time.sleep(0.3)  # Rate limiting
            
            if page > data.get('total_pages', 1):
                break
                
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break
    
    print(f"  -> {len(new_stories)} new documents")
    return new_stories

def git_commit_push(message):
    os.system(f'cd {REPO_DIR} && git add -A && git commit -m "{message}" && git push')

def main(days_back=30, batch_commit_size=100):
    """Mine historical Federal Register documents."""
    state = load_state()
    state['next_story_num'] = get_next_story_num()
    
    total_new = 0
    batch_stories = []
    
    # Mine documents from past N days
    for i in range(days_back):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        new_stories = mine_date_all(date, state)
        batch_stories.extend(new_stories)
        total_new += len(new_stories)
        
        # Commit in batches
        if len(batch_stories) >= batch_commit_size:
            save_state(state)
            git_commit_push(f"Federal Register historical batch: {len(batch_stories)} documents")
            print(f"Committed batch of {len(batch_stories)} stories. Total: {total_new}")
            batch_stories = []
    
    # Final commit for remaining
    if batch_stories:
        save_state(state)
        git_commit_push(f"Federal Register historical batch: {len(batch_stories)} documents")
        print(f"Final batch: {len(batch_stories)} stories. Total: {total_new}")
    
    print(f"\n=== COMPLETE: Published {total_new} new Federal Register documents ===")
    return total_new

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    main(days_back=days)
