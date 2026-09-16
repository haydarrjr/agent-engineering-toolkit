# Architecture decisions

Identify the behavior owner before introducing an abstraction. Keep canonical state and authority in one place; adapters translate rather than duplicate policy. Prefer the smallest boundary that makes the requested change testable and reversible. Record durable decisions: owner, inputs/outputs, failure behavior, compatibility constraint, and why the seam fits.
