# Codex adapter contract

Treat root `plugin.json` and `skills/` as portable authority. `.codex-plugin/plugin.json` is a Codex compatibility/presentation adapter and must reconcile identity, version, description, homepage, repository, and license without overriding portable `keywords`.

For repository distribution, keep the Codex catalog at `.agents/plugins/marketplace.json`. A moving development catalog may point at the repository URL plus `ref: main`; release catalogs should use an immutable tag or commit when a release workflow explicitly renders one.

Codex host-specific subagent/model behavior belongs in the relevant skill reference, not in portable manifest fields. A source declaration never proves the effective model, reasoning level, subagent availability, installation, or runtime execution.

Adapter success proves only source consistency. Installation, marketplace acceptance, host discovery, and live readback require their own evidence.
