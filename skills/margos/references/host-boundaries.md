# Host and profile boundaries

Configuration describes an intended role; it does not prove that the host ran it. Before delegation, check the effective subagent, model-selection, reasoning, tool, sandbox, network, isolation, and concurrency capabilities the host actually reports.

Keep the root session, approval policy, global sandbox, connectors, credentials, and marketplace state unchanged unless the user explicitly asks to change that owned configuration. A root model selected in the UI is the parent session choice, not automatically a prohibition on cheaper or stronger children. By contrast, an instruction such as "use model X for all work" or "review this with provider Y" is an explicit routing constraint and must be preserved.

Reflex output is never host-capability evidence. A probabilistic preference cannot prove that a child, model tier, tool, network boundary, or concurrency primitive exists.

For a requested profile/configuration change, inspect owned state, plan the smallest create/replace/no-op/conflict result, obtain any confirmation required for that mutation, apply only the requested scope, then verify readback. Never infer capability from a profile, manifest, model label, previous success, or route receipt alone.
