#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

TEXT_EXT = {'.py', '.toml', '.ini', '.cfg', '.md', '.yml', '.yaml', '.json'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('needle')
    ap.add_argument('--root', default='.')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rx = re.compile(re.escape(args.needle))
    hits = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT or '.git' in p.parts:
            continue
        try: lines = p.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError: continue
        for no, line in enumerate(lines, 1):
            if rx.search(line):
                hits.append({'path': p.relative_to(root).as_posix(), 'line': no, 'text': line.strip()[:240]})
    print(json.dumps({'needle': args.needle, 'hits': hits}, indent=2))

if __name__ == '__main__':
    main()
