# RSS-to-Joplin 📰➡️📝

> **Plug-and-Play Full-Text RSS Archiver & Intelligent Notebook Router for Joplin**

[![Joplin](https://img.shields.io/badge/Joplin-Data_API-blue?logo=joplin)](https://joplinapp.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-green?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`rss-to-joplin` is an easy-to-use, zero-maintenance Python tool that automatically fetches RSS feeds, scrapes full article text using [Trafilatura](https://github.com/adbar/trafilatura), and archives them into categorized [Joplin](https://joplinapp.org/) notebooks via the Joplin Web Clipper Data API.

*Keywords: Joplin RSS Sync, Joplin RSS Archiver, Joplin Data API, Full-Text RSS to Joplin, Self-Hosted News Reader for Joplin.*

---

## ⚡ 1-Minute Plug & Play Setup

No complex setup or external tools required—just Python!

```bash
# 1. Clone & install dependencies
git clone https://github.com/psthi/rss-to-joplin.git
cd rss-to-joplin
pip install -r requirements.txt

# 2. Run with your Joplin Web Clipper Token and any RSS feed!
python3 main.py --token YOUR_JOPLIN_TOKEN --feed https://news.ycombinator.com/rss
```

---

## 🌟 Key Features

- 🔌 **100% Plug-and-Play**: Built-in RSS parser (`feedparser`) and article scraper (`trafilatura`)—runs out of the box with zero third-party services.
- 📖 **Full-Text Article Extraction**: Automatically bypasses truncated RSS snippets to fetch complete web articles, images, and formatting into clean Markdown.
- 📂 **Automated Notebook Categorization**: Routes articles to specific Joplin notebooks based on RSS feed titles or keyword rules (e.g. *Tech News*, *Cybersecurity*).
- 🔄 **Smart Update & Deduplication**: Checks existing notes and updates previews with full-text article markdown.
- 🔒 **Privacy-First & Self-Hosted**: Runs 100% locally on your computer via Joplin's local Web Clipper API (`http://localhost:41184`).

---

## ⚙️ Configuration (Optional)

### Option A: `.env` File
Create a `.env` file in the project folder so you don't have to pass your token manually every time:

```env
JOPLIN_TOKEN=your_joplin_web_clipper_token_here
JOPLIN_API_URL=http://localhost:41184
DEFAULT_NOTEBOOK=RSS Articles
```

*(Retrieve your token in Joplin under Tools -> Options -> Web Clipper).*

### Option B: `config.json`
Define your RSS feeds and notebook routing rules in `config.json`:

```json
{
  "default_notebook": "RSS Articles",
  "feeds": [
    "https://news.ycombinator.com/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
  ],
  "notebook_map": {
    "Hacker News": "Tech & Startups",
    "New York Times": "World News",
    "security": "Cybersecurity"
  }
}
```

### 🗺️ How Automated Notebook Routing Works

The script resolves where each article belongs using a 3-step intelligent matching engine:

1. **Exact Feed Title Match**: Checks if the RSS feed title matches a key in `notebook_map` (e.g. `"Hacker News"` ➔ routes to `"Tech & Startups"`).
2. **Keyword Search**: If no exact match exists, it checks if any keyword in `notebook_map` (e.g. `"security"`) appears in the **feed name**, **article title**, or **URL** (e.g. an article from `krebsonsecurity.com` ➔ routes to `"Cybersecurity"`).
3. **Auto-Creation & Fallback**: Automatically creates the target notebook in Joplin if it doesn't exist yet. If no rules match, the article is routed to your `default_notebook` (e.g., `"RSS Articles"`).

---

## 🖥️ Usage Examples

```bash
# Process feeds defined in config.json
python3 main.py

# Process specific RSS feed URLs from command line
python3 main.py --feed https://news.ycombinator.com/rss --feed https://krebsonsecurity.com/feed/

# Run without full-text scraping (snippets only)
python3 main.py --no-full-text
```

### Automation via Cron
Run automatically every 6 hours by adding an entry to `crontab -e`:

```cron
0 */6 * * * /usr/bin/python3 /path/to/rss-to-joplin/main.py >> /var/log/rss_joplin.log 2>&1
```

---

## 🛠️ Troubleshooting & Joplin Sync Notes

### `Error 499: Client Closed Request` during Remote Sync
If Joplin shows `Error 499: Client Closed Request` when synchronizing with Nextcloud, Joplin Server, or WebDAV:
1. **Oversized Note Payload Prevention**: `rss-to-joplin` automatically strips heavy inline base64 image strings (`data:image/...;base64,...`) and caps max note length to prevent ballooning note sizes that overload WebDAV/Nginx connections.
2. **Re-sync in Joplin**: Simply click **Synchronise** again in Joplin Desktop. Joplin tracks item sync state independently and will resume uploading remaining notes.
3. **Adjust Reverse Proxy Timeouts**: If self-hosting Joplin Server or Nextcloud behind Nginx, increase `proxy_read_timeout` and `fastcgi_read_timeout` to `600s`.
4. **Snippet-Only Mode**: If a specific feed creates massive articles, run with `--no-full-text` to import lightweight RSS snippets only.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
