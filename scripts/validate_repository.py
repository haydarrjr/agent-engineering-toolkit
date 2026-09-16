#!/usr/bin/env python3
import json, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPLICIT={'margos','rethinking','agent-plugins-author'}; IMPLICIT={'software-craft','python-engineering-harness'}
errors=[]

def check(cond,msg):
    if not cond: errors.append(msg)

p=json.loads((ROOT/'plugin.json').read_text(encoding='utf-8'))
check(p.get('license')=='Apache-2.0','plugin license must be Apache-2.0')
check(p.get('$schema')=='https://agent-plugins.org/schemas/1.0.0/plugin.schema.json','portable schema mismatch')
check(p.get('name')=='agent-engineering-toolkit','plugin name mismatch')
check((ROOT/'LICENSE').is_file(),'missing LICENSE')
prov=json.loads((ROOT/'provenance/imports.json').read_text(encoding='utf-8'))
check(len(prov.get('imports',[]))>=2,'provenance imports incomplete')

for name in sorted(EXPLICIT|IMPLICIT):
    d=ROOT/'skills'/name
    check((d/'SKILL.md').is_file(),f'{name}: missing SKILL.md')
    meta=d/'agents/openai.yaml'; check(meta.is_file(),f'{name}: missing agents/openai.yaml')
    if meta.is_file():
        t=meta.read_text(encoding='utf-8')
        expect='false' if name in EXPLICIT else 'true'
        check(re.search(r'allow_implicit_invocation:\s*'+expect+r'\b',t) is not None,f'{name}: implicit policy drift')

# Version and license parity.
c=json.loads((ROOT/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))
for k in ('name','version','description','homepage','repository','license'):
    check(p.get(k)==c.get(k),f'codex parity mismatch: {k}')
for mp in (ROOT/'.github/plugin/marketplace.json',ROOT/'.agents/plugins/marketplace.json'):
    m=json.loads(mp.read_text(encoding='utf-8')); entry=m['plugins'][0]
    check(entry['name']==p['name'] and entry['version']==p['version'],'marketplace identity mismatch')
    check(entry.get('license')=='Apache-2.0','marketplace license mismatch')

# Public hygiene.
for f in ROOT.rglob('*'):
    if not f.is_file() or '.git' in f.parts or f.suffix.lower() in {'.zip'}: continue
    if f.resolve() == Path(__file__).resolve(): continue
    if f.name in {'.env'} or f.suffix.lower() in {'.pem','.key','.p12','.pfx'}: errors.append(f'unsafe tracked file: {f.relative_to(ROOT)}')
    if f.stat().st_size < 2_000_000:
        try: text=f.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        for bad in ('C:\\Users\\onder','/home/onder/','BEGIN OPENSSH PRIVATE KEY','ghp_','sk-proj-'):
            if bad in text: errors.append(f'private/sensitive marker {bad!r} in {f.relative_to(ROOT)}')
        if 'Proprietary' in text and f.relative_to(ROOT).as_posix() not in {'provenance/imports.json'}:
            errors.append(f'proprietary marker in public source: {f.relative_to(ROOT)}')

# Application draft limits.
app=(ROOT/'docs/CODEX_FOR_OSS_APPLICATION.md').read_text(encoding='utf-8')
for heading in ['Why this repository qualifies','API credits','Anything else']:
    m=re.search(r'## '+re.escape(heading)+r'.*?\n\n(.*?)(?=\n\n## |\Z)',app,re.S)
    if m:
        body=' '.join(line.strip() for line in m.group(1).splitlines() if line.strip() and not line.startswith('#'))
        check(len(body)<=500,f'application draft exceeds 500 chars: {heading} ({len(body)})')

if errors:
    print('Repository validation: FAIL')
    for e in errors: print('ERROR:',e)
    raise SystemExit(1)
print('Repository validation: PASS')
print('skills:', ', '.join(sorted(EXPLICIT|IMPLICIT)))
print('evidence boundary: source-only')
