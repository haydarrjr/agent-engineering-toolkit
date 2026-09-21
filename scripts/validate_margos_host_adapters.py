#!/usr/bin/env python3
import json, re
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
for signal in ('gpt-','claude','anthropic','gemini','typesafe','jev'):
    check(signal not in lower,f'MARGOS root must stay provider/model agnostic: {signal}')
for phrase in ('three layers','policy always outranks reflex','host-native'):
    check(phrase in lower,f'MARGOS root missing vNext invariant: {phrase}')

refs=('decision-model.md','model-routing.md','policy-layer.md','reflex-layer.md','reflex-confidence.md','reflex-provider.md','execution-layer.md','host-codex.md','host-copilot.md','host-boundaries.md','external-effects.md')
for ref in refs:
    check((MARGOS/'references'/ref).is_file(),f'missing MARGOS reference: {ref}')
    check(f'references/{ref}' in skill,f'MARGOS root does not route {ref}')

for name in ('question-set-v2.json','threshold-policy-v2.json'):
    path=MARGOS/'contracts'/name
    check(path.is_file(),f'missing MARGOS contract: {name}')
    if path.is_file():
        try: json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc: errors.append(f'invalid contract {name}: {exc}')

question_doc = json.loads((MARGOS/'contracts/question-set-v2.json').read_text(encoding='utf-8'))
for question in question_doc.get('questions', []):
    check(isinstance(question.get('instructions'), str) and '`state.' in question['instructions'], f"question lacks a self-contained structured path: {question.get('id')}")
    if question.get('kind') == 'choice':
        check(set(question.get('criteria', {})) == set(question.get('choices', [])), f"Choice criteria are not exhaustive: {question.get('id')}")
    elif question.get('kind') == 'score':
        check(len(question.get('criteria', [])) == len(question.get('levels', [])), f"Score criteria do not cover levels: {question.get('id')}")
        check('criterion' in question and 'instructions' in question, f"Score semantics are incomplete: {question.get('id')}")
    elif question.get('kind') == 'noul':
        check(isinstance(question.get('true'), str) and isinstance(question.get('false'), str), f"Noul criteria are incomplete: {question.get('id')}")

for name in ('routing-state-v2.schema.json','reflex-request-v2.schema.json','reflex-result-v2.schema.json','route-decision-v1.schema.json','route-receipt-v2.schema.json','jev-calibration-binding-v2.schema.json'):
    path=MARGOS/'schemas'/name
    check(path.is_file(),f'missing MARGOS schema: {name}')
    if path.is_file():
        try: json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc: errors.append(f'invalid schema {name}: {exc}')

kernel=MARGOS/'scripts/margos_decide.py'
check(kernel.is_file(),'missing deterministic MARGOS decision kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in ('coordination','disposition','computetier','role','reflexprovider','margos-pol-001','decision_authority','--reflex-provider','ambiguity_escalation','verification_escalation','direct_escalation','threshold_policy_sha256','admit_reflex'):
        check(token in text,f'MARGOS decision kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','typesafe','api_key'):
        check(forbidden not in text,f'phase-2 kernel must not add remote provider coupling: {forbidden}')

adapter=MARGOS/'scripts/margos_reflex_jev.py'
check(adapter.is_file(),'missing optional Jev Reflex adapter')
if adapter.is_file():
    text=adapter.read_text(encoding='utf-8')
    check('https://api.typesafe.ai' in text,'Jev adapter default endpoint mismatch')
    check('TYPESAFE_API_KEY' in text,'Jev adapter must read runtime key from environment')
    check('urllib.request' in text,'Jev adapter must remain stdlib-only')
    check('import requests' not in text and 'import httpx' not in text,'Jev adapter must not add third-party HTTP dependencies')
    for token in ('ROUTING_PROJECTION_VERSION','CONTEXT_PROJECTION_VERSION','CALIBRATION_BINDING_VERSION','state.candidates['):
        check(token in text,f'Jev adapter missing v2 contract: {token}')
check((ROOT/'scripts/benchmark_margos_routing.py').is_file(),'missing MARGOS routing benchmark')
check((ROOT/'docs/MARGOS_RESEARCH.md').is_file(),'missing MARGOS research record')
check((ROOT/'docs/MARGOS_EVALUATION.md').is_file(),'missing MARGOS evaluation record')

routing=(MARGOS/'references/model-routing.md').read_text(encoding='utf-8')
for token in ('ECONOMY_READ','BALANCED_EXEC','FRONTIER_REASONING','INDEPENDENT_CRITIC','failed verification'):
    check(token.lower() in routing.lower(),f'model-routing.md missing {token}')
check('role, not a compute tier' in routing.lower(),'critic role must be separate from compute')
check('do not escalate merely because' in routing.lower(),'routing must reject keyword/length escalation')

decision=(MARGOS/'references/decision-model.md').read_text(encoding='utf-8')
for token in ('DIRECT','TRANSFER','DELEGATED','SERIALIZED','PROCEED','FALLBACK_DIRECT','HALT'):
    check(token in decision,f'decision-model.md missing {token}')

codex=(MARGOS/'references/host-codex.md').read_text(encoding='utf-8').lower()
check('native subagent' in codex,'Codex adapter must use native subagents')
check('mcp server' in codex,'Codex adapter must preserve no-MCP boundary')
copilot=(MARGOS/'references/host-copilot.md').read_text(encoding='utf-8').lower()
check('com.github.copilot/agents' in copilot,'Copilot namespace must be documented')
check('model: auto' in copilot,'Copilot model selection must remain host-owned')

actual={p.name for p in COPILOT.glob('*.agent.md')} if COPILOT.is_dir() else set()
check(actual==EXPECTED,f'Copilot MARGOS agents mismatch: {sorted(actual)}')
for p in sorted(COPILOT.glob('*.agent.md')):
    text=p.read_text(encoding='utf-8')
    match=re.match(r'^---\n(.*?)\n---\n',text,re.S)
    check(match is not None,f'{p.name}: missing frontmatter')
    if not match: continue
    fm=match.group(1)
    check(re.search(r'^model:\s*auto\s*$',fm,re.M) is not None,f'{p.name}: model must be auto')
    check(re.search(r'^user-invocable:\s*false\s*$',fm,re.M) is not None,f'{p.name}: must be hidden leaf agent')
    tools=re.search(r'^tools:\s*\[(.*?)\]\s*$',fm,re.M)
    check(tools is not None,f'{p.name}: tools list missing')
    if tools: check('agent' not in {x.strip().lower() for x in tools.group(1).split(',')},f'{p.name}: recursive agent tool forbidden')

check(not (ROOT/'mcp.json').exists(),'MARGOS public package must not add mcp.json')
if errors:
    print('MARGOS host-adapter validation: FAIL')
    for error in errors: print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS host-adapter validation: PASS')
print('vNext boundary: deterministic Policy + optional typed Reflex provider + host-native Execution')
