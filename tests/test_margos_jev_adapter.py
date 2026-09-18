import json, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/margos/scripts'
sys.path.insert(0,str(SCRIPTS))
import margos_decide as core
import margos_reflex_jev as jev

def state(**updates):
    value={
      'task':{'objective':'inspect parser','task_kind':'RESEARCH','mutation_kind':'READ_ONLY','requested_outcome':'report','verification_obligation':'evidence-backed answer'},
      'host':{'host_id':'private-host-name','subagents_proven':True,'per_child_model_control_proven':True,'reasoning_control_proven':True,'concurrency_proven':True,'isolation_proven':True,'available_compute_classes':['ECONOMY_READ','BALANCED_EXEC','FRONTIER_REASONING']},
      'authority':{'explicit_model_provider_constraint':'SECRET-PROVIDER/MODEL','remote_write_authorized':False,'destructive_or_production_authorized':False,'unresolved_external_effect':False},
      'work_shape':{'obligation_count':2,'overlapping_write_scopes':False,'shared_state':False,'parallel_safe':True},
      'evidence':{'verification_failed':False,'conflicting_sources':False,'unresolved_ambiguity':False,'cross_system_impact':False,'high_impact_correctness_or_security':False},
      'budget':{'max_children':2,'max_escalations':1,'cost_class':'NORMAL','latency_class':'NORMAL'},
    }
    for section,patch in updates.items(): value[section].update(patch)
    return value

def fake_response(payload):
    q=payload['questions']
    answers={}
    if 'coordination_preference' in q:
        opts=list(q['coordination_preference']['criteria'])
        answers['coordination_preference']={'choice':'TRANSFER' if 'TRANSFER' in opts else opts[0],'probabilities':{x:(.82 if x==('TRANSFER' if 'TRANSFER' in opts else opts[0]) else .18/(len(opts)-1)) for x in opts}}
    if 'compute_preference' in q:
        opts=list(q['compute_preference']['criteria'])
        pick='ECONOMY_READ' if 'ECONOMY_READ' in opts else opts[0]
        answers['compute_preference']={'choice':pick,'probabilities':{x:(.84 if x==pick else .16/(len(opts)-1)) for x in opts}}
    answers['task_ambiguity']={'score':0.1,'probabilities':{'0':.86,'1':.08,'2':.04,'3':.02}}
    answers['verification_risk']={'score':0.1,'probabilities':{'0':.88,'1':.07,'2':.03,'3':.02}}
    answers['needs_escalation']={'noul':.08}
    answers['needs_independent_critic']={'noul':.07}
    answers['transfer_sufficient']={'noul':.91}
    return {'model':'jev-1.13.0','answers':answers,'usage':{'input_tokens':321,'output_tokens':42}}

class JevAdapterTests(unittest.TestCase):
    def test_projection_minimizes_host_and_constraint_identity(self):
        pre=core.policy_pre_evaluate(state())
        projected=jev.project_reflex_state(core.build_reflex_request(pre))
        encoded=json.dumps(projected)
        self.assertNotIn('private-host-name',encoded)
        self.assertNotIn('SECRET-PROVIDER/MODEL',encoded)
        self.assertTrue(projected['authority']['explicit_model_provider_constraint_present'])

    def test_payload_uses_only_policy_admissible_choices(self):
        pre=core.policy_pre_evaluate(state(work_shape={'overlapping_write_scopes':True}))
        payload=jev.build_jev_payload(core.build_reflex_request(pre),core.QUESTION_SET)
        self.assertNotIn('DELEGATED',payload['questions']['coordination_preference']['criteria'])

    def test_policy_restricted_jev_result_still_validates(self):
        pre=core.policy_pre_evaluate(state(work_shape={'overlapping_write_scopes':True}))
        provider=jev.JevReflexProvider(api_key='test-key',transport=lambda b,k,p,t: fake_response(p))
        result=provider.evaluate(core.build_reflex_request(pre),core.QUESTION_SET)
        validated=core.validate_reflex_result(result,pre)
        self.assertEqual(validated['answers']['coordination_preference']['probabilities']['DELEGATED'],0.0)
        self.assertNotEqual(validated['answers']['coordination_preference']['value'],'DELEGATED')

    def test_adapter_maps_choice_score_and_noul(self):
        seen={}
        def transport(base,key,payload,timeout):
            seen.update({'base':base,'key':key,'payload':payload,'timeout':timeout})
            return fake_response(payload)
        pre=core.policy_pre_evaluate(state())
        provider=jev.JevReflexProvider(api_key='test-key',transport=transport)
        result=provider.evaluate(core.build_reflex_request(pre),core.QUESTION_SET)
        validated=core.validate_reflex_result(result,pre)
        self.assertEqual(validated['provider']['kind'],'typesafe-jev')
        self.assertEqual(validated['answers']['coordination_preference']['value'],'TRANSFER')
        self.assertEqual(validated['answers']['task_ambiguity']['value'],'LOW')
        self.assertAlmostEqual(validated['answers']['needs_escalation']['probability'],.08)
        self.assertEqual(seen['base'],'https://api.typesafe.ai')
        self.assertEqual(seen['key'],'test-key')

    def test_missing_key_falls_back_without_network(self):
        called=False
        def transport(*args):
            nonlocal called; called=True
            raise AssertionError('network should not run')
        receipt=core.decide(state(),jev.JevReflexProvider(api_key='',transport=transport))
        self.assertFalse(called)
        self.assertEqual(receipt['provider']['status'],'ERROR')
        self.assertEqual(receipt['selected']['coordination'],'DIRECT')
        self.assertTrue(receipt['selected']['abstained'])

    def test_transport_error_is_bounded(self):
        def transport(*args):
            raise jev.JevAdapterError('synthetic failure')
        receipt=core.decide(state(),jev.JevReflexProvider(api_key='test-key',transport=transport))
        self.assertEqual(receipt['provider']['kind'],'typesafe-jev')
        self.assertEqual(receipt['provider']['status'],'ERROR')
        self.assertEqual(receipt['selected']['coordination'],'DIRECT')

    def test_reflex_assisted_decision_preserves_user_constraint(self):
        provider=jev.JevReflexProvider(api_key='test-key',transport=lambda b,k,p,t: fake_response(p))
        receipt=core.decide(state(),provider)
        self.assertEqual(receipt['selected']['coordination'],'TRANSFER')
        self.assertEqual(receipt['selected']['compute'],'ECONOMY_READ')
        self.assertEqual(receipt['selected']['role'],'SCOUT')
        self.assertEqual(receipt['selected']['model_provider_constraint'],'SECRET-PROVIDER/MODEL')
        self.assertEqual(receipt['host_execution']['status'],'PENDING')

if __name__=='__main__': unittest.main()
