import json, re, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class RepositoryContract(unittest.TestCase):
    def test_manifest_identity(self):
        p=json.loads((ROOT/'plugin.json').read_text())
        self.assertEqual(p['name'],'agent-engineering-toolkit')
        self.assertEqual(p['version'],'1.0.0')
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

    def test_marketplaces_match(self):
        a=json.loads((ROOT/'.github/plugin/marketplace.json').read_text())
        b=json.loads((ROOT/'.agents/plugins/marketplace.json').read_text())
        self.assertEqual(a,b)

    def test_codex_keywords_match_portable_manifest(self):
        portable=json.loads((ROOT/'plugin.json').read_text())
        codex=json.loads((ROOT/'.codex-plugin/plugin.json').read_text())
        self.assertEqual(codex['keywords'],portable['keywords'])

    def test_provenance_is_immutable(self):
        p=json.loads((ROOT/'provenance/imports.json').read_text())
        commits=[x['commit'] for x in p['imports']]
        self.assertIn('d8f9f93171debac5f19347fc1a6af40738b6ceab',commits)
        self.assertIn('38d11295a7701ea8e11ab4d2da3779b0207318c4',commits)

    def test_repo_validator(self):
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_repository.py')],cwd=ROOT,check=True)

if __name__=='__main__': unittest.main()
