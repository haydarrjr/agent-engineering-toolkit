#!/usr/bin/env python3
import argparse, json
from pathlib import Path

def render(root):
    p=json.loads((root/'plugin.json').read_text(encoding='utf-8'))
    c=json.loads((root/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    repo=p['repository'].removesuffix('.git')
    return {
        'name':p['name'],
        'interface':{'displayName':c.get('interface',{}).get('displayName',p['name'])},
        'plugins':[{'name':p['name'],'source':{'source':'url','url':repo+'.git','ref':'main'},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':c.get('interface',{}).get('category','Productivity')}],
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default='.'); ap.add_argument('--check',action='store_true'); args=ap.parse_args(); root=Path(args.root).resolve()
    target=root/'.agents/plugins/marketplace.json'; rendered=json.dumps(render(root),indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf-8')!=rendered: raise SystemExit('Codex marketplace drift: '+str(target))
        print('Codex marketplace render check: PASS'); return
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(rendered,encoding='utf-8'); print('Rendered Codex marketplace')
if __name__=='__main__': main()
