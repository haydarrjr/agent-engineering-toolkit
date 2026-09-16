#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

REQ = {'name','version','description'}

def validate(root: Path):
    errors=[]; warnings=[]
    manifest = root/'plugin.json'
    if not manifest.is_file(): return ['missing plugin.json'], warnings
    try: data=json.loads(manifest.read_text(encoding='utf-8'))
    except Exception as e: return [f'invalid plugin.json: {e}'], warnings
    miss=REQ-set(data)
    if miss: errors.append('missing manifest fields: '+', '.join(sorted(miss)))
    if data.get('$schema') != 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json': warnings.append('manifest does not declare Agent Plugins 1.0 schema')
    skills=root/'skills'
    if not skills.is_dir(): errors.append('missing skills directory')
    else:
        for d in sorted(p for p in skills.iterdir() if p.is_dir()):
            if not (d/'SKILL.md').is_file(): errors.append(f'{d.name}: missing SKILL.md')
            if not (d/'agents'/'openai.yaml').is_file(): warnings.append(f'{d.name}: missing agents/openai.yaml')
    return errors,warnings

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root', nargs='?', default='.'); ap.add_argument('--json', action='store_true'); args=ap.parse_args()
    root=Path(args.root).resolve(); errors,warnings=validate(root)
    result={'status':'FAIL' if errors else 'PASS','root':str(root),'errors':errors,'warnings':warnings,'evidence_boundary':'source-only'}
    if args.json: print(json.dumps(result,indent=2))
    else:
        print(f"Agent Plugin validation: {result['status']}")
        for x in errors: print('ERROR:',x)
        for x in warnings: print('WARN:',x)
    raise SystemExit(1 if errors else 0)
if __name__=='__main__': main()
