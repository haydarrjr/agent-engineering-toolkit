#!/usr/bin/env python3
import argparse, re, sys
from pathlib import Path

FM = re.compile(r'^---\n(.*?)\n---\n', re.S)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default='.'); args=ap.parse_args(); root=Path(args.root).resolve()
    errors=[]
    for p in sorted((root/'skills').glob('*/SKILL.md')):
        text=p.read_text(encoding='utf-8'); m=FM.match(text)
        if not m: errors.append(f'{p}: invalid frontmatter'); continue
        fm=m.group(1)
        nm=re.search(r'^name:\s*([^\n]+)$',fm,re.M); ds=re.search(r'^description:\s*(.+)$',fm,re.M)
        if not nm or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', nm.group(1).strip()): errors.append(f'{p}: invalid lowercase kebab-case name')
        if not ds or len(ds.group(1).strip('"\'')) < 20: errors.append(f'{p}: description too weak')
        if len(text.splitlines()) > 500: errors.append(f'{p}: entrypoint exceeds 500 lines')
        for target in re.findall(r'\]\((references/[^)]+)\)', text):
            if not (p.parent/target).is_file(): errors.append(f'{p}: broken reference {target}')
    print('Skill design validation:', 'FAIL' if errors else 'PASS')
    for e in errors: print('ERROR:',e)
    raise SystemExit(1 if errors else 0)
if __name__=='__main__': main()
