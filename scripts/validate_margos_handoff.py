#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARGOS=ROOT/'skills/margos'
errors=[]

def check(cond,msg):
    if not cond: errors.append(msg)

schemas=(
 'child-contract-v1.schema.json',
 'child-context-bundle-v1.schema.json',
 'child-context-receipt-v1.schema.json',
 'child-result-v1.schema.json',
 'child-rehydration-plan-v1.schema.json',
 'child-rehydration-result-v1.schema.json',
 'route-receipt-v1.schema.json',
)
parsed={}
for name in schemas:
    path=MARGOS/'schemas'/name
    check(path.is_file(),f'missing Phase 3 schema: {name}')
    if path.is_file():
        try: parsed[name]=json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc: errors.append(f'invalid schema {name}: {exc}')

policy_path=MARGOS/'contracts/child-handoff-policy-v1.json'
check(policy_path.is_file(),'missing child-handoff-policy-v1.json')
policy={}
if policy_path.is_file():
    try: policy=json.loads(policy_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc: errors.append(f'invalid child handoff policy: {exc}')
check(policy.get('version')=='margos-child-handoff-policy/v1','child handoff policy version drift')
roles=policy.get('roles',{})
check(set(roles)=={'SCOUT','WORKER','VERIFIER','INDEPENDENT_CRITIC'},'child handoff roles drift')
check(roles.get('INDEPENDENT_CRITIC',{}).get('inherit_optional') is False,'critic must not inherit optional implementation context')

route=parsed.get('route-receipt-v1.schema.json',{})
binding=route.get('properties',{}).get('context_binding',{})
check(binding.get('type')=='object','route receipt must expose optional context_binding')

bundle=parsed.get('child-context-bundle-v1.schema.json',{})
check(bundle.get('properties',{}).get('authority',{}).get('const')=='DERIVED_VIEW','child bundle must be DERIVED_VIEW')
check(bundle.get('properties',{}).get('handoff_policy_version',{}).get('const')=='margos-child-handoff-policy/v1','child bundle must bind handoff policy')
receipt=parsed.get('child-context-receipt-v1.schema.json',{})
check(receipt.get('properties',{}).get('canonical_source_mutated',{}).get('const') is False,'child receipt must prove canonical source unchanged')

script=MARGOS/'scripts/margos_handoff.py'
check(script.is_file(),'missing margos_handoff.py')
if script.is_file():
    text=script.read_text(encoding='utf-8')
    lower=text.lower()
    for token in ('build_child_handoff','bind_route_context','plan_child_rehydration','resolve_child_rehydration','required_coverage','context_binding','handoff_policy_version'):
        check(token in lower,f'handoff kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in lower,f'handoff kernel must stay host-neutral/offline: {forbidden}')

child_doc=MARGOS/'references/child-context.md'
check(child_doc.is_file(),'missing child-context.md')
execution=(MARGOS/'references/execution-layer.md').read_text(encoding='utf-8')
check('child-context.md' in execution,'execution layer must progressively disclose child-context.md')
check('margos_handoff.py' in execution,'execution layer must name handoff helper')

codex=(MARGOS/'references/host-codex.md').read_text(encoding='utf-8').lower()
copilot=(MARGOS/'references/host-copilot.md').read_text(encoding='utf-8').lower()
for text,name in ((codex,'Codex'),(copilot,'Copilot')):
    check('margos-child-context-bundle/v1' in text or 'margos_handoff.py' in text,f'{name} must document bounded child handoff')
    check('rehydration' in text,f'{name} must document parent-side rehydration')

for name in ('margos-scout.agent.md','margos-worker.agent.md','margos-verifier.agent.md','margos-critic.agent.md'):
    path=ROOT/'com.github.copilot/agents'/name
    check(path.is_file(),f'missing leaf agent: {name}')
    if path.is_file():
        text=path.read_text(encoding='utf-8')
        check('rehydration_requests' in text,f'{name} must expose rehydration request protocol')

check((ROOT/'tests/test_margos_child_context.py').is_file(),'missing Phase 3 child-context tests')
fixture=ROOT/'tests/fixtures/margos/child-role-contract-v1.json'
check(fixture.is_file(),'missing frozen Phase 3 role fixture')

ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
check('MARGOS child-context contract' in ci,'CI must run child-context validator')
check('TYPESAFE_API_KEY' not in ci,'CI must not inject live TypeSafe credentials')

if errors:
    print('MARGOS child-context validation: FAIL')
    for error in errors: print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS child-context validation: PASS')
print('binding: route -> parent context -> role-aware child bundle; canonical source unchanged')
