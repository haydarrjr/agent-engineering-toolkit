import re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MARGOS=ROOT/'skills/margos'
COPILOT=ROOT/'com.github.copilot/agents'

def frontmatter(path):
    text=path.read_text(encoding='utf-8')
    m=re.match(r'^---\n(.*?)\n---\n',text,re.S)
    if not m: raise AssertionError(f'missing frontmatter: {path}')
    return m.group(1)

class MargosHostAdapterTests(unittest.TestCase):
    def test_root_policy_is_provider_agnostic(self):
        text=(MARGOS/'SKILL.md').read_text(encoding='utf-8').lower()
        for signal in ('gpt-','claude','anthropic','gemini'): self.assertNotIn(signal,text)
        self.assertIn('host-native subagents',text)
        self.assertIn('never requires an mcp server',text)

    def test_compute_classes_and_evidence_escalation(self):
        text=(MARGOS/'references/model-routing.md').read_text(encoding='utf-8')
        for token in ('ECONOMY_READ','BALANCED_EXEC','FRONTIER_REASONING','INDEPENDENT_CRITIC'): self.assertIn(token,text)
        self.assertIn('failed verification',text.lower())
        self.assertIn('Do not escalate merely because',text)

    def test_host_references_preserve_evidence_boundary(self):
        codex=(MARGOS/'references/host-codex.md').read_text(encoding='utf-8').lower()
        copilot=(MARGOS/'references/host-copilot.md').read_text(encoding='utf-8').lower()
        self.assertIn('native subagent',codex)
        self.assertIn('mcp server',codex)
        self.assertIn('com.github.copilot/agents',copilot)
        self.assertIn('model: auto',copilot)

    def test_copilot_agents_are_hidden_auto_model_leaf_agents(self):
        paths=sorted(COPILOT.glob('*.agent.md'))
        self.assertEqual({p.name for p in paths},{'margos-scout.agent.md','margos-worker.agent.md','margos-verifier.agent.md','margos-critic.agent.md'})
        for p in paths:
            fm=frontmatter(p)
            self.assertRegex(fm,re.compile(r'^model:\s*auto\s*$',re.M),msg=p.name)
            self.assertRegex(fm,re.compile(r'^user-invocable:\s*false\s*$',re.M),msg=p.name)
            tools=re.search(r'^tools:\s*\[(.*?)\]\s*$',fm,re.M)
            self.assertIsNotNone(tools,p.name)
            self.assertNotIn('agent',{x.strip().lower() for x in tools.group(1).split(',')})

    def test_no_mcp_runtime_is_added(self):
        self.assertFalse((ROOT/'mcp.json').exists())

if __name__=='__main__': unittest.main()
