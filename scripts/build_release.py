#!/usr/bin/env python3
import argparse, hashlib, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BUILDER=ROOT/'skills/agent-plugins-author/scripts/build_package.py'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def build(out): subprocess.run([sys.executable,str(BUILDER),str(ROOT),'--out',str(out.relative_to(ROOT))],check=True,cwd=ROOT,stdout=subprocess.DEVNULL)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check-reproducible',action='store_true'); args=ap.parse_args()
    subprocess.run([sys.executable,str(ROOT/'scripts/validate_repository.py')],check=True,cwd=ROOT)
    out=ROOT/'dist/agent-engineering-toolkit-1.0.0.zip'; out.parent.mkdir(exist_ok=True); build(out)
    if args.check_reproducible:
        tmp=ROOT/'dist/.repro.zip'; build(tmp)
        if sha(out)!=sha(tmp): raise SystemExit('reproducibility check failed')
        tmp.unlink(); print('reproducibility: PASS')
    print('archive:',out); print('sha256:',sha(out))
if __name__=='__main__': main()
