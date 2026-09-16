# Security policy

## Supported versions

Security fixes target the latest released major version and `main` unless a release note says otherwise.

## Reporting

Please use GitHub's private vulnerability reporting when available. Do not disclose credentials, tokens, private endpoints, exploit details, or sensitive host information in a public issue.

## Security boundaries

AET is source tooling. Repository-local validators must not collect telemetry, transmit repository content, install dependencies, publish packages, mutate live hosts, or read credentials unless a future feature explicitly documents and isolates that behavior.

The repository rejects common secret-bearing file names and user-specific private state in its own release validation. A green source validation result is not a security certification of downstream repositories.
