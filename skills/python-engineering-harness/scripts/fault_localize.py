#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

PAT = re.compile(r'(?P<path>[A-Za-z0-9_./\\-]+\.py):(?P<line>\d+)')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    args = ap.parse_args()
    text = Path(args.log).read_text(encoding='utf-8', errors='replace')
    seen, frames = set(), []
    for m in PAT.finditer(text):
        key = (m.group('path'), int(m.group('line')))
        if key not in seen:
            seen.add(key); frames.append({'path': key[0], 'line': key[1]})
    print(json.dumps({'frames': frames}, indent=2))

if __name__ == '__main__':
    main()
