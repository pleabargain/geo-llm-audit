#!/usr/bin/env python3
"""AI visibility audit (GEO) starter tool.

Checks a website for signals AI engines (ChatGPT, Gemini, Claude, Perplexity)
use to understand, trust, cite, and recommend a business.

====================================================================
HOW TO RUN
====================================================================

Prerequisites
-------------
- Python 3.10+ (https://www.python.org/downloads/)
- `uv` (recommended) OR `pip` for dependency management
  Install uv:  https://docs.astral.sh/uv/getting-started/installation/
- A working internet connection (the tool fetches live URLs).

Install dependencies
--------------------
With uv (recommended, creates an isolated env automatically):
    uv add httpx beautifulsoup4

With pip:
    pip install httpx beautifulsoup4

Run
---
With uv:
    uv run 20261112T120000_ai_visibility_audit.py https://example.com

With python directly (after installing deps):
    python 20261112T120000_ai_visibility_audit.py https://example.com

Options
-------
    uv run 20261112T120000_ai_visibility_audit.py <url> [--output PATH] [--quiet]

        <url>       Website to audit (must include scheme, e.g. https://example.com)
        --output    Write the JSON report to a specific file (default: audit_<host>.json)
        --quiet     Print only the score and saved file path (no full JSON)
        --version   Print version and exit
        -h, --help  Show this help

Environment variables (optional)
--------------------------------
    OPENAI_API_KEY      Enables a live ChatGPT brand-mention test.
    ANTHROPIC_API_KEY   Enables a live Claude brand-mention test.

    Without these keys the audit still runs all on-site checks; the
    "ai_mentions" section will simply be empty.

Examples
--------
    # Basic audit
    uv run 20261112T120000_ai_visibility_audit.py https://example.com

    # Save to a custom file, quiet output
    uv run 20261112T120000_ai_visibility_audit.py https://example.com \
        --output reports/example.json --quiet

    # With AI mention tests enabled
    OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... \
        uv run 20261112T120000_ai_visibility_audit.py https://example.com

Output
------
A JSON report is printed to stdout and also saved to disk. It contains:
  - robots_txt : whether robots.txt exists and blocks AI crawlers
  - sitemap    : whether sitemap.xml exists
  - llms_txt   : whether llms.txt exists (AI-facing site summary)
  - homepage   : title, meta description, H1s, schema.org types, image alt
                 coverage, word count
  - ai_mentions: (optional) how ChatGPT/Claude describe your brand
  - score      : 0-100 heuristic GEO visibility score

Exit codes
----------
    0  success
    1  usage error (missing/invalid URL) or fatal failure

Notes
-----
- Only public, crawlable pages are checked. No authentication is performed.
- The score is a heuristic starter metric, not an official ranking signal.
- Be respectful: the tool sends a small number of requests with a clear
  User-Agent. Do not point it at sites you do not own without permission.
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

__version__ = "1.0.0"

UA = "Mozilla/5.0 (compatible; FlareFalcon-like-Audit/1.0)"


def fetch(url):
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
        return r
    except Exception:
        return None


def audit(url):
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL must include a scheme and host, e.g. https://example.com")
    base = f"{parsed.scheme}://{parsed.netloc}"
    report = {"url": url, "checks": {}}

    # 1. robots.txt
    r = fetch(base + "/robots.txt")
    report["checks"]["robots_txt"] = {
        "exists": r is not None and r.status_code == 200,
        "blocks_ai": bool(r and re.search(r"User-agent:\s*(GPTBot|ClaudeBot|PerplexityBot|Google-Extended)", r.text, re.I)),
        "content": (r.text[:500] if r and r.status_code == 200 else None),
    }

    # 2. sitemap
    r = fetch(base + "/sitemap.xml")
    report["checks"]["sitemap"] = {"exists": r is not None and r.status_code == 200}

    # 3. llms.txt
    r = fetch(base + "/llms.txt")
    report["checks"]["llms_txt"] = {
        "exists": r is not None and r.status_code == 200,
        "content": (r.text[:1000] if r and r.status_code == 200 else None),
    }

    # 4. homepage parse
    r = fetch(url)
    if r and r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title else None
        meta_desc = None
        md = soup.find("meta", attrs={"name": "description"})
        if md:
            meta_desc = md.get("content")
        # structured data
        schemas = []
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                schemas.append(json.loads(s.string))
            except Exception:
                schemas.append("INVALID")
        # headings
        h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
        # images alt
        imgs = soup.find_all("img")
        alt_missing = sum(1 for i in imgs if not i.get("alt"))
        report["checks"]["homepage"] = {
            "title": title,
            "meta_description": meta_desc,
            "h1": h1,
            "schema_types": [(s.get("@type") if isinstance(s, dict) else s) for s in schemas],
            "schema_count": len(schemas),
            "images_total": len(imgs),
            "images_missing_alt": alt_missing,
            "word_count": len(soup.get_text(" ").split()),
        }
    else:
        report["checks"]["homepage"] = {"error": "fetch failed"}

    # 5. AI mention test (optional)
    brand = urlparse(url).netloc.replace("www.", "")
    prompt = f"What is {brand}? In one sentence, what does it do and is it trustworthy? Cite sources."
    ai_results = {}
    if os.getenv("OPENAI_API_KEY"):
        try:
            rr = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            ai_results["openai"] = rr.json()["choices"][0]["message"]["content"]
        except Exception as e:
            ai_results["openai"] = f"error: {e}"
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            rr = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.getenv("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]},
                timeout=30,
            )
            ai_results["anthropic"] = rr.json()["content"][0]["text"]
        except Exception as e:
            ai_results["anthropic"] = f"error: {e}"
    report["checks"]["ai_mentions"] = ai_results

    # score (simple heuristic)
    score = 0
    c = report["checks"]
    if c["robots_txt"]["exists"] and not c["robots_txt"]["blocks_ai"]:
        score += 20
    if c["sitemap"]["exists"]:
        score += 10
    if c["llms_txt"]["exists"]:
        score += 15
    hp = c.get("homepage", {})
    if hp.get("title") and hp.get("meta_description"):
        score += 10
    if hp.get("schema_count", 0) > 0:
        score += 15
    if hp.get("h1"):
        score += 10
    if hp.get("images_total", 0) > 0 and hp.get("images_missing_alt", 0) == 0:
        score += 10
    if hp.get("word_count", 0) > 300:
        score += 10
    report["score"] = min(score, 100)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ai_visibility_audit",
        description="AI visibility (GEO) audit starter tool.",
        epilog="See module docstring for full usage and environment variables.",
    )
    parser.add_argument("url", help="Website to audit, e.g. https://example.com")
    parser.add_argument("--output", "-o", help="Path to write the JSON report (default: audit_<host>.json)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Print only score and saved file path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    try:
        rep = audit(args.url)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.output:
        out = args.output
    else:
        out = f"audit_{urlparse(args.url).netloc.replace('.', '_')}.json"

    # ensure parent dir exists
    parent = os.path.dirname(os.path.abspath(out))
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)

    if args.quiet:
        print(f"score: {rep['score']}/100")
        print(f"saved: {out}")
    else:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())