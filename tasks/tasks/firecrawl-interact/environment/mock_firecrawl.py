#!/usr/bin/env python3
import argparse, json, os, re, sys
from pathlib import Path

STATE = Path("/tmp/firecrawl_interact_state.json")
DATA = Path(os.environ.get("FIRECRAWL_MOCK_DATA", "/root/data/portal.json"))

def load_data(): return json.loads(DATA.read_text())
def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"scraped": False, "filters": {}, "page": 1, "open": None}
def save(s): STATE.write_text(json.dumps(s))
def filtered(d, s):
    rows=d["tickets"]
    for k,v in s["filters"].items(): rows=[r for r in rows if str(r.get(k,"")).lower()==v]
    return rows
def main():
    if len(sys.argv)<2: sys.exit("usage: firecrawl scrape|interact")
    d=load_data(); action=sys.argv[1]; s=load_state()
    if action=="scrape":
        if len(sys.argv)<3 or sys.argv[2] != "mock://support-console": sys.exit("offline mock supports mock://support-console")
        s={"scraped":True,"filters":{},"page":1,"open":None}; save(s)
        print(json.dumps({"scrape_id":"scrape-support-001","title":d["portal"],"visible":"queue totals only","total":len(d["tickets"])})); return
    if action!="interact" or not s.get("scraped"): sys.exit("scrape the endpoint first")
    if len(sys.argv)>2 and sys.argv[2]=="stop":
        STATE.unlink(missing_ok=True); print('{"stopped":true}'); return
    ap=argparse.ArgumentParser(); ap.add_argument("--prompt"); ap.add_argument("--code"); ap.add_argument("--language"); ap.add_argument("--scrape-id"); ap.add_argument("-o","--output")
    a=ap.parse_args(sys.argv[2:]); q=(a.prompt or a.code or "").lower()
    for k in ("status","priority","region"):
        m=re.search(rf"(?:set|filter)(?: the)? {k}(?: to|=) ([a-z]+)",q)
        if m: s["filters"][k]=m.group(1); s["page"]=1; s["open"]=None
    if "clear filter" in q: s["filters"]={}; s["page"]=1; s["open"]=None
    if "next page" in q: s["page"]+=1; s["open"]=None
    m=re.search(r"(?:open|details? for) (t-\d+)",q)
    if m: s["open"]=m.group(1).upper()
    rows=filtered(d,s); size=d["page_size"]; pages=max(1,(len(rows)+size-1)//size); s["page"]=min(s["page"],pages)
    if s.get("open"):
        hit=next((r for r in rows if r["ticket_id"]==s["open"]),None); result={"drawer":hit}
    else:
        start=(s["page"]-1)*size
        result={"filters":s["filters"],"page":s["page"],"pages":pages,"matching":len(rows),"visible":[{k:r[k] for k in ("ticket_id","customer","status","priority")} for r in rows[start:start+size]]}
    save(s); out=json.dumps(result,indent=2)
    if a.output: Path(a.output).write_text(out+"\n")
    print(out)
if __name__=="__main__": main()
