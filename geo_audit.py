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
    uv run geo_audit.py https://example.com

With python directly (after installing deps):
    python geo_audit.py https://example.com

Options
-------
    uv run geo_audit.py <url> [--output PATH] [--quiet]

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
    uv run geo_audit.py https://example.com

    # Save to a custom file, quiet output
    uv run geo_audit.py https://example.com \
        --output reports/example.json --quiet

    # With AI mention tests enabled
    OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... \
        uv run geo_audit.py https://example.com

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
import datetime
import html
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

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
        missing_alt_srcs = [ (i.get("src") or "") for i in imgs if not i.get("alt") ]
        # platform guess
        platform = "Unknown"
        gen = soup.find("meta", attrs={"name": "generator"})
        gen_content = (gen.get("content") if gen else "") or ""
        known = ["wordpress", "wix", "shopify", "squarespace", "webflow", "drupal", "joomla", "ghost", "hubspot"]
        if any(k in gen_content.lower() for k in known):
            platform = gen_content
        else:
            low = r.text.lower()
            if "wixstatic" in low or "wix.com" in low or "x-wix" in low:
                platform = "Wix"
            elif "wp-content" in low or "wordpress" in low:
                platform = "WordPress"
            elif "shopify" in low:
                platform = "Shopify"
            elif "squarespace" in low:
                platform = "Squarespace"
            elif "webflow" in low:
                platform = "Webflow"
            elif "drupal" in low:
                platform = "Drupal"
            elif "joomla" in low:
                platform = "Joomla"
            elif gen_content:
                platform = gen_content  # fallback to whatever generator says

        report["checks"]["homepage"] = {
            "title": title,
            "meta_description": meta_desc,
            "h1": h1,
            "schema_types": [(s.get("@type") if isinstance(s, dict) else s) for s in schemas],
            "schema_count": len(schemas),
            "images_total": len(imgs),
            "images_missing_alt": alt_missing,
            "images_missing_alt_list": missing_alt_srcs,
            "platform_guess": platform,
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


def build_html_report(report):
    """Build an HTML report string from an audit report dict."""
    url = report.get("url", "")
    host = urlparse(url).netloc or url
    score = report.get("score", 0)
    checks = report.get("checks", {})
    run_date = datetime.date.today().strftime("%Y-%b-%d")
    title = f"{host} — AI Visibility Audit — {run_date}"

    def esc(v):
        return html.escape(str(v)) if v is not None else ""

    def badge(val):
        color = "#2e7d32" if val else "#c62828"
        label = "Yes" if val else "No"
        return f'<span style="color:{color};font-weight:bold">{label}</span>'

    hp = checks.get("homepage", {})
    missing = hp.get('images_missing_alt_list', []) if isinstance(hp, dict) else []
    thumbs_html = ""
    if missing:
        imgs = "".join(f'<img src="{esc(s)}" style="width:120px;height:auto;margin:6px;border:1px solid #ccc;border-radius:6px" loading="lazy" />' for s in missing)
        thumbs_html = f"<h3>Missing-alt thumbnails</h3><div>{imgs}</div>"
    hp_rows = ""
    if "error" in hp:
        hp_rows = f"<tr><td colspan='2'>Error: {esc(hp['error'])}</td></tr>"
    else:
        hp_rows = f"""
        <tr><td>Title</td><td>{esc(hp.get('title'))}</td></tr>
        <tr><td>Meta description</td><td>{esc(hp.get('meta_description'))}</td></tr>
        <tr><td>H1</td><td>{esc(', '.join(hp.get('h1', [])))}</td></tr>
        <tr><td>Schema types</td><td>{esc(', '.join(str(s) for s in hp.get('schema_types', [])))}</td></tr>
        <tr><td>Schema count</td><td>{hp.get('schema_count', 0)}</td></tr>
        <tr><td>Images total</td><td>{hp.get('images_total', 0)}</td></tr>
        <tr><td>Images missing alt</td><td>{hp.get('images_missing_alt', 0)}</td></tr>
        <tr><td>Missing alt image srcs</td><td>{'<br>'.join(esc(s) for s in hp.get('images_missing_alt_list', [])) or '&mdash;'}</td></tr>
        <tr><td>Platform guess</td><td>{esc(hp.get('platform_guess', 'Unknown'))}</td></tr>
        <tr><td>Word count</td><td>{hp.get('word_count', 0)}</td></tr>
        """

    # ai mentions
    ai = checks.get("ai_mentions", {})
    ai_html = ""
    if ai:
        for k, v in ai.items():
            ai_html += f"<h4>{esc(k)}</h4><pre>{esc(v)}</pre>"
    else:
        ai_html = "<p><em>No AI providers configured (set OPENAI_API_KEY / ANTHROPIC_API_KEY).</em></p>"

    robots = checks.get("robots_txt", {})
    sitemap = checks.get("sitemap", {})
    llms = checks.get("llms_txt", {})
    hp = checks.get("homepage", {})

    score_color = "#2e7d32" if score >= 80 else ("#ef6c00" if score >= 50 else "#c62828")

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px; background: #f5f7fa; color: #1a1a1a; }}
  .container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  h1 {{ margin: 0 0 4px; font-size: 24px; }}
  .subtitle {{ color: #555; margin-bottom: 24px; }}
  .score {{ display: inline-block; font-size: 48px; font-weight: 800; color: {score_color}; margin: 8px 0 24px; }}
  h2 {{ border-bottom: 2px solid #eee; padding-bottom: 6px; margin-top: 28px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 16px; }}
  td, th {{ padding: 8px 10px; border: 1px solid #e6e6e6; text-align: left; vertical-align: top; }}
  th {{ background: #f0f2f5; }}
  pre {{ background: #f0f2f5; padding: 12px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap; }}
  .footer {{ margin-top: 32px; font-size: 12px; color: #888; }}
</style>
</head>
<body>
<div class="container">
  <h1>{esc(host)}</h1>
  <div class="subtitle">AI Visibility (GEO) Audit &mdash; {esc(run_date)}</div>
  <div>Source URL: <a href="{esc(url)}">{esc(url)}</a></div>
  <div class="score">{score}/100</div>

  <h2>robots.txt</h2>
  <table>
    <tr><td>Exists</td><td>{badge(robots.get('exists', False))}</td></tr>
    <tr><td>Blocks AI crawlers</td><td>{badge(robots.get('blocks_ai', False))}</td></tr>
  </table>
  {('<pre>' + esc(robots.get('content')) + '</pre>') if robots.get('content') else ''}

  <h2>sitemap.xml</h2>
  <table>
    <tr><td>Exists</td><td>{badge(sitemap.get('exists', False))}</td></tr>
  </table>

  <h2>llms.txt</h2>
  <table>
    <tr><td>Exists</td><td>{badge(llms.get('exists', False))}</td></tr>
  </table>
  {('<pre>' + esc(llms.get('content')) + '</pre>') if llms.get('content') else ''}

  <h2>Homepage</h2>
  <table>
    {hp_rows}
  </table>
  {thumbs_html}

  <h2>AI mentions</h2>
  {ai_html}

  <div class="footer">Generated by geo_audit.py &mdash; heuristic starter metric, not an official ranking signal.</div>
</div>
</body>
</html>
"""
    return doc


UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Visibility (GEO) Audit</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --accent:#38bdf8; --good:#22c55e; --bad:#ef4444; --warn:#f59e0b; --text:#e2e8f0; --muted:#94a3b8; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); }
  .wrap { max-width: 1000px; margin: 0 auto; padding: 24px; }
  header { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
  h1 { margin:0; font-size:22px; }
  .card { background: var(--card); border-radius:12px; padding:20px; margin-bottom:16px; box-shadow:0 2px 12px rgba(0,0,0,.3); }
  form { display:flex; gap:10px; flex-wrap:wrap; }
  input[type=text] { flex:1; min-width:200px; padding:10px 12px; border-radius:8px; border:1px solid #334155; background:#0f172a; color:var(--text); font-size:15px; }
  button { padding:10px 18px; border:none; border-radius:8px; background:var(--accent); color:#0f172a; font-weight:700; cursor:pointer; font-size:15px; }
  button:disabled { opacity:.6; cursor:not-allowed; }
  .score { font-size:56px; font-weight:800; margin:8px 0; }
  .good { color: var(--good); } .bad { color: var(--bad); } .warn { color: var(--warn); }
  table { width:100%; border-collapse:collapse; }
  td, th { padding:8px 10px; border-bottom:1px solid #334155; text-align:left; vertical-align:top; }
  th { color: var(--muted); font-weight:600; width:220px; }
  pre { background:#0f172a; padding:12px; border-radius:8px; overflow-x:auto; white-space:pre-wrap; font-size:13px; }
  .thumbs img { width:110px; height:auto; margin:6px; border:1px solid #334155; border-radius:6px; }
  .muted { color: var(--muted); font-size:13px; }
  .spinner { display:inline-block; width:18px; height:18px; border:3px solid #334155; border-top-color:var(--accent); border-radius:50%; animation:spin 1s linear infinite; vertical-align:middle; margin-right:8px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hidden { display:none; }
  .section { margin-top:12px; }
  .badge { display:inline-block; padding:2px 8px; border-radius:6px; font-weight:700; font-size:13px; }
  .badge.yes { background:rgba(34,197,94,.15); color:var(--good); }
  .badge.no { background:rgba(239,68,68,.15); color:var(--bad); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>AI Visibility (GEO) Audit</h1>
    <span class="muted">local tool</span>
  </header>

  <div class="card">
    <form id="auditForm">
      <input type="text" id="urlInput" placeholder="https://example.com" required />
      <button type="submit" id="runBtn">Run audit</button>
    </form>
    <div id="status" class="muted" style="margin-top:10px;"></div>
  </div>

  <div id="results" class="hidden"></div>
</div>

<script>
const form = document.getElementById('auditForm');
const input = document.getElementById('urlInput');
const btn = document.getElementById('runBtn');
const status = document.getElementById('status');
const results = document.getElementById('results');

function esc(s){ return (s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function badge(v){ return v ? '<span class="badge yes">Yes</span>' : '<span class="badge no">No</span>'; }

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = input.value.trim();
  if(!url) return;
  btn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> Auditing ' + esc(url) + '...';
  results.classList.add('hidden');
  try {
    const r = await fetch('/api/audit', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
    const data = await r.json();
    if(data.error){ status.textContent = 'Error: ' + data.error; return; }
    render(data);
    status.textContent = 'Done. Score: ' + data.score + '/100';
  } catch(err) {
    status.textContent = 'Error: ' + err;
  } finally {
    btn.disabled = false;
  }
});

function render(d){
  const c = d.checks || {};
  const hp = c.homepage || {};
  const scoreColor = d.score>=80 ? 'good' : (d.score>=50 ? 'warn' : 'bad');
  let html = '';
  html += `<div class="card"><div class="score ${scoreColor}">${d.score}/100</div><div class="muted">${esc(d.url)}</div></div>`;

  // robots
  const rob = c.robots_txt || {};
  html += `<div class="card"><h2>robots.txt</h2><table>
    <tr><th>Exists</th><td>${badge(rob.exists)}</td></tr>
    <tr><th>Blocks AI crawlers</th><td>${badge(rob.blocks_ai)}</td></tr>
  </table>${rob.content ? '<pre>'+esc(rob.content)+'</pre>' : ''}</div>`;

  // sitemap
  const sm = c.sitemap || {};
  html += `<div class="card"><h2>sitemap.xml</h2><table><tr><th>Exists</th><td>${badge(sm.exists)}</td></tr></table></div>`;

  // llms
  const ll = c.llms_txt || {};
  html += `<div class="card"><h2>llms.txt</h2><table><tr><th>Exists</th><td>${badge(ll.exists)}</td></tr></table>${ll.content ? '<pre>'+esc(ll.content)+'</pre>' : ''}</div>`;

  // homepage
  if(hp.error){
    html += `<div class="card"><h2>Homepage</h2><p>${esc(hp.error)}</p></div>`;
  } else {
    html += `<div class="card"><h2>Homepage</h2><table>
      <tr><th>Title</th><td>${esc(hp.title)}</td></tr>
      <tr><th>Meta description</th><td>${esc(hp.meta_description)}</td></tr>
      <tr><th>H1</th><td>${esc((hp.h1||[]).join(', '))}</td></tr>
      <tr><th>Schema types</th><td>${esc((hp.schema_types||[]).join(', '))}</td></tr>
      <tr><th>Schema count</th><td>${hp.schema_count||0}</td></tr>
      <tr><th>Images total</th><td>${hp.images_total||0}</td></tr>
      <tr><th>Images missing alt</th><td>${hp.images_missing_alt||0}</td></tr>
      <tr><th>Platform guess</th><td>${esc(hp.platform_guess)}</td></tr>
      <tr><th>Word count</th><td>${hp.word_count||0}</td></tr>
    </table>`;
    const missing = hp.images_missing_alt_list || [];
    if(missing.length){
      html += `<h3>Missing-alt thumbnails</h3><div class="thumbs">` + missing.map(s=>`<img src="${esc(s)}" loading="lazy" />`).join('') + `</div>`;
      html += `<details class="section"><summary>Missing alt src list</summary><pre>${esc(missing.join('\n'))}</pre></details>`;
    }
    html += `</div>`;
  }

  // ai mentions
  const ai = c.ai_mentions || {};
  let aiHtml = '';
  if(Object.keys(ai).length){
    for(const k in ai){ aiHtml += `<h4>${esc(k)}</h4><pre>${esc(ai[k])}</pre>`; }
  } else {
    aiHtml = '<p class="muted">No AI providers configured.</p>';
  }
  html += `<div class="card"><h2>AI mentions</h2>${aiHtml}</div>`;

  results.innerHTML = html;
  results.classList.remove('hidden');
}
</script>
</body>
</html>
"""


class AuditHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = UI_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/api/audit":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            url = data.get("url", "").strip()
        except Exception:
            url = ""
        if not url:
            self._json({"error": "missing url"}, 400)
            return
        try:
            rep = audit(url)
        except Exception as e:
            self._json({"error": str(e)}, 500)
            return
        # save reports
        host = urlparse(url).netloc.replace(".", "_")
        out = f"audit_{host}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        html_path = f"audit_{host}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(build_html_report(rep))
        rep["_saved_json"] = out
        rep["_saved_html"] = html_path
        self._json(rep, 200)

    def _json(self, obj, status):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(port=8765, open_browser=True):
    httpd = HTTPServer(("127.0.0.1", port), AuditHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"AI Visibility Audit web UI: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="geo_audit",
        description="AI visibility (GEO) audit tool with web UI.",
        epilog="Run without --cli to start the local web UI.",
    )
    parser.add_argument("url", nargs="?", help="Website to audit (CLI mode)")
    parser.add_argument("--cli", action="store_true", help="Run in command-line mode (no web UI)")
    parser.add_argument("--port", type=int, default=8765, help="Web UI port (default 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--output", "-o", help="Path to write the JSON report (CLI mode)")
    parser.add_argument("--html", help="Path to write the HTML report (CLI mode)")
    parser.add_argument("--no-html", action="store_true", help="Skip HTML report (CLI mode)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Print only score and saved paths (CLI mode)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.cli or args.url and not args.cli and False:
        pass

    # Web UI mode unless --cli or a URL given without --cli? Default web UI.
    if not args.cli and not args.url:
        serve(port=args.port, open_browser=not args.no_browser)
        return 0

    # If a URL is given without --cli, still allow quick CLI? Treat as CLI for convenience.
    if args.url and not args.cli:
        # start web UI but prefill not supported; run CLI instead for a single URL
        args.cli = True

    if args.cli:
        if not args.url:
            print("error: URL required in --cli mode", file=sys.stderr)
            return 1
        try:
            rep = audit(args.url)
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

        if args.output:
            out = args.output
        else:
            out = f"audit_{urlparse(args.url).netloc.replace('.', '_')}.json"

        parent = os.path.dirname(os.path.abspath(out))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

        with open(out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)

        html_path = None
        if not args.no_html:
            if args.html:
                html_path = args.html
            else:
                html_path = os.path.splitext(out)[0] + ".html"
            html_parent = os.path.dirname(os.path.abspath(html_path))
            if html_parent and not os.path.exists(html_parent):
                os.makedirs(html_parent, exist_ok=True)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(build_html_report(rep))

        if args.quiet:
            print(f"score: {rep['score']}/100")
            print(f"saved: {out}")
            if html_path:
                print(f"html:  {html_path}")
        else:
            print(json.dumps(rep, indent=2, ensure_ascii=False))
            print(f"\nSaved {out}")
            if html_path:
                print(f"HTML report saved {html_path}")
        return 0

    serve(port=args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
