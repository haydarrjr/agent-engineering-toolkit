#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARGOS=ROOT/'skills/margos'
errors=[]

def check(condition,message):
    if not condition:
        errors.append(message)

skill=(MARGOS/'SKILL.md').read_text(encoding='utf-8')
lower=skill.lower()
check('derived context view' in lower,'MARGOS root must route derived Context View behavior')
check('canonical evidence remains unchanged' in lower,'MARGOS root must preserve canonical evidence')
check('references/context-governor.md' in skill,'MARGOS root must route context-governor.md')
check('references/context-retention-policy.md' not in skill,'retention detail should remain progressively disclosed')
check('references/context-rehydration.md' not in skill,'rehydration detail should remain progressively disclosed')

for name in ('context-governor.md','context-retention-policy.md','context-rehydration.md'):
    check((MARGOS/'references'/name).is_file(),f'missing context reference: {name}')

schemas={}
schema_names=(
    'context-item-v1.schema.json',
    'context-state-v1.schema.json',
    'context-decision-v1.schema.json',
    'context-receipt-v1.schema.json',
    'context-reflex-request-v1.schema.json',
    'context-reflex-result-v1.schema.json',
)
for name in schema_names:
    path=MARGOS/'schemas'/name
    check(path.is_file(),f'missing context schema: {name}')
    if path.is_file():
        try:
            schemas[name]=json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            errors.append(f'invalid context schema {name}: {exc}')

contracts={}
for name in ('context-question-set-v1.json','context-threshold-policy-v1.json'):
    path=MARGOS/'contracts'/name
    check(path.is_file(),f'missing context contract: {name}')
    if path.is_file():
        try:
            contracts[name]=json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            errors.append(f'invalid context contract {name}: {exc}')

questions=contracts.get('context-question-set-v1.json',{})
check(questions.get('version')=='margos-context-questions/v1','context question-set version drift')
qitems=questions.get('questions',[])
check(
    [x.get('id') for x in qitems if isinstance(x,dict)]==['keep_awareness','keep_full','replay_needed'],
    'Context Reflex v1 question IDs/order drift',
)
check(all(isinstance(x,dict) and x.get('kind')=='noul' for x in qitems),'Context Reflex v1 must use atomic Noul questions')

thresholds=contracts.get('context-threshold-policy-v1.json',{})
check(thresholds.get('version')=='margos-context-thresholds/v1','context threshold version drift')
for key in ('full_threshold','awareness_threshold','replay_risk_threshold','abstain_band'):
    value=thresholds.get(key)
    check(isinstance(value,(int,float)) and not isinstance(value,bool) and 0<=float(value)<=1,f'invalid context threshold: {key}')
check(isinstance(thresholds.get('max_items_per_batch'),int) and 1<=thresholds.get('max_items_per_batch',0)<=64,'invalid context max_items_per_batch')
check(isinstance(thresholds.get('max_projection_chars'),int) and thresholds.get('max_projection_chars',0)>=1000,'invalid context max_projection_chars')
check(isinstance(thresholds.get('max_semantic_capsule_chars'),int) and 0<thresholds.get('max_semantic_capsule_chars',0)<=512,'invalid context max_semantic_capsule_chars')
check(thresholds.get('provider_failure_action')=='KEEP_REF','provider failure must conservatively keep a reference')

decision=schemas.get('context-decision-v1.schema.json',{})
actions=set(decision.get('properties',{}).get('action',{}).get('enum',[]))
check(actions=={'PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE'},'context action enum drift')
check('DELETE' not in actions,'context action model must not contain DELETE')
rehydration=decision.get('properties',{}).get('rehydration',{}).get('properties',{})
check(rehydration.get('may_repeat_external_effect',{}).get('const') is False,'rehydration must forbid external-effect replay')
sources=set(decision.get('properties',{}).get('decision_source',{}).get('enum',[]))
check('REFLEX_ASSISTED' in sources and 'REFLEX_CONSERVATIVE_FALLBACK' in sources,'context decision schema missing Reflex composition sources')

receipt=schemas.get('context-receipt-v1.schema.json',{})
props=receipt.get('properties',{})
check(props.get('authority',{}).get('const')=='DERIVED_VIEW','context receipt authority must be DERIVED_VIEW')
check(props.get('canonical_source_mutated',{}).get('const') is False,'context receipt must prove canonical source is not mutated')
check(props.get('question_set_version',{}).get('const')=='margos-context-questions/v1','context receipt must bind question-set version')
check(props.get('threshold_policy_version',{}).get('const')=='margos-context-thresholds/v1','context receipt must bind threshold-policy version')
check(props.get('threshold_policy_sha256',{}).get('pattern')=='^[0-9a-f]{64}provider_statuses=set(props.get('provider',{}).get('properties',{}).get('status',{}).get('enum',[]))
for status in ('DISABLED','AVAILABLE','NOT_CONFIGURED','ERROR'):
    check(status in provider_statuses,f'context receipt provider status missing {status}')

kernel=MARGOS/'scripts/margos_context.py'
check(kernel.is_file(),'missing MARGOS context kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in (
        'contextaction',
        'omit_rehydratable',
        'margos-ctx-pol-001',
        'canonical_source_mutated',
        'may_repeat_external_effect',
        'derived_view',
        'routing_core.reflexprovider',
        'keep_awareness',
        'keep_full',
        'replay_needed',
        '--reflex-provider',
        'not_configured',
        'remote_semantic_capsule_allowed',
        'semantic_capsule_chars',
        'threshold_policy_sha256',
        'secret_patterns',
    ):
        check(token in text,f'MARGOS context kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in text,f'context kernel must remain host-neutral and transport-free: {forbidden}')

adapter=MARGOS/'scripts/margos_reflex_jev.py'
check(adapter.is_file(),'missing shared Jev Reflex adapter')
if adapter.is_file():
    text=adapter.read_text(encoding='utf-8')
    for token in ('TYPESAFE_API_KEY','CONTEXT_REQUEST_VERSION','project_context_reflex_state','network_request_count','semantic_capsule','state.candidates['):
        check(token in text,f'Jev adapter missing Context Reflex boundary: {token}')
    check('SECOND_TYPESAFE' not in text,'Context Reflex must not create a second credential path')
    check(text.count('os.environ.get("TYPESAFE_API_KEY"')==1,'Jev adapter must use one runtime TYPESAFE_API_KEY lookup')

policy=(MARGOS/'references/context-retention-policy.md').read_text(encoding='utf-8') if (MARGOS/'references/context-retention-policy.md').is_file() else ''
for token in ('PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE','MARGOS-CTX-POL-001'):
    check(token in policy,f'context retention policy missing {token}')
check('There is no DELETE action.' in policy,'context retention policy must reject destructive deletion')

governor=(MARGOS/'references/context-governor.md').read_text(encoding='utf-8') if (MARGOS/'references/context-governor.md').is_file() else ''
for token in ('keep_awareness','keep_full','replay_needed','TYPESAFE_API_KEY','NOT_CONFIGURED'):
    check(token in governor,f'context governor docs missing Phase 2 contract: {token}')
check('alone never enables Context Reflex' in governor,'Context Reflex must require explicit provider selection')

rehydration_doc=(MARGOS/'references/context-rehydration.md').read_text(encoding='utf-8') if (MARGOS/'references/context-rehydration.md').is_file() else ''
check('cannot silently repeat an external mutation' in rehydration_doc,'rehydration must forbid silent mutation replay')
check('content_sha256' in rehydration_doc,'rehydration must be content-addressed')

ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
check('TYPESAFE_API_KEY' not in ci,'CI must not inject a live TypeSafe key')
check('--reflex-provider jev' not in ci,'CI must not invoke live Context Reflex')
check((ROOT/'tests/test_margos_context_policy.py').is_file(),'missing deterministic context policy tests')
check((ROOT/'tests/test_margos_context_reflex.py').is_file(),'missing Context Reflex fixture tests')

if errors:
    print('MARGOS context validation: FAIL')
    for error in errors:
        print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS context validation: PASS')
print('authority: deterministic Policy -> optional Context Reflex -> derived Context View')
print('live provider: explicit opt-in only; CI remains fixture/offline')
,'context receipt must bind threshold-policy hash')
provider_statuses=set(props.get('provider',{}).get('properties',{}).get('status',{}).get('enum',[]))
for status in ('DISABLED','AVAILABLE','NOT_CONFIGURED','ERROR'):
    check(status in provider_statuses,f'context receipt provider status missing {status}')

kernel=MARGOS/'scripts/margos_context.py'
check(kernel.is_file(),'missing MARGOS context kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in (
        'contextaction',
        'omit_rehydratable',
        'margos-ctx-pol-001',
        'canonical_source_mutated',
        'may_repeat_external_effect',
        'derived_view',
        'routing_core.reflexprovider',
        'keep_awareness',
        'keep_full',
        'replay_needed',
        '--reflex-provider',
        'not_configured',
    ):
        check(token in text,f'MARGOS context kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in text,f'context kernel must remain host-neutral and transport-free: {forbidden}')

adapter=MARGOS/'scripts/margos_reflex_jev.py'
check(adapter.is_file(),'missing shared Jev Reflex adapter')
if adapter.is_file():
    text=adapter.read_text(encoding='utf-8')
    for token in ('TYPESAFE_API_KEY','CONTEXT_REQUEST_VERSION','project_context_reflex_state','network_request_count'):
        check(token in text,f'Jev adapter missing Context Reflex boundary: {token}')
    check('SECOND_TYPESAFE' not in text,'Context Reflex must not create a second credential path')
    check(text.count('os.environ.get("TYPESAFE_API_KEY"')==1,'Jev adapter must use one runtime TYPESAFE_API_KEY lookup')

policy=(MARGOS/'references/context-retention-policy.md').read_text(encoding='utf-8') if (MARGOS/'references/context-retention-policy.md').is_file() else ''
for token in ('PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE','MARGOS-CTX-POL-001'):
    check(token in policy,f'context retention policy missing {token}')
check('There is no DELETE action.' in policy,'context retention policy must reject destructive deletion')

governor=(MARGOS/'references/context-governor.md').read_text(encoding='utf-8') if (MARGOS/'references/context-governor.md').is_file() else ''
for token in ('keep_awareness','keep_full','replay_needed','TYPESAFE_API_KEY','NOT_CONFIGURED'):
    check(token in governor,f'context governor docs missing Phase 2 contract: {token}')
check('alone never enables Context Reflex' in governor,'Context Reflex must require explicit provider selection')

rehydration_doc=(MARGOS/'references/context-rehydration.md').read_text(encoding='utf-8') if (MARGOS/'references/context-rehydration.md').is_file() else ''
check('cannot silently repeat an external mutation' in rehydration_doc,'rehydration must forbid silent mutation replay')
check('content_sha256' in rehydration_doc,'rehydration must be content-addressed')

ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
check('TYPESAFE_API_KEY' not in ci,'CI must not inject a live TypeSafe key')
check('--reflex-provider jev' not in ci,'CI must not invoke live Context Reflex')
check((ROOT/'tests/test_margos_context_policy.py').is_file(),'missing deterministic context policy tests')
check((ROOT/'tests/test_margos_context_reflex.py').is_file(),'missing Context Reflex fixture tests')

if errors:
    print('MARGOS context validation: FAIL')
    for error in errors:
        print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS context validation: PASS')
print('authority: deterministic Policy -> optional Context Reflex -> derived Context View')
print('live provider: explicit opt-in only; CI remains fixture/offline')
,'context receipt must bind threshold-policy hash')
provider_statuses=set(props.get('provider',{}).get('properties',{}).get('status',{}).get('enum',[]))
for status in ('DISABLED','AVAILABLE','NOT_CONFIGURED','ERROR'):
    check(status in provider_statuses,f'context receipt provider status missing {status}')

kernel=MARGOS/'scripts/margos_context.py'
check(kernel.is_file(),'missing MARGOS context kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in (
        'contextaction',
        'omit_rehydratable',
        'margos-ctx-pol-001',
        'canonical_source_mutated',
        'may_repeat_external_effect',
        'derived_view',
        'routing_core.reflexprovider',
        'keep_awareness',
        'keep_full',
        'replay_needed',
        '--reflex-provider',
        'not_configured',
        'remote_semantic_capsule_allowed',
        'semantic_capsule_chars',
        'threshold_policy_sha256',
        'secret_patterns',
    ):
        check(token in text,f'MARGOS context kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in text,f'context kernel must remain host-neutral and transport-free: {forbidden}')

adapter=MARGOS/'scripts/margos_reflex_jev.py'
check(adapter.is_file(),'missing shared Jev Reflex adapter')
if adapter.is_file():
    text=adapter.read_text(encoding='utf-8')
    for token in ('TYPESAFE_API_KEY','CONTEXT_REQUEST_VERSION','project_context_reflex_state','network_request_count','semantic_capsule','state.candidates['):
        check(token in text,f'Jev adapter missing Context Reflex boundary: {token}')
    check('SECOND_TYPESAFE' not in text,'Context Reflex must not create a second credential path')
    check(text.count('os.environ.get("TYPESAFE_API_KEY"')==1,'Jev adapter must use one runtime TYPESAFE_API_KEY lookup')

policy=(MARGOS/'references/context-retention-policy.md').read_text(encoding='utf-8') if (MARGOS/'references/context-retention-policy.md').is_file() else ''
for token in ('PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE','MARGOS-CTX-POL-001'):
    check(token in policy,f'context retention policy missing {token}')
check('There is no DELETE action.' in policy,'context retention policy must reject destructive deletion')

governor=(MARGOS/'references/context-governor.md').read_text(encoding='utf-8') if (MARGOS/'references/context-governor.md').is_file() else ''
for token in ('keep_awareness','keep_full','replay_needed','TYPESAFE_API_KEY','NOT_CONFIGURED'):
    check(token in governor,f'context governor docs missing Phase 2 contract: {token}')
check('alone never enables Context Reflex' in governor,'Context Reflex must require explicit provider selection')

rehydration_doc=(MARGOS/'references/context-rehydration.md').read_text(encoding='utf-8') if (MARGOS/'references/context-rehydration.md').is_file() else ''
check('cannot silently repeat an external mutation' in rehydration_doc,'rehydration must forbid silent mutation replay')
check('content_sha256' in rehydration_doc,'rehydration must be content-addressed')

ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
check('TYPESAFE_API_KEY' not in ci,'CI must not inject a live TypeSafe key')
check('--reflex-provider jev' not in ci,'CI must not invoke live Context Reflex')
check((ROOT/'tests/test_margos_context_policy.py').is_file(),'missing deterministic context policy tests')
check((ROOT/'tests/test_margos_context_reflex.py').is_file(),'missing Context Reflex fixture tests')

if errors:
    print('MARGOS context validation: FAIL')
    for error in errors:
        print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS context validation: PASS')
print('authority: deterministic Policy -> optional Context Reflex -> derived Context View')
print('live provider: explicit opt-in only; CI remains fixture/offline')
,'context receipt must bind threshold-policy hash')
provider_statuses=set(props.get('provider',{}).get('properties',{}).get('status',{}).get('enum',[]))
for status in ('DISABLED','AVAILABLE','NOT_CONFIGURED','ERROR'):
    check(status in provider_statuses,f'context receipt provider status missing {status}')

kernel=MARGOS/'scripts/margos_context.py'
check(kernel.is_file(),'missing MARGOS context kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in (
        'contextaction',
        'omit_rehydratable',
        'margos-ctx-pol-001',
        'canonical_source_mutated',
        'may_repeat_external_effect',
        'derived_view',
        'routing_core.reflexprovider',
        'keep_awareness',
        'keep_full',
        'replay_needed',
        '--reflex-provider',
        'not_configured',
    ):
        check(token in text,f'MARGOS context kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in text,f'context kernel must remain host-neutral and transport-free: {forbidden}')

adapter=MARGOS/'scripts/margos_reflex_jev.py'
check(adapter.is_file(),'missing shared Jev Reflex adapter')
if adapter.is_file():
    text=adapter.read_text(encoding='utf-8')
    for token in ('TYPESAFE_API_KEY','CONTEXT_REQUEST_VERSION','project_context_reflex_state','network_request_count'):
        check(token in text,f'Jev adapter missing Context Reflex boundary: {token}')
    check('SECOND_TYPESAFE' not in text,'Context Reflex must not create a second credential path')
    check(text.count('os.environ.get("TYPESAFE_API_KEY"')==1,'Jev adapter must use one runtime TYPESAFE_API_KEY lookup')

policy=(MARGOS/'references/context-retention-policy.md').read_text(encoding='utf-8') if (MARGOS/'references/context-retention-policy.md').is_file() else ''
for token in ('PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE','MARGOS-CTX-POL-001'):
    check(token in policy,f'context retention policy missing {token}')
check('There is no DELETE action.' in policy,'context retention policy must reject destructive deletion')

governor=(MARGOS/'references/context-governor.md').read_text(encoding='utf-8') if (MARGOS/'references/context-governor.md').is_file() else ''
for token in ('keep_awareness','keep_full','replay_needed','TYPESAFE_API_KEY','NOT_CONFIGURED'):
    check(token in governor,f'context governor docs missing Phase 2 contract: {token}')
check('alone never enables Context Reflex' in governor,'Context Reflex must require explicit provider selection')

rehydration_doc=(MARGOS/'references/context-rehydration.md').read_text(encoding='utf-8') if (MARGOS/'references/context-rehydration.md').is_file() else ''
check('cannot silently repeat an external mutation' in rehydration_doc,'rehydration must forbid silent mutation replay')
check('content_sha256' in rehydration_doc,'rehydration must be content-addressed')

ci=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
check('TYPESAFE_API_KEY' not in ci,'CI must not inject a live TypeSafe key')
check('--reflex-provider jev' not in ci,'CI must not invoke live Context Reflex')
check((ROOT/'tests/test_margos_context_policy.py').is_file(),'missing deterministic context policy tests')
check((ROOT/'tests/test_margos_context_reflex.py').is_file(),'missing Context Reflex fixture tests')

if errors:
    print('MARGOS context validation: FAIL')
    for error in errors:
        print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS context validation: PASS')
print('authority: deterministic Policy -> optional Context Reflex -> derived Context View')
print('live provider: explicit opt-in only; CI remains fixture/offline')
