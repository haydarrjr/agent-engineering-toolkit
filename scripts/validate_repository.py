#!/usr/bin/env python3
import json, re, tomllib
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
check(re.fullmatch(r'\d+\.\d+\.\d+',str(p.get('version',''))) is not None,'plugin version must be semver')
check((ROOT/'LICENSE').is_file(),'missing LICENSE')
version=p.get('version')

skills={x.name for x in (ROOT/'skills').iterdir() if x.is_dir()}
check(skills==EXPLICIT|IMPLICIT,f'skill topology mismatch: {sorted(skills)}')
for name in sorted(EXPLICIT|IMPLICIT):
    d=ROOT/'skills'/name
    check((d/'SKILL.md').is_file(),f'{name}: missing SKILL.md')
    meta=d/'agents/openai.yaml'; check(meta.is_file(),f'{name}: missing agents/openai.yaml')
    if meta.is_file():
        t=meta.read_text(encoding='utf-8'); expect='false' if name in EXPLICIT else 'true'
        check(re.search(r'allow_implicit_invocation:\s*'+expect+r'\b',t) is not None,f'{name}: implicit policy drift')

c=json.loads((ROOT/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))
for k in ('name','version','description','homepage','repository','license'): check(p.get(k)==c.get(k),f'codex parity mismatch: {k}')
check('keywords' not in c,'Codex adapter must not override portable keywords')

py=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
check(py.get('project',{}).get('version')==version,'pyproject version mismatch')
cff=(ROOT/'CITATION.cff').read_text(encoding='utf-8')
check(re.search(r'^version:\s*'+re.escape(str(version))+r'\s*$',cff,re.M) is not None,'CITATION.cff version mismatch')

prov=json.loads((ROOT/'provenance/imports.json').read_text(encoding='utf-8'))
check(prov.get('generated_for_release')==version,'provenance release version mismatch')
check(len(prov.get('imports',[]))>=3,'provenance imports incomplete for 1.1')

codex=json.loads((ROOT/'.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
centry=codex.get('plugins',[{}])[0]
check(centry.get('name')==p['name'],'Codex marketplace name mismatch')
source=centry.get('source',{})
check(source.get('source')=='url' and source.get('url')==p['repository']+'.git' and source.get('ref')=='main','Codex marketplace source mismatch')
check(centry.get('policy')=={'installation':'AVAILABLE','authentication':'ON_INSTALL'},'Codex marketplace policy mismatch')

copilot=json.loads((ROOT/'.github/plugin/marketplace.json').read_text(encoding='utf-8'))
gentry=copilot.get('plugins',[{}])[0]
check(gentry.get('name')==p['name'] and gentry.get('version')==version,'Copilot marketplace identity mismatch')
check(gentry.get('source')=='.','Copilot marketplace source must be repository root')
check(gentry.get('strict') is True,'Copilot marketplace must keep strict Agent Plugins validation')
check(gentry.get('license')=='Apache-2.0','Copilot marketplace license mismatch')
check(gentry.get('keywords')==p.get('keywords'),'Copilot marketplace keywords must come from portable manifest')

check(not (ROOT/'mcp.json').exists(),'public package unexpectedly contains mcp.json')
expected_agents={'margos-scout.agent.md','margos-worker.agent.md','margos-verifier.agent.md','margos-critic.agent.md'}
agent_root=ROOT/'com.github.copilot/agents'
check(agent_root.is_dir(),'Copilot MARGOS agent namespace missing')
if agent_root.is_dir(): check({x.name for x in agent_root.glob('*.agent.md')}==expected_agents,'Copilot MARGOS agent set mismatch')

readme=(ROOT/'README.md').read_text(encoding='utf-8')
check('actions/workflows/ci.yml/badge.svg' in readme,'README CI badge missing')

for f in ROOT.rglob('*'):
    if not f.is_file() or '.git' in f.parts or f.suffix.lower() in {'.zip'}: continue
    if f.resolve()==Path(__file__).resolve(): continue
    if f.name in {'.env'} or f.suffix.lower() in {'.pem','.key','.p12','.pfx'}: errors.append(f'unsafe tracked file: {f.relative_to(ROOT)}')
    if f.stat().st_size < 2_000_000:
        try: text=f.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        for bad in ('C:\\Users\\onder','/home/onder/','BEGIN OPENSSH PRIVATE KEY','ghp_','sk-proj-'):
            if bad in text: errors.append(f'private/sensitive marker {bad!r} in {f.relative_to(ROOT)}')
        if 'Proprietary' in text and f.relative_to(ROOT).as_posix() not in {'provenance/imports.json'}: errors.append(f'proprietary marker in public source: {f.relative_to(ROOT)}')

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
print('version:',version)
print('skills:', ', '.join(sorted(EXPLICIT|IMPLICIT)))
print('evidence boundary: source-only')
