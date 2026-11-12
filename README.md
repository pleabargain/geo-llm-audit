# AI Visibility Audit (GEO) — `geo_audit.py`

Audits a website for the signals AI search engines (ChatGPT, Gemini, Claude,
Perplexity) use to **understand, trust, cite, and recommend** a business.
Produces a 0–100 heuristic "GEO visibility" score plus JSON and HTML reports,
with actionable recommendations.

## Features

- Local **web UI** (vanilla JS/HTML) by default — pretty interface, no build step.
- **CLI mode** for scripting/CI.
- Checks: robots.txt, sitemap.xml, llms.txt, homepage metadata, schema.org,
  image alt coverage, word count, platform guess.
- Optional live AI brand-mention tests (OpenAI / Anthropic).
- **Missing-alt image thumbnails** and a **platform guess** in the report.
- **Recommendations checklist** to improve the score.
- **Download images** to a local `images/` folder next to the report.
- Unit + regression tests (`tests/`).

## Requirements

- Python 3.10+
- `httpx` and `beautifulsoup4` (`pip install httpx beautifulsoup4` or `uv add httpx beautifulsoup4`)
- Internet connection (fetches live URLs)

## Run (Web UI)

```bash
python geo_audit.py
```

Opens http://127.0.0.1:8765/. Enter a URL, click "Run audit", get the score,
full report, and recommendations. Check "Save report & images locally" to also
download images.

Options: `--port 8765`, `--no-browser`.

## Run (CLI)

```bash
python geo_audit.py --cli https://example.com
python geo_audit.py --cli example.com --quiet          # assumes https://
python geo_audit.py --cli https://example.com --download-images
```

CLI options:

```
--cli URL            Run in command-line mode
--output, -o PATH    JSON report path (default audit_<host>.json)
--html PATH          HTML report path (default audit_<host>.html)
--no-html            Skip HTML report
--download-images    Download images to a local images/ folder
--quiet, -q          Print only score and saved paths
--version            Print version
```

## What it checks

| Check | What it looks for |
|---|---|
| `robots.txt` | Exists? Blocks AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)? |
| `sitemap.xml` | Exists? |
| `llms.txt` | Exists? (AI-facing site summary) |
| Homepage | Title, meta description, H1s, schema.org (JSON-LD) types, image alt coverage, word count, platform guess |
| AI mentions (optional) | How ChatGPT / Claude describe your brand |

## Environment variables (optional)

| Variable | Effect |
|---|---|
| `OPENAI_API_KEY` | Enables a live ChatGPT brand-mention test |
| `ANTHROPIC_API_KEY` | Enables a live Claude brand-mention test |

## Output

JSON and HTML reports saved as `audit_<host>.json` / `audit_<host>.html`
(gitignored). HTML title includes site name and run date (`YYYY-MMM-DD`).
With `--download-images`, images are saved to `images/` next to the report.

## Tests

```bash
python -m unittest tests.test_geo_audit -v
```

## Notes

- Only public, crawlable pages are checked. No authentication is performed.
- The score is a heuristic starter metric, not an official ranking signal.
- Be respectful: small number of requests with a clear User-Agent. Don't audit
  sites you don't own without permission.

## Source

https://github.com/pleabargain/geo-llm-audit