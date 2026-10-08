import json, os
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

OUT=Path(os.environ.get('TASK_OUTPUT','/root/results/output.json')); SNAP=Path(os.environ.get('TASK_SNAPSHOT','/root/data/site_snapshot.json'))
def canon(u):
    p=urlsplit(str(u)); return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/') or '/','',''))
def load_output(): return json.loads(OUT.read_text(encoding='utf-8'))
def pages_from(obj):
    if isinstance(obj,list): return obj
    for k in ('data','pages','results','documents','items'):
        if isinstance(obj.get(k),list): return obj[k]
    raise AssertionError('crawl JSON has no page collection')
def field(row,*names):
    for n in names:
        if n in row:return row[n]
    meta=row.get('metadata',{}) if isinstance(row.get('metadata'),dict) else {}
    for n in names:
        if n in meta:return meta[n]
    return None
def expected():
    s=json.loads(SNAP.read_text()); by={canon(x['url']):x for x in s['pages']}; start=canon(s['base_url']+'/docs/releases')
    q=deque([(start,0)]); seen=set(); out={}
    while q:
        u,d=q.popleft(); u=canon(u)
        if u in seen or u not in by or d>5:continue
        seen.add(u); p=by[u]; path=urlsplit(u).path
        if path.startswith('/docs/releases/drafts') or path.startswith('/docs/releases/legacy'):continue
        if path.startswith('/docs/releases') and len(out)<80:out[u]=(p,d)
        for x in p['links']:q.append((x,d+1))
    return out
def normalized():
    obj=load_output(); rows=pages_from(obj); out={}
    for r in rows:
        assert isinstance(r,dict),'every extracted page must be an object'
        u=field(r,'url','sourceURL','source_url'); assert u,'every extracted page needs its source URL'
        out.setdefault(canon(u),[]).append(r)
    return obj,rows,out

def test_artifact_usability():
    assert OUT.is_file() and OUT.stat().st_size>20
    obj,rows,_=normalized(); assert rows
    if isinstance(obj,dict):
        assert obj.get('success',True) is not False
        assert str(obj.get('status','completed')).lower() in ('completed','complete','done','success','succeeded')

def test_scope_coverage():
    _,_,actual=normalized(); exp=expected()
    assert set(actual)==set(exp),f'missing={sorted(set(exp)-set(actual))[:6]}, unexpected={sorted(set(actual)-set(exp))[:6]}'

def test_content_fidelity():
    _,_,actual=normalized(); exp=expected(); problems=[]
    for u,(src,_) in exp.items():
        if u not in actual: continue
        r=actual[u][0]; title=field(r,'title','name'); body=field(r,'markdown','content','text')
        if title!=src['title'] or body!=src['markdown']:problems.append(u)
    assert not problems,f'incomplete or incorrect extracted content for {problems[:6]}'

def test_crawl_consistency():
    obj,rows,actual=normalized(); exp=expected()
    assert len(rows)==len(actual),'canonical URLs must not be duplicated (query strings do not create new pages)'
    assert all(not urlsplit(u).path.startswith(('/docs/releases/drafts','/docs/releases/legacy')) for u in actual)
    bad=[]
    for u,rs in actual.items():
        d=field(rs[0],'depth','crawlDepth','crawl_depth')
        if d is None or int(d)!=exp[u][1] or int(d)>5:bad.append(u)
    assert not bad,f'incorrect or missing crawl depth for {bad[:6]}'
    if isinstance(obj,dict) and any(k in obj for k in ('total','count','pageCount')):
        total=next(obj[k] for k in ('total','count','pageCount') if k in obj); assert int(total)==len(rows)
