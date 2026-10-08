#!/usr/bin/env python3
import argparse, json, os, sys
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

def canon(u):
    p=urlsplit(u); return urlunsplit((p.scheme,p.netloc,p.path.rstrip('/') or '/', '', ''))
def vals(items):
    out=[]
    for x in items or []: out += [y.strip() for y in x.split(',') if y.strip()]
    return out
def main():
    ap=argparse.ArgumentParser(prog='firecrawl'); sub=ap.add_subparsers(dest='cmd',required=True)
    c=sub.add_parser('crawl'); c.add_argument('url'); c.add_argument('--wait',action='store_true'); c.add_argument('--progress',action='store_true'); c.add_argument('--limit',type=int,default=10000); c.add_argument('--max-depth',type=int,default=10); c.add_argument('--include-paths',action='append'); c.add_argument('--exclude-paths',action='append'); c.add_argument('--delay'); c.add_argument('--max-concurrency'); c.add_argument('--pretty',action='store_true'); c.add_argument('-o','--output')
    a=ap.parse_args()
    if not a.wait:
        print(json.dumps({'id':'offline-job-001','status':'pending'})); return 0
    snap_path=Path(os.environ.get('FIRECRAWL_SNAPSHOT','/root/data/site_snapshot.json'))
    snap=json.loads(snap_path.read_text()); by={canon(x['url']):x for x in snap['pages']}
    start=canon(a.url); inc=vals(a.include_paths); exc=vals(a.exclude_paths)
    q=deque([(start,0)]); seen=set(); data=[]
    while q and len(data)<a.limit:
        u,d=q.popleft(); u=canon(u)
        if u in seen or u not in by or d>a.max_depth: continue
        seen.add(u); page=by[u]; path=urlsplit(u).path
        included=not inc or any(path.startswith(x) for x in inc)
        excluded=any(path.startswith(x) for x in exc)
        if included and not excluded:
            data.append({k:page[k] for k in ('url','title','markdown')} | {'depth':d})
        if not excluded:
            for link in page['links']: q.append((link,d+1))
    obj={'success':True,'status':'completed','startUrl':start,'total':len(data),'data':data}
    s=json.dumps(obj,indent=2 if a.pretty else None)+"\n"
    if a.output: Path(a.output).write_text(s)
    else: sys.stdout.write(s)
    return 0
if __name__=='__main__': raise SystemExit(main())
