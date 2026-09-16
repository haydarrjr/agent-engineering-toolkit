# Codex adapter contract

Treat root `plugin.json` as the portable authority. For new portable packages, prefer OpenAI-specific presentation and lifecycle settings under `extensions.com.openai`; `.codex-plugin/plugin.json` remains a compatibility fallback.

Root owns portable identity and metadata, including `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, and `keywords`. Do not redeclare `keywords` in the Codex compatibility overlay when root `plugin.json` exists. Any compatibility identity fields that must remain in the overlay must reconcile with the root manifest rather than define a competing value.

Adapter success proves only source consistency; installation, marketplace acceptance, and host discovery require separate evidence.
