import json, os
from collections import Counter
from pathlib import Path

OUT=Path(os.environ.get('TASK_OUTPUT','/root/results/output.json'))
DATA=Path(os.environ.get('TASK_DATA','/root/data/portal.json'))

def doc(): return json.loads(OUT.read_text())
def tickets(o):
    for k in ('breached_tickets','tickets','breaches','results'):
        if isinstance(o.get(k),list): return o[k]
    return []
def val(r,*names):
    lower={str(k).lower().replace(' ','_'):v for k,v in r.items()}
    for n in names:
        if n in lower:return lower[n]
def source_expected():
    rows=json.loads(DATA.read_text())['tickets']
    return {r['ticket_id']:r for r in rows if r['status']=='open' and r['priority']=='urgent' and r['age_hours']>r['sla_hours']}

def test_artifact_is_usable():
    assert OUT.is_file(), 'requested output.json is missing'
    o=doc(); assert isinstance(o,dict), 'output must be a JSON object'
    assert tickets(o), 'no recognizable breached-ticket collection was found'
    assert isinstance(o.get('summary'),dict), 'a summary object is required for operational use'

def test_breach_selection():
    rows=tickets(doc()); ids=[str(val(r,'ticket_id','id')).upper() for r in rows]
    exp=set(source_expected())
    assert len(ids)==len(set(ids)), 'duplicate tickets inflate the handoff workload'
    assert set(ids)==exp, f'breach selection differs: missing={sorted(exp-set(ids))}, extra={sorted(set(ids)-exp)}'

def test_ticket_details():
    rows={str(val(r,'ticket_id','id')).upper():r for r in tickets(doc())}; exp=source_expected()
    assert set(rows)==set(exp), 'cannot validate details until the selected ticket set is correct'
    for tid,s in exp.items():
        r=rows[tid]
        for field in ('customer','region','status','priority','age_hours','sla_hours','subject','latest_note','tags'):
            assert val(r,field)==s[field], f'{tid} has incorrect or missing {field}'
        owner=val(r,'owner','assignee')
        assert owner==s['owner'] or (s['owner']=='' and owner in (None,'','unassigned','Unassigned')), f'{tid} owner meaning is wrong'
        over=val(r,'hours_over_sla','overdue_hours','breach_hours')
        assert over is not None and float(over)==s['age_hours']-s['sla_hours'], f'{tid} breach duration is wrong'

def test_summary_counts():
    o=doc(); s=o['summary']; exp=source_expected()
    count=val(s,'breach_count','count','total')
    assert int(count)==len(exp), 'summary total does not match eligible breaches'
    by=val(s,'counts_by_region','by_region','region_counts')
    assert isinstance(by,dict), 'regional counts are missing'
    assert {str(k):int(v) for k,v in by.items()}==dict(Counter(r['region'] for r in exp.values())), 'regional counts are inconsistent'
    unassigned=val(s,'unassigned_count','unassigned')
    assert int(unassigned)==sum(not r['owner'] for r in exp.values()), 'unassigned count is inconsistent'
