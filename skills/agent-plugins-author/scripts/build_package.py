#!/usr/bin/env python3
import argparse, hashlib, zipfile
from pathlib import Path
SKIP={'.git','dist','build','__pycache__','.venv'}

def files(root):
    for p in sorted(root.rglob('*')):
        if p.is_file() and not any(part in SKIP for part in p.relative_to(root).parts): yield p

def build(root,out):
    epoch=(2026,9,17,0,0,0)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files(root):
            rel=p.relative_to(root).as_posix(); info=zipfile.ZipInfo(rel,epoch); info.external_attr=0o644<<16
            z.writestr(info,p.read_bytes())
    return hashlib.sha256(out.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default='.'); ap.add_argument('--out',default='dist/agent-engineering-toolkit.zip'); args=ap.parse_args()
    root=Path(args.root).resolve(); out=(root/args.out).resolve(); out.parent.mkdir(parents=True,exist_ok=True); print(build(root,out),out)
if __name__=='__main__': main()
