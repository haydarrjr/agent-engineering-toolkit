# External effects

Before a destructive, production, credentialed, irreversible, remote-write, or externally visible mutation, confirm that the current task authorizes it. After an authorized effect, read back the authoritative state.

An ambiguous prior mutation outcome is a deterministic `HALT` condition. Reflex cannot downgrade it, and MARGOS must not blind-retry until authoritative reconciliation resolves what happened.
