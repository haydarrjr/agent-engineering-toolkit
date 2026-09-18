# MARGOS vNext research basis

MARGOS vNext turns routing into an explicit decision problem instead of relying only on whichever root model reads the orchestration prompt.

## Jev / System One inspiration

TypeSafe AI's Jev exposes typed Choice, Score, and Noul judgments over shared state and returns uncertainty information rather than free-form prose. MARGOS adopts the architectural idea, not the proprietary model/training stack.

Primary references:
- TypeSafe introduction: https://docs.typesafe.ai/introduction
- Primitives: https://docs.typesafe.ai/primitives
- Confidence: https://docs.typesafe.ai/confidence
- API: https://docs.typesafe.ai/api
- Agent skill: https://docs.typesafe.ai/agent-skill

## Routing and cascades

- Chen, Zaharia, Zou, *FrugalGPT* (2023): https://arxiv.org/abs/2305.05176
- Ding et al., *Hybrid LLM* (ICLR 2024): https://proceedings.iclr.cc/paper_files/paper/2024/hash/b47d93c99fa22ac0b377578af0a1f63a-Abstract-Conference.html
- Ong et al., *RouteLLM* (2024): https://arxiv.org/abs/2406.18665
- Hu et al., *RouterBench* (2024): https://arxiv.org/abs/2403.12031
- Aggarwal et al., *AutoMix* (2023): https://arxiv.org/abs/2310.12963

These motivate evaluating routing as a cost/quality/verification trade-off rather than defaulting to maximum compute.

## Adaptive compute

- Schuster et al., *CALM* (2022): https://arxiv.org/abs/2207.07061
- Jeong et al., *Adaptive-RAG* (NAACL 2024): https://aclanthology.org/2024.naacl-long.389/

MARGOS therefore uses evidence and verification state instead of prompt length, file count, or model-brand words as primary escalation signals.

## Calibration and uncertainty

- Guo et al., *On Calibration of Modern Neural Networks* (ICML 2017): https://arxiv.org/abs/1706.04599
- Gupta et al., *Language Model Cascades: Token-Level Uncertainty and Beyond* (ICLR 2024): https://proceedings.iclr.cc/paper_files/paper/2024/hash/11f5520daf9132775e8604e89f53925a-Abstract-Conference.html
- Ulmer et al., *APRICOT* (ACL 2024): https://aclanthology.org/2024.acl-long.824/
- Farquhar et al., *Detecting Hallucinations Using Semantic Entropy* (Nature 2024): https://www.nature.com/articles/s41586-024-07421-0

AET therefore records provider probability separately from local calibration status and downstream verification outcome.

## Abstention and deferral

- Geifman & El-Yaniv, *SelectiveNet* (ICML 2019): https://proceedings.mlr.press/v97/geifman19a.html
- Mozannar & Sontag, *Learning to Defer to an Expert* (ICML 2020): https://arxiv.org/abs/2006.01862
- Zellinger et al., *Cost-Saving LLM Cascades with Early Abstention* (2025): https://arxiv.org/abs/2502.09054

MARGOS treats abstention, direct fallback, halt, escalation, and independent criticism as legitimate outcomes.

## Multi-agent boundaries

- Yao et al., *ReAct* (ICLR 2023): https://arxiv.org/abs/2210.03629
- Wang et al., *Mixture-of-Agents* (2024): https://arxiv.org/abs/2406.04692
- Tran et al., multi-agent collaboration survey (2025): https://arxiv.org/abs/2501.06322

The design conclusion is intentionally conservative: more children are not automatically better. Delegation needs bounded ownership, host capability evidence, and a measurable reason.
