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
for name in ('context-item-v1.schema.json','context-state-v1.schema.json','context-decision-v1.schema.json','context-receipt-v1.schema.json'):
    path=MARGOS/'schemas'/name
    check(path.is_file(),f'missing context schema: {name}')
    if path.is_file():
        try:
            schemas[name]=json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            errors.append(f'invalid context schema {name}: {exc}')

decision=schemas.get('context-decision-v1.schema.json',{})
actions=set(decision.get('properties',{}).get('action',{}).get('enum',[]))
check(actions=={'PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE'},'context action enum drift')
check('DELETE' not in actions,'context action model must not contain DELETE')
rehydration=decision.get('properties',{}).get('rehydration',{}).get('properties',{})
check(rehydration.get('may_repeat_external_effect',{}).get('const') is False,'rehydration must forbid external-effect replay')

receipt=schemas.get('context-receipt-v1.schema.json',{})
props=receipt.get('properties',{})
check(props.get('authority',{}).get('const')=='DERIVED_VIEW','context receipt authority must be DERIVED_VIEW')
check(props.get('canonical_source_mutated',{}).get('const') is False,'context receipt must prove canonical source is not mutated')

kernel=MARGOS/'scripts/margos_context.py'
check(kernel.is_file(),'missing deterministic context kernel')
if kernel.is_file():
    text=kernel.read_text(encoding='utf-8').lower()
    for token in ('contextaction','omit_rehydratable','margos-ctx-pol-001','canonical_source_mutated','may_repeat_external_effect','derived_view'):
        check(token in text,f'context kernel missing {token}')
    for forbidden in ('import requests','import httpx','urllib.request','session.compact','claude'):
        check(forbidden not in text,f'context kernel must remain offline and host-neutral: {forbidden}')

policy=(MARGOS/'references/context-retention-policy.md').read_text(encoding='utf-8') if (MARGOS/'references/context-retention-policy.md').is_file() else ''
for token in ('PIN','KEEP_FULL','KEEP_REF','KEEP_HEAD','OMIT_REHYDRATABLE','MARGOS-CTX-POL-001'):
    check(token in policy,f'context retention policy missing {token}')
check('There is no DELETE action.' in policy,'context retention policy must reject destructive deletion')

rehydration_doc=(MARGOS/'references/context-rehydration.md').read_text(encoding='utf-8') if (MARGOS/'references/context-rehydration.md').is_file() else ''
check('cannot silently repeat an external mutation' in rehydration_doc,'rehydration must forbid silent mutation replay')
check('content_sha256' in rehydration_doc,'rehydration must be content-addressed')
check((ROOT/'tests/test_margos_context_policy.py').is_file(),'missing deterministic context policy tests')

if errors:
    print('MARGOS context validation: FAIL')
    for error in errors:
        print('ERROR:',error)
    raise SystemExit(1)
print('MARGOS context validation: PASS')
print('authority: deterministic Policy -> derived Context View; canonical evidence unchanged')
