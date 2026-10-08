import json, os, re
from pathlib import Path

DATA=Path(os.environ.get('TASK_DATA_DIR','/root/data')); OUT=Path(os.environ.get('TASK_RESULTS_DIR','/root/results'))/'snapshot'

def load():
    p=OUT/'manifest.json'; assert p.is_file(), 'snapshot manifest is missing'
    obj=json.loads(p.read_text()); rows=obj if isinstance(obj,list) else obj.get('pages') or obj.get('entries') or obj.get('items')
    assert isinstance(rows,list), 'manifest must expose a list of page entries'
    norm=[]
    for x in rows:
        url=x.get('url') or x.get('source_url'); fn=x.get('file') or x.get('path') or x.get('markdown_file'); links=x.get('links') or x.get('extracted_links') or []
        norm.append((url,fn,links))
    return norm

def test_artifact_usable():
    rows=load(); assert rows
    for url,fn,_ in rows:
        assert isinstance(url,str) and isinstance(fn,str)
        p=OUT/fn; assert p.resolve().is_relative_to(OUT.resolve()) and p.is_file() and p.stat().st_size>100

def test_target_coverage():
    rows=load(); expected=DATA.joinpath('targets.txt').read_text().splitlines(); urls=[r[0] for r in rows]
    assert len(urls)==len(set(urls))==len(expected) and set(urls)==set(expected)
    assert len({r[1] for r in rows})==len(expected)

def test_rendered_main_content():
    pages={p['url']:p for p in json.loads(DATA.joinpath('mock_pages.json').read_text())}
    for url,fn,_ in load():
        text=(OUT/fn).read_text()
        assert pages[url]['title'] in text and f'NS-{list(pages).index(url)+1:02d}-17' in text
        assert 'Loading...' not in text and 'Pricing Sign in' not in text and 'Copyright Careers Status' not in text

def test_links_and_redaction():
    pages={p['url']:p for p in json.loads(DATA.joinpath('mock_pages.json').read_text())}
    all_text=''
    for url,fn,links in load():
        assert set(links)==set(pages[url]['links'])
        all_text+=(OUT/fn).read_text()+' '+json.dumps(links)
    assert 'mira.vale@' not in all_text.lower() and '+1 555 010 2040' not in all_text
