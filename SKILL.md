---
name: rss-to-joplin
description: Automated workflow skill to sync RSS feeds, parse articles, extract full markdown content, and archive them to categorized Joplin notebooks.
---

# RSS-to-Joplin Sync Workflow 📰➡️📝

Use this skill to sync, configure, debug, or automate the `rss-to-joplin` workflow. This tool retrieves web feeds, scrapes full text, sanitizes content to avoid Joplin WebDAV/Nginx connection limits, and automatically creates/organizes notebooks.

---

## 📁 Project Structure

All workflow development files reside in this repository:
- [`main.py`](main.py): The main Python syncing engine.
- [`config.example.json`](config.example.json): Template for feeding sources and routing configuration.
- [`.env.example`](.env.example): Environment variable configuration template.
- [`requirements.txt`](requirements.txt): Python dependencies (`feedparser`, `trafilatura`, `requests`, `python-dotenv`).

---

## ⚡ Execution Commands

### Manual Sync Run
Always make sure Joplin Desktop is running and Web Clipper is enabled (default port `41184`).

```bash
# Sync using configurations defined in config.json
python3 main.py

# Override with a specific RSS feed URL
python3 main.py --feed https://news.ycombinator.com/rss

# Run with AI summarization and tagging enabled (Ollama/Cloud)
python3 main.py --summary

# Process multiple feeds via command line
python3 main.py --feed https://news.ycombinator.com/rss --feed https://krebsonsecurity.com/feed/ --summary

# Run in lightweight snippet mode (skips full-text scraping)
python3 main.py --no-full-text
```

### Automation via Crontab
To sync feeds in the background, configure a cron job using `crontab -e`:
```cron
0 */6 * * * /usr/bin/python3 /path/to/rss-to-joplin/main.py >> /var/log/rss_joplin.log 2>&1
```

---

## ⚙️ Configuration File (`config.json`)

Configure source feeds and matching rules in `config.json`:

```json
{
  "default_notebook": "RSS Articles",
  "feeds": [
    "https://news.ycombinator.com/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
  ],
  "notebook_map": {
    "Hacker News": "Tech News",
    "security": "Cybersecurity"
  }
}
```

### 🧠 Notebook Routing Rules
Notebook routing checks three conditions:
1. **Exact Feed Title Match**: Checks if the RSS feed title matches a key in `notebook_map` (e.g. `"Hacker News"` matches and maps to `"Tech News"`).
2. **Partial Keyword Search**: Looks for key strings (e.g., `"security"`) inside the feed title, article title, or URL.
3. **Fallback**: Routes to the `default_notebook` (e.g., `"RSS Articles"`).

*Note: The script automatically creates the target notebook if it does not exist.*

---

## 🛠️ Architecture and Optimization Decisions

- **Deduplication via Search API**: Instead of querying folders line-by-line, the script queries Joplin's Search API (`/search?query=source_url:"..."`) to check if an article URL already exists. This avoids paging limitations and speeds up execution.
- **Base64 & Size Sanitization**: To prevent `Error 499: Client Closed Request` errors when Joplin syncs to remote servers (Nextcloud/WebDAV), the workflow automatically strips inline base64 images and truncates notes exceeding `150,000` characters.
- **AI-Powered Summarization & Tagging**: When run with `--summary`, the script sends the first 3,000 characters of the scraped article to an LLM (Ollama or cloud via standard OpenAI compatible API). The LLM yields a JSON summary and a matching tag/category (e.g. `tech`, `news`, `ai`, `health`).
- **Joplin Tag Integration**: Assigns AI-extracted tags directly to Joplin notes for easier search and organization, avoiding manual metadata curation.
- **Language Filtering**: Scrapes article text targeting English (`target_language='en'`). If the content is in a foreign language or can't be scraped, it skips syncing that article when in full-text mode.
- **Mobile Scraping User-Agent**: Uses a custom Android/Pixel 10 Pro XL User-Agent to bypass standard scraper blockers.

