#!/usr/bin/env python3
from pathlib import Path
import subprocess, sys, tempfile

HERE = Path(__file__).resolve().parent

def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, check=True)

def main():
    run(HERE / 'repo_index.py', HERE.parent)
    run(HERE / 'impact_analysis.py', 'Python', '--root', HERE.parent)
    with tempfile.NamedTemporaryFile('w', suffix='.log', delete=False) as f:
        f.write('pkg/mod.py:12: failure\n')
        name = f.name
    out = run(HERE / 'fault_localize.py', name)
    assert 'pkg/mod.py' in out.stdout
    Path(name).unlink(missing_ok=True)
    print('python-engineering-harness self-test: PASS')

if __name__ == '__main__':
    main()
