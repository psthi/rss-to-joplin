#!/usr/bin/env python3
"""
RSS-to-Joplin: Automated Full-Text RSS Archiver & Notebook Router for Joplin.
Plug-and-Play Python script that fetches RSS feeds, scrapes full-text articles using Trafilatura,
and syncs them into Joplin Notebooks via the Web Clipper REST API.
"""

import os
import sys
import re
import json
import argparse
import requests
import feedparser
import trafilatura
import time
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

DEFAULT_API_URL = "http://localhost:41184"
DEFAULT_NOTEBOOK = "RSS Articles"

def load_or_create_config(config_path):
    """Loads configuration file or returns a default template if not found."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Warning: Could not read config file {config_path}: {e}")
    
    # Return sensible plug-and-play default config
    return {
        "default_notebook": DEFAULT_NOTEBOOK,
        "feeds": [
            "https://news.ycombinator.com/rss"
        ],
        "notebook_map": {
            "Hacker News": "Tech News",
            "security": "Cybersecurity"
        }
    }

def get_or_create_notebook(api_url, token, name, cache):
    """Finds or creates a notebook ID in Joplin by name (with caching)."""
    if name in cache:
        return cache[name]

    try:
        res = requests.get(f"{api_url}/folders?token={token}", timeout=15).json()
        for folder in res.get("items", []):
            if folder.get("title").strip().lower() == name.strip().lower():
                folder_id = folder.get("id")
                cache[name] = folder_id
                return folder_id
    except Exception as e:
        print(f"❌ Error communicating with Joplin API: {e}")
        sys.exit(1)

    # Create notebook if not found
    res = requests.post(f"{api_url}/folders?token={token}", json={"title": name}, timeout=15)
    if res.status_code == 200:
        folder_id = res.json().get("id")
        cache[name] = folder_id
        return folder_id
    else:
        print(f"❌ Failed to create notebook '{name}' in Joplin: {res.text}")
        sys.exit(1)

def resolve_target_notebook(feed_title, item_title, url, default_notebook, notebook_map):
    """Determines which Joplin Notebook an item should belong to based on mapping rules."""
    # Check exact feed title match
    if feed_title in notebook_map:
        return notebook_map[feed_title]

    # Partial keyword match against feed title or URL
    for key, target_nb in notebook_map.items():
        if key and (key.lower() in feed_title.lower() or key.lower() in url.lower() or key.lower() in item_title.lower()):
            return target_nb

    return default_notebook

def clean_markdown_content(md_text, max_len=150000):
    """Sanitizes markdown content by stripping massive base64 images and capping size to prevent Joplin sync timeouts (Error 499)."""
    if not md_text:
        return md_text
    
    # Remove inline base64 data image URIs: ![alt](data:image/...;base64,...)
    md_cleaned = re.sub(r'!\[([^\]]*)\]\(data:image/[^;]+;base64,[A-Za-z0-9+/=]+\)', r'*[Inline image omitted]*', md_text)
    md_cleaned = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '', md_cleaned)
    
    if len(md_cleaned) > max_len:
        md_cleaned = md_cleaned[:max_len] + "\n\n*(...Article truncated due to size limit...)*"
        
    return md_cleaned

def fetch_full_article_markdown(url):
    """Downloads webpage at URL and extracts full article body in Markdown format."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 10 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Upgrade-Insecure-Requests": "1"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            extracted = trafilatura.extract(
                response.text, 
                output_format='markdown',
                target_language='en',
                include_links=True,
                include_images=True,
                include_formatting=True
            )
            if extracted and len(extracted.strip()) > 100:
                return clean_markdown_content(extracted)
    except Exception as e:
        print(f"  ⚠️ Could not fetch full article from {url}: {e}")
    return None

def get_article_summary_and_tags(content, title):
    """Uses LLM (Ollama or Cloud provider via environment variables) to summarize the article and classify it into a category."""
    # Limit content length to prevent slow processing / VRAM overflow
    excerpt = content[:3000]
    prompt = f"""You are a professional research assistant cataloging web articles for a digital library.
Analyze the following article text.

Title: {title}

Article:
{excerpt}

Return a JSON object containing:
1. "summary": A concise, bulleted TL;DR of the key points (maximum 3 bullet points, markdown list format).
2. "category": A string classifying this article. Choose EXACTLY one category from this list: ["news", "tech", "ai", "health"].

Output ONLY the JSON object. Do not include markdown code blocks or preambles.
"""
    try:
        api_url = os.environ.get("LLM_API_URL", "http://localhost:11434/v1/chat/completions")
        model = os.environ.get("LLM_MODEL", "phi3.5:latest")
        api_key = os.environ.get("LLM_API_KEY", "")

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        is_native_ollama = "/api/chat" in api_url

        if is_native_ollama:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "options": {
                    "temperature": 0.1,
                    "num_predict": 250
                },
                "stream": False
            }
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 250
            }

        res = requests.post(api_url, json=payload, headers=headers, timeout=120)
        if res.status_code == 200:
            resp_data = res.json()
            if is_native_ollama:
                raw_text = resp_data.get("message", {}).get("content", "").strip()
            else:
                choices = resp_data.get("choices", [])
                raw_text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
            
            # Clean markdown code fences if model returned them
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\n|\n```$", "", raw_text, flags=re.MULTILINE).strip()
            
            parsed = json.loads(raw_text)
            category = parsed.get("category", "tech").lower()
            # Fallback validation to ensure it matches allowed list
            if category not in ["news", "tech", "ai", "health"]:
                category = "tech"
            return parsed.get("summary", ""), [category]
    except Exception as e:
        print(f"  ⚠️ LLM summary/tag extraction failed: {e}")
    return "", ["tech"]

def add_tags_to_note(api_url, token, note_id, tags):
    """Creates tags in Joplin and associates them with a note."""
    for tag_name in tags:
        tag_name = tag_name.strip().lower()
        if not tag_name:
            continue
        try:
            # 1. Create/Find tag in Joplin
            res = requests.post(f"{api_url}/tags?token={token}", json={"title": tag_name}, timeout=15)
            if res.status_code == 200:
                tag_id = res.json().get("id")
                # 2. Link tag to note
                requests.post(f"{api_url}/tags/{tag_id}/notes?token={token}", json={"id": note_id}, timeout=15)
        except Exception as e:
            print(f"  ⚠️ Failed to attach tag '{tag_name}': {e}")


def fetch_entries_from_rss_url(feed_url):
    """Fetches and parses entries directly from an RSS feed URL using feedparser."""
    print(f"📡 Fetching RSS feed: {feed_url}")
    parsed = feedparser.parse(feed_url)
    feed_title = parsed.feed.get("title", feed_url)
    entries = []
    
    for entry in parsed.entries:
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published_at = ""
        if published_parsed:
            try:
                published_at = time.strftime("%m-%d-%Y", published_parsed)
            except Exception:
                published_at = entry.get("published", entry.get("updated", ""))
        else:
            published_at = entry.get("published", entry.get("updated", ""))
            
        entries.append({
            "title": entry.get("title", "Untitled Article"),
            "url": entry.get("link", ""),
            "published_at": published_at,
            "summary": entry.get("summary", entry.get("description", "")),
            "feed_title": feed_title
        })
    return feed_title, entries

def sync_rss_to_joplin(api_url, token, default_notebook, feed_urls, notebook_map, fetch_full_articles, use_llm=False):
    notebook_cache = {}

    # 1. Verify Joplin API connection
    try:
        requests.get(f"{api_url}/folders?token={token}", timeout=15).json()
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Unable to connect to Joplin API at {api_url}.")
        print("   Please make sure Joplin Desktop is running and Web Clipper service is enabled.")
        sys.exit(1)

    total_synced = 0
    total_updated = 0

    for feed_url in feed_urls:
        feed_title, entries = fetch_entries_from_rss_url(feed_url)
        print(f"  Found {len(entries)} articles in '{feed_title}'...\n")

        for item in entries:
            title = item.get("title", "Untitled Article")
            url = item.get("url", "")
            published = item.get("published_at", "")
            rss_snippet = item.get("summary", "")

            target_notebook_name = resolve_target_notebook(feed_title, title, url, default_notebook, notebook_map)
            notebook_id = get_or_create_notebook(api_url, token, target_notebook_name, notebook_cache)

            # Extract full article content if enabled
            full_md = None
            if fetch_full_articles and url:
                full_md = fetch_full_article_markdown(url)

            # If full-text extraction failed or returned non-English (which returns None),
            # check if we should skip importing if we only want English articles.
            # (If full_md is None and we parsed a non-English page, discard it).
            if fetch_full_articles and not full_md:
                print(f"  ⚠️ Skipping {title[:40]}... (not retrieved or non-English).")
                continue

            final_content = full_md if full_md else rss_snippet

            # Format markdown body
            body = f"# [{title}]({url})\n\n" if url else f"# {title}\n\n"
            if published:
                body += f"*Published: {published}*\n\n"
            
            tags = []
            if use_llm and final_content:
                print(f"  🧠 Generating local AI summary and tags using phi3.5...")
                summary, extracted_tags = get_article_summary_and_tags(final_content, title)
                if summary:
                    if isinstance(summary, list):
                        summary_text = "\n".join(summary)
                    else:
                        summary_text = str(summary)
                    body += f"## TL;DR Summary\n{summary_text}\n\n---\n\n"
                tags = extracted_tags

            body += final_content

            # Query Joplin search API for existing note by source URL to avoid paging limitations
            note_id = None
            if url:
                # Clean URL for search query (escape special characters if needed, or query exact)
                search_url = url.replace('"', '\\"')
                search_resp = requests.get(f"{api_url}/search?query=source_url:\"{search_url}\"&token={token}", timeout=15).json()
                items = search_resp.get("items", [])
                if items:
                    note_id = items[0].get("id")

            if note_id:
                resp = requests.put(
                    f"{api_url}/notes/{note_id}?token={token}",
                    json={"body": body, "title": title, "parent_id": notebook_id, "source_url": url},
                    timeout=15
                )
                if resp.status_code == 200:
                    total_updated += 1
                    print("  ✓ Updated existing Joplin note with full article body.")
                    if tags:
                        add_tags_to_note(api_url, token, note_id, tags)
            else:
                note_data = {
                    "title": title,
                    "body": body,
                    "parent_id": notebook_id,
                    "source_url": url
                }
                resp = requests.post(f"{api_url}/notes?token={token}", json=note_data, timeout=15)
                if resp.status_code == 200:
                    total_synced += 1
                    created_note_id = resp.json().get("id")
                    print("  ✓ Saved new full-text article to Joplin.")
                    if tags and created_note_id:
                        add_tags_to_note(api_url, token, created_note_id, tags)

    print(f"\n🎉 Finished! Created {total_synced} new notes, updated {total_updated} existing notes.")

def main():
    parser = argparse.ArgumentParser(description="RSS-to-Joplin Full-Text Archiver (Plug-and-Play)")
    parser.add_argument("--token", default=os.environ.get("JOPLIN_TOKEN", ""), help="Joplin Web Clipper API Token")
    parser.add_argument("--url", default=os.environ.get("JOPLIN_API_URL", DEFAULT_API_URL), help="Joplin API Base URL")
    parser.add_argument("--feed", action="append", help="RSS Feed URL to process (can specify multiple times)")
    parser.add_argument("--default-notebook", default=os.environ.get("DEFAULT_NOTEBOOK", ""), help="Default Joplin notebook name")
    parser.add_argument("--config", default="config.json", help="Path to config.json file")
    parser.add_argument("--no-full-text", action="store_true", help="Disable Trafilatura full article scraping")
    parser.add_argument("--summary", action="store_true", help="Generate local AI summaries and tags using Ollama phi3.5")

    args = parser.parse_args()

    token = args.token
    if not token:
        print("❌ Error: Joplin API Token is required.")
        print("   Set JOPLIN_TOKEN in your .env file or run with: python main.py --token YOUR_TOKEN")
        sys.exit(1)

    cfg = load_or_create_config(args.config)
    default_notebook = args.default_notebook if args.default_notebook else cfg.get("default_notebook", DEFAULT_NOTEBOOK)
    notebook_map = cfg.get("notebook_map", {})
    
    feed_urls = args.feed if args.feed else cfg.get("feeds", [])
    if not feed_urls:
        feed_urls = ["https://news.ycombinator.com/rss"]

    sync_rss_to_joplin(
        api_url=args.url.rstrip("/"),
        token=token,
        default_notebook=default_notebook,
        feed_urls=feed_urls,
        notebook_map=notebook_map,
        fetch_full_articles=not args.no_full_text,
        use_llm=args.summary
    )

if __name__ == "__main__":
    main()
