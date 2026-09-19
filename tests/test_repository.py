import json, re, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class RepositoryContract(unittest.TestCase):
    def test_manifest_identity(self):
        p=json.loads((ROOT/'plugin.json').read_text())
        self.assertEqual(p['name'],'agent-engineering-toolkit')
        self.assertEqual(p['version'],'1.2.0')
        self.assertEqual(p['license'],'Apache-2.0')

    def test_five_skills(self):
        names=sorted(p.name for p in (ROOT/'skills').iterdir() if p.is_dir())
        self.assertEqual(names,sorted(['software-craft','python-engineering-harness','margos','rethinking','agent-plugins-author']))

    def test_activation_policy(self):
        for name in ['margos','rethinking','agent-plugins-author']:
            text=(ROOT/'skills'/name/'agents/openai.yaml').read_text()
            self.assertRegex(text,r'allow_implicit_invocation:\s*false')
        for name in ['software-craft','python-engineering-harness']:
            text=(ROOT/'skills'/name/'agents/openai.yaml').read_text()
            self.assertRegex(text,r'allow_implicit_invocation:\s*true')

    def test_marketplaces_are_client_specific(self):
        portable=json.loads((ROOT/'plugin.json').read_text())
        copilot=json.loads((ROOT/'.github/plugin/marketplace.json').read_text())
        codex=json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
        self.assertNotEqual(copilot,codex)
        self.assertEqual(copilot['plugins'][0]['version'],portable['version'])
        self.assertTrue(copilot['plugins'][0]['strict'])
        self.assertEqual(copilot['plugins'][0]['source'],'.')
        self.assertEqual(codex['plugins'][0]['source']['source'],'url')
        self.assertEqual(codex['plugins'][0]['source']['ref'],'main')

    def test_codex_keywords_owned_by_portable_manifest(self):
        portable=json.loads((ROOT/'plugin.json').read_text())
        codex=json.loads((ROOT/'.codex-plugin/plugin.json').read_text())
        self.assertIn('keywords',portable)
        self.assertNotIn('keywords',codex)
        self.assertIn('orchestration',portable['keywords'])
        self.assertIn('copilot',portable['keywords'])

    def test_provenance_keeps_baseline_and_v11_source(self):
        p=json.loads((ROOT/'provenance/imports.json').read_text())
        self.assertEqual(p['generated_for_release'],'1.2.0')
        commits=[x['commit'] for x in p['imports']]
        self.assertIn('d8f9f93171debac5f19347fc1a6af40738b6ceab',commits)
        self.assertIn('2346885855e074cdb52f543b5e466c4dfd3de307',commits)
        self.assertIn('38d11295a7701ea8e11ab4d2da3779b0207318c4',commits)

    def test_readme_exposes_ci_badge(self):
        text=(ROOT/'README.md').read_text()
        self.assertIn('actions/workflows/ci.yml/badge.svg',text)

    def test_repo_validator(self):
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_repository.py')],cwd=ROOT,check=True)

if __name__=='__main__': unittest.main()
