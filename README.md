# AI Visibility Audit (GEO) — `geo_audit.py`

A Python tool that audits a website for the signals AI search engines
(ChatGPT, Gemini, Claude, Perplexity) use to **understand, trust, cite, and
recommend** a business. It produces a 0–100 heuristic "GEO visibility" score
plus a detailed JSON and HTML report.

Runs as a **local web app** (pretty UI) by default, or in CLI mode.

## Requirements

- Python 3.10+
- `httpx` and `beautifulsoup4` (install: `pip install httpx beautifulsoup4` or `uv add httpx beautifulsoup4`)
- Internet connection (fetches live URLs)

## Run (Web UI)

```bash
python geo_audit.py
```

Opens http://127.0.0.1:8765/ in your browser. Enter a URL, click "Run audit",
get a prettier report with score, checks, platform guess, and missing-alt
thumbnails.

Options:
```
python geo_audit.py [--port 8765] [--no-browser]
```

## Run (CLI)

```bash
python geo_audit.py --cli https://example.com
python geo_audit.py --cli https://example.com --quiet
```

CLI options:
```
--cli URL          Run in command-line mode
--output, -o PATH  JSON report path (default audit_<host>.json)
--html PATH        HTML report path (default audit_<host>.html)
--no-html          Skip HTML report
--quiet, -q        Print only score and saved paths
--version          Print version
```

## What it checks

| Check | What it looks for |
|---|---|
| `robots.txt` | Exists? Blocks AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)? |
| `sitemap.xml` | Exists? |
| `llms.txt` | Exists? (AI-facing site summary) |
| Homepage | Title, meta description, H1s, schema.org (JSON-LD) types, image alt coverage, word count, platform guess |
| AI mentions (optional) | How ChatGPT / Claude describe your brand (requires API keys) |

## Environment variables (optional)

| Variable | Effect |
|---|---|
| `OPENAI_API_KEY` | Enables a live ChatGPT brand-mention test |
| `ANTHROPIC_API_KEY` | Enables a live Claude brand-mention test |

## Output

JSON and HTML reports saved as `audit_<host>.json` / `audit_<host>.html`
(gitignored). HTML title includes site name and run date (`YYYY-MMM-DD`).

## Notes

- Only public, crawlable pages are checked. No authentication is performed.
- The score is a heuristic starter metric, not an official ranking signal.
- Be respectful: small number of requests with a clear User-Agent. Don't audit
  sites you don't own without permission.

## License

MIT
path">
C:\Users\denni\OneDrive\Documents\02-AI-Automation\site-visiblity-to-AI\README.md