#!/usr/bin/env python3
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARGOS=ROOT/'skills/margos'
COPILOT=ROOT/'com.github.copilot/agents'
EXPECTED={'margos-scout.agent.md','margos-worker.agent.md','margos-verifier.agent.md','margos-critic.agent.md'}
errors=[]

def check(cond,msg):
    if not cond: errors.append(msg)

skill=(MARGOS/'SKILL.md').read_text(encoding='utf-8')
lower=skill.lower()
for signal in ('gpt-','claude','anthropic','gemini'): check(signal not in lower,f'MARGOS root must stay provider/model agnostic: {signal}')
for ref in ('decision-model.md','model-routing.md','host-codex.md','host-copilot.md','host-boundaries.md','external-effects.md'):
    check((MARGOS/'references'/ref).is_file(),f'missing MARGOS reference: {ref}')
    check(f'references/{ref}' in skill,f'MARGOS root does not route {ref}')

routing=(MARGOS/'references/model-routing.md').read_text(encoding='utf-8')
for token in ('ECONOMY_READ','BALANCED_EXEC','FRONTIER_REASONING','INDEPENDENT_CRITIC','failed verification'): check(token.lower() in routing.lower(),f'model-routing.md missing {token}')
check('do not escalate merely because' in routing.lower(),'model-routing.md must reject keyword/length escalation')

codex=(MARGOS/'references/host-codex.md').read_text(encoding='utf-8').lower()
check('native subagent' in codex,'Codex adapter must use native subagents')
check('mcp server' in codex,'Codex adapter must preserve no-MCP boundary')
copilot=(MARGOS/'references/host-copilot.md').read_text(encoding='utf-8').lower()
check('com.github.copilot/agents' in copilot,'Copilot namespace must be documented')
check('model: auto' in copilot,'Copilot host-owned model selection must be documented')

actual={p.name for p in COPILOT.glob('*.agent.md')} if COPILOT.is_dir() else set()
check(actual==EXPECTED,f'Copilot MARGOS agents mismatch: {sorted(actual)}')
for p in sorted(COPILOT.glob('*.agent.md')):
    text=p.read_text(encoding='utf-8')
    m=re.match(r'^---\n(.*?)\n---\n',text,re.S)
    check(m is not None,f'{p.name}: missing frontmatter')
    if not m: continue
    fm=m.group(1)
    check(re.search(r'^model:\s*auto\s*$',fm,re.M) is not None,f'{p.name}: model must be auto')
    check(re.search(r'^user-invocable:\s*false\s*$',fm,re.M) is not None,f'{p.name}: must be hidden leaf agent')
    tools=re.search(r'^tools:\s*\[(.*?)\]\s*$',fm,re.M)
    check(tools is not None,f'{p.name}: tools list missing')
    if tools: check('agent' not in {x.strip().lower() for x in tools.group(1).split(',')},f'{p.name}: recursive agent tool forbidden')

check(not (ROOT/'mcp.json').exists(),'MARGOS public package must not add mcp.json')

if errors:
    print('MARGOS host-adapter validation: FAIL')
    for e in errors: print('ERROR:',e)
    raise SystemExit(1)
print('MARGOS host-adapter validation: PASS')
print('evidence boundary: source-only')
