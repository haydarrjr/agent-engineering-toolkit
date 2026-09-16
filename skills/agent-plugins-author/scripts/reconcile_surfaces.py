#!/usr/bin/env python3
import json, sys
from pathlib import Path
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
p=json.loads((root/'plugin.json').read_text(encoding='utf-8')); c=json.loads((root/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))
fields=['name','version','description','homepage','repository','license']
errors=[f'{k}: portable={p.get(k)!r} codex={c.get(k)!r}' for k in fields if p.get(k)!=c.get(k)]
print('Surface reconciliation:', 'FAIL' if errors else 'PASS')
for e in errors: print('ERROR:',e)
raise SystemExit(1 if errors else 0)
