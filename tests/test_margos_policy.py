import importlib.util, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'skills/margos/scripts/margos_decide.py'
spec=importlib.util.spec_from_file_location('margos_decide',SCRIPT)
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

def state(**updates):
    value={
      'task':{'objective':'inspect parser','task_kind':'ENGINEERING','mutation_kind':'READ_ONLY','requested_outcome':'report','verification_obligation':'evidence-backed answer'},
      'host':{'host_id':'fixture','subagents_proven':True,'per_child_model_control_proven':True,'reasoning_control_proven':True,'concurrency_proven':True,'isolation_proven':True,'available_compute_classes':['ECONOMY_READ','BALANCED_EXEC','FRONTIER_REASONING']},
      'authority':{'explicit_model_provider_constraint':None,'remote_write_authorized':False,'destructive_or_production_authorized':False,'unresolved_external_effect':False},
      'work_shape':{'obligation_count':2,'overlapping_write_scopes':False,'shared_state':False,'parallel_safe':True},
      'evidence':{'verification_failed':False,'conflicting_sources':False,'unresolved_ambiguity':False,'cross_system_impact':False,'high_impact_correctness_or_security':False},
      'budget':{'max_children':2,'max_escalations':1,'cost_class':'NORMAL','latency_class':'NORMAL'},
    }
    for section,patch in updates.items(): value[section].update(patch)
    return value

def choice(value, options, winner=.8):
    rest=(1-winner)/(len(options)-1)
    return {'value':value,'probabilities':{x:(winner if x==value else rest) for x in options}}

def answers(coord='TRANSFER',compute='ECONOMY_READ',escalation=.1,critic=.1,transfer=.9):
    return {
      'coordination_preference':choice(coord,[x.value for x in mod.Coordination]),
      'compute_preference':choice(compute,[x.value for x in mod.ComputeTier]),
      'task_ambiguity':choice('LOW',['LOW','MODERATE','HIGH','SEVERE']),
      'verification_risk':choice('LOW',['LOW','MEDIUM','HIGH','CRITICAL']),
      'needs_escalation':{'probability':escalation},
      'needs_independent_critic':{'probability':critic},
      'transfer_sufficient':{'probability':transfer},
    }

class MargosPolicyTests(unittest.TestCase):
    def test_unresolved_external_effect_halts(self):
        receipt=mod.decide(state(authority={'unresolved_external_effect':True}))
        self.assertEqual(receipt['selected']['disposition'],'HALT')
        self.assertIn('MARGOS-POL-001',{r['rule_id'] for r in receipt['policy_rules_applied']})

    def test_missing_subagent_capability_falls_back_direct(self):
        receipt=mod.decide(state(host={'subagents_proven':False}))
        self.assertEqual(receipt['selected']['disposition'],'FALLBACK_DIRECT')
        self.assertEqual(receipt['selected']['coordination'],'DIRECT')

    def test_overlapping_writes_remove_delegated(self):
        pre=mod.policy_pre_evaluate(state(work_shape={'overlapping_write_scopes':True}))
        self.assertNotIn('DELEGATED',pre['admissible']['coordination'])
        self.assertIn('SERIALIZED',pre['admissible']['coordination'])

    def test_mutation_cannot_use_economy_read(self):
        pre=mod.policy_pre_evaluate(state(task={'mutation_kind':'LOCAL_WRITE'}))
        self.assertNotIn('ECONOMY_READ',pre['admissible']['compute'])

    def test_length_keywords_and_model_name_do_not_change_policy(self):
        a=mod.policy_pre_evaluate(state(task={'objective':'x'}))
        b=mod.policy_pre_evaluate(state(task={'objective':'research GPT-999 '+('x'*20000)}))
        self.assertEqual(a['admissible'],b['admissible'])

    def test_failed_verification_policy_fallback_uses_frontier(self):
        self.assertEqual(mod.decide(state(evidence={'verification_failed':True}))['selected']['compute'],'FRONTIER_REASONING')

    def test_explicit_model_constraint_is_preserved(self):
        receipt=mod.decide(state(authority={'explicit_model_provider_constraint':'provider-X/model-Y'}))
        self.assertEqual(receipt['selected']['model_provider_constraint'],'provider-X/model-Y')

    def test_reflex_cannot_choose_policy_inadmissible_route(self):
        provider=mod.FixtureReflexProvider(answers(coord='DELEGATED'))
        receipt=mod.decide(state(work_shape={'overlapping_write_scopes':True}),provider)
        self.assertEqual(receipt['provider']['status'],'ERROR')
        self.assertEqual(receipt['selected']['coordination'],'DIRECT')

    def test_compute_and_critic_are_separate_dimensions(self):
        receipt=mod.decide(state(),mod.FixtureReflexProvider(answers(escalation=.9,critic=.9)))
        self.assertEqual(receipt['selected']['compute'],'FRONTIER_REASONING')
        self.assertEqual(receipt['selected']['role'],'INDEPENDENT_CRITIC')

    def test_low_margin_abstains(self):
        a=answers(); a['coordination_preference']={'value':'TRANSFER','probabilities':{'DIRECT':.42,'TRANSFER':.43,'DELEGATED':.10,'SERIALIZED':.05}}
        receipt=mod.decide(state(),mod.FixtureReflexProvider(a))
        self.assertEqual(receipt['selected']['source'],'LOW_MARGIN_FALLBACK')
        self.assertTrue(receipt['selected']['abstained'])

    def test_receipt_is_proposed_not_execution_proof(self):
        receipt=mod.decide(state())
        self.assertEqual(receipt['decision_authority'],'PROPOSED')
        self.assertEqual(receipt['host_execution']['status'],'PENDING')
        self.assertEqual(len(receipt['state_sha256']),64)
        self.assertEqual(len(receipt['question_set_sha256']),64)

if __name__=='__main__': unittest.main()
