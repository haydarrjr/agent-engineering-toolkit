# Report schema

For machine-readable audit output, prefer a JSON object with: `status`, `mode`, `plugin_root`, `checks`, `warnings`, `errors`, `changed_surfaces`, and `evidence_boundary`. Use `PASS`, `FAIL`, or `UNVERIFIED`; do not turn unknown external state into PASS.
