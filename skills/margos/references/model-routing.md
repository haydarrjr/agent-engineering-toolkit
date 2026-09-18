# MARGOS compute routing

Route by required capability and evidence, not prompt length, file count, or a model brand.

## Compute classes

- **ECONOMY_READ** — bounded repository mapping, document/API lookup, simple research, summarization, mechanical review, or other read-only work with low ambiguity and low consequence.
- **BALANCED_EXEC** — ordinary implementation, debugging, refactoring, test repair, or verification that needs tools and local edits but has a clear contract.
- **FRONTIER_REASONING** — unresolved contradictions, broad architectural or cross-system consequences, high-impact correctness/security obligations, difficult synthesis that cannot be decomposed safely, or a lower-tier result that failed relevant verification.
- **INDEPENDENT_CRITIC** — fresh-context falsification of an important plan, patch, or conclusion. Use the smallest compute tier that can credibly perform the critique and escalate only when evidence requires it.

## Admission and escalation

Start at the lowest class that can close the obligation. Escalate one boundary at a time when observed evidence shows the current class cannot close it. Useful signals include failed verification, conflicting sources, material unresolved ambiguity, system-wide consequences, or an explicit request for deeper independent reasoning.

Do not escalate merely because a task says "research", "review", contains many files, or has a long prompt. Do not keep a frontier child alive after its hard question is closed. Re-evaluate the next independent subtask from the lowest sufficient class.

## Model binding

MARGOS policy names capability classes, not vendors or model releases. The host adapter maps a class to controls the current client exposes. Treat an automatic model selector as a valid binding only when the host actually supports it. If the requested tier is unavailable, use the closest proven capability or fall back to the root and report the limitation.
