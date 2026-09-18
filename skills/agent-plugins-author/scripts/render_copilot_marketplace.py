#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def render(root):
    p=json.loads((root/'plugin.json').read_text(encoding='utf-8'))
    author=p.get('author',{})
    entry={'name':p['name'],'description':p['description'],'version':p['version'],'source':'.','author':author,'strict':True,'category':'Productivity'}
    for field in ('homepage','repository','license','keywords'):
        if field in p: entry[field]=p[field]
    return {'name':p['name'],'owner':{'name':author.get('name','Unknown')},'metadata':{'description':'GitHub Copilot marketplace for '+p['name'],'version':p['version']},'plugins':[entry]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default='.'); ap.add_argument('--check',action='store_true'); args=ap.parse_args(); root=Path(args.root).resolve()
    target=root/'.github/plugin/marketplace.json'; rendered=json.dumps(render(root),indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf-8')!=rendered: raise SystemExit('Copilot marketplace drift: '+str(target))
        print('Copilot marketplace render check: PASS'); return
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(rendered,encoding='utf-8'); print('Rendered Copilot marketplace')
if __name__=='__main__': main()
