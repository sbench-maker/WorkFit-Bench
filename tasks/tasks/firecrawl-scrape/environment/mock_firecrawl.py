#!/usr/bin/env python3
import argparse, html, json, re, sys
from pathlib import Path

def clean(raw, main):
    if main:
        m = re.search(r"<main>(.*?)</main>", raw, re.S|re.I)
        raw = m.group(1) if m else raw
    raw = re.sub(r"<(nav|footer|aside)[^>]*>.*?</\1>", "", raw, flags=re.S|re.I)
    raw = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n\n", raw, flags=re.S|re.I)
    raw = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n\n", raw, flags=re.S|re.I)
    raw = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", raw, flags=re.S|re.I)
    raw = re.sub(r"<a[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", r"[\2](\1)\n", raw, flags=re.S|re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(raw)).strip()+"\n"

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd"); s=sub.add_parser("scrape")
    s.add_argument("urls", nargs="+"); s.add_argument("-o","--output"); s.add_argument("-f","--format",default="markdown"); s.add_argument("--only-main-content",action="store_true"); s.add_argument("--wait-for",type=int,default=0); s.add_argument("--redact-pii",action="store_true")
    a=ap.parse_args();
    if a.cmd != "scrape": return 2
    data_dir=Path(__import__('os').environ.get('FIRECRAWL_DATA_DIR','/root/data'))
    pages={p["url"]:p for p in json.loads((data_dir/"mock_pages.json").read_text())}
    results=[]
    for url in a.urls:
        if url not in pages: print(f"unknown fixture URL: {url}",file=sys.stderr); return 3
        p=pages[url]; raw=p["rendered_html"] if a.wait_for>=p["render_delay_ms"] else p["static_html"]
        md=clean(raw,a.only_main_content)
        if a.redact_pii:
            md=re.sub(r"[\w.+-]+@[\w.-]+", "[REDACTED_EMAIL]", md); md=re.sub(r"\+1 555 \d{3} \d{4}","[REDACTED_PHONE]",md)
        results.append({"url":url,"title":p["title"],"markdown":md,"links":p["links"]})
    formats=[x.strip() for x in a.format.split(",")]
    payload=results[0]["markdown"] if len(results)==1 and formats==["markdown"] else (results[0] if len(results)==1 else results)
    if formats==["links"]: payload=results[0]["links"] if len(results)==1 else [{"url":r["url"],"links":r["links"]} for r in results]
    out=json.dumps(payload,indent=2)+"\n" if not isinstance(payload,str) else payload
    if a.output: Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(out)
    else: print(out,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
