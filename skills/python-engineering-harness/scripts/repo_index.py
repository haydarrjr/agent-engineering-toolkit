#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

SKIP = {'.git', '.venv', 'venv', '__pycache__', 'dist', 'build'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    rows = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or any(part in SKIP for part in p.relative_to(root).parts):
            continue
        data = p.read_bytes()
        rows.append({'path': p.relative_to(root).as_posix(), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    print(json.dumps({'root': str(root), 'files': rows}, indent=2))

if __name__ == '__main__':
    main()
