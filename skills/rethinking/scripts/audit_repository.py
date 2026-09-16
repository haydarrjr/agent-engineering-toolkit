#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path

NAMES = {'AGENTS.md', 'SKILL.md', 'plugin.json', 'marketplace.json', 'openai.yaml'}
SIGNALS = [
    ('blanket-reading', re.compile(r'(?i)read\s+(all|every)\s+.*(file|doc)')),
    ('approval-pause', re.compile(r'(?i)(ask|request).*(approval|confirmation).*(before|prior)')),
    ('generic-expertise', re.compile(r'(?i)best practices|write clean code|be an expert')),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files, findings = [], []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '.git' in p.parts:
            continue
        if p.name in NAMES or p.suffix.lower() == '.md' and ('skill' in p.as_posix().lower() or 'agent' in p.as_posix().lower()):
            try: text = p.read_text(encoding='utf-8')
            except UnicodeDecodeError: continue
            rel = p.relative_to(root).as_posix(); files.append(rel)
            if len(text.splitlines()) > 500 and p.name == 'SKILL.md':
                findings.append({'path': rel, 'signal': 'large-entrypoint', 'detail': 'SKILL.md exceeds 500 lines'})
            for label, rx in SIGNALS:
                if rx.search(text):
                    findings.append({'path': rel, 'signal': label})
    result = {'root': str(root), 'instruction_files': files, 'findings': findings, 'status': 'REVIEW' if findings else 'PASS', 'note': 'Heuristic discovery only; current-source conformance still requires reading the official guidance.'}
    if args.format == 'json': print(json.dumps(result, indent=2))
    else:
        print(f"ReThinking discovery: {result['status']}")
        print(f"instruction files: {len(files)}")
        for f in findings: print(f"- {f['path']}: {f['signal']}")

if __name__ == '__main__':
    main()
