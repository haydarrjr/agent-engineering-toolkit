#!/usr/bin/env python3
"""Frozen MARGOS routing benchmark for Policy, fixture Reflex, or live Jev Reflex."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/margos/scripts'))
import margos_decide as core
import margos_reflex_jev as jev

def _choice(value, options, winner=.86):
    if len(options)==1: return {"value":value,"probabilities":{value:1.0}}
    rest=(1-winner)/(len(options)-1)
    return {"value":value,"probabilities":{x:(winner if x==value else rest) for x in options}}

def _fixture_answers(case):
    f=case["fixture"]
    return {
      "coordination_preference":_choice(f["coordination"],[x.value for x in core.Coordination]),
      "compute_preference":_choice(f["compute"],[x.value for x in core.ComputeTier]),
      "task_ambiguity":_choice("LOW",["LOW","MODERATE","HIGH","SEVERE"]),
      "verification_risk":_choice("LOW",["LOW","MEDIUM","HIGH","CRITICAL"]),
      "needs_escalation":{"probability":float(f["escalation"])},
      "needs_independent_critic":{"probability":float(f["critic"])},
      "transfer_sufficient":{"probability":float(f["transfer"])},
    }

def _matches(selected,gold):
    return all(selected.get(k)==v for k,v in gold.items())

def _brier(probs,gold):
    return sum((float(p)-(1.0 if label==gold else 0.0))**2 for label,p in probs.items())

def run_suite(document, mode):
    rows=[]; calibration=[]; groups={}
    provider_live=jev.JevReflexProvider() if mode=="jev" else None
    for case in document["cases"]:
        provider=None
        if mode=="fixture": provider=core.FixtureReflexProvider(_fixture_answers(case))
        elif mode=="jev": provider=provider_live
        receipt=core.decide(case["state"],provider)
        selected=receipt["selected"]; passed=_matches(selected,case["gold"])
        hard_violation=selected["disposition"]!="HALT" and (
            selected["coordination"] not in receipt["admissible"]["coordination"] or
            selected["compute"] not in receipt["admissible"]["compute"] or
            selected["role"] not in receipt["admissible"]["roles"]
        )
        rows.append({"id":case["id"],"pass":passed,"hard_violation":hard_violation,"provider_status":receipt["provider"].get("status"),"selected":selected,"gold":case["gold"]})
        if case.get("equivalence_group"):
            groups.setdefault(case["equivalence_group"],[]).append((selected["disposition"],selected["coordination"],selected["compute"],selected["role"]))
        answers=receipt["reflex"]["answers"]
        for qid,gold_key in (("coordination_preference","coordination"),("compute_preference","compute")):
            if qid in answers and case["gold"].get(gold_key) is not None:
                probs=answers[qid]["probabilities"]; confidence=max(probs.values())
                correct=answers[qid]["value"]==case["gold"][gold_key]
                calibration.append((confidence,correct,_brier(probs,case["gold"][gold_key])))
    invariance_failures=[group for group,values in groups.items() if len(set(values))>1]
    bins=[[] for _ in range(5)]
    for confidence,correct,brier in calibration:
        bins[min(4,int(confidence*5))].append((confidence,correct))
    ece=0.0
    for items in bins:
        if items:
            avg_c=sum(x[0] for x in items)/len(items); avg_a=sum(1.0 if x[1] else 0.0 for x in items)/len(items)
            ece+=len(items)/max(1,len(calibration))*abs(avg_c-avg_a)
    report={
      "schema_version":"margos-benchmark/v1",
      "suite_id":document.get("suite_id"),
      "mode":mode,
      "case_count":len(rows),
      "passed":sum(r["pass"] for r in rows),
      "hard_boundary_violations":sum(r["hard_violation"] for r in rows),
      "abstentions":sum(bool(r["selected"].get("abstained")) for r in rows),
      "equivalence_invariance_failures":invariance_failures,
      "calibration":{"samples":len(calibration),"brier_mean":(sum(x[2] for x in calibration)/len(calibration) if calibration else None),"ece_5_bin":(ece if calibration else None),"status":"MEASURED_FIXTURE_ONLY" if mode=="fixture" else ("LIVE_UNCALIBRATED" if mode=="jev" else "NOT_APPLICABLE")},
      "cases":rows,
    }
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dataset",type=Path,default=ROOT/"tests/fixtures/margos/routing-cases-v1.json")
    ap.add_argument("--mode",choices=("policy","fixture","jev"),default="fixture")
    ap.add_argument("--output",type=Path)
    ap.add_argument("--strict",action="store_true")
    args=ap.parse_args()
    document=json.loads(args.dataset.read_text(encoding="utf-8"))
    report=run_suite(document,args.mode)
    rendered=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.output: args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(rendered,encoding="utf-8")
    else: print(rendered,end="")
    if report["hard_boundary_violations"] or report["equivalence_invariance_failures"]: return 1
    if args.strict and report["passed"]!=report["case_count"]: return 1
    return 0

if __name__=="__main__": raise SystemExit(main())
