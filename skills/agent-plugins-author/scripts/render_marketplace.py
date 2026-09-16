#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default='.'); ap.add_argument('--check',action='store_true'); args=ap.parse_args(); root=Path(args.root).resolve()
    p=json.loads((root/'plugin.json').read_text(encoding='utf-8'))
    obj={'name':p['name'],'owner':{'name':p.get('author',{}).get('name','Unknown')},'metadata':{'description':p['description'],'version':p['version']},'plugins':[{'name':p['name'],'description':p['description'],'version':p['version'],'source':'.','license':p.get('license','')}]}
    rendered=json.dumps(obj,indent=2,ensure_ascii=False)+'\n'
    targets=[root/'.github/plugin/marketplace.json',root/'.agents/plugins/marketplace.json']
    if args.check:
        bad=[str(t) for t in targets if not t.is_file() or t.read_text(encoding='utf-8')!=rendered]
        if bad: raise SystemExit('marketplace drift: '+', '.join(bad))
        print('Marketplace render check: PASS'); return
    for t in targets: t.parent.mkdir(parents=True,exist_ok=True); t.write_text(rendered,encoding='utf-8')
    print('Rendered marketplace surfaces')
if __name__=='__main__': main()
