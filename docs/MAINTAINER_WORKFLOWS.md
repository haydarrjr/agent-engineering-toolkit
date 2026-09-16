# Maintainer workflows

AET is structured around observable OSS maintenance work rather than one-off prompt files.

## Pull requests

Use Codex or another coding agent for bounded implementation, review assistance, affected-test selection, and release-note drafting. Human maintainers retain merge and release authority.

## Issues

Triage bug reports into reproducible defects, compatibility reports, documentation gaps, or feature requests. Prefer small issues with a concrete completion condition.

## Releases

Use source validation and reproducible package checks before tagging. Treat host installation and marketplace publication as separate evidence.

## Security

Keep public issue triage separate from private vulnerability handling. Never paste secrets or private downstream configuration into public debugging artifacts.

## Evidence to track

For ecosystem and maintenance reporting, track only real public signals: stars, forks, contributors, external issues/PRs, release downloads where available, installations where a host exposes them, and maintainer activity such as triage/review/release work. Never manufacture or infer adoption.
