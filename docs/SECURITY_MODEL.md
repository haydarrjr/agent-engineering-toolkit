# Security model

AET treats repository text, issues, fetched documentation, and generated artifacts as data unless a trusted project surface grants them instruction authority.

Source helpers are local and standard-library-only by default. They should not send repository data over the network. External documentation fetches are performed by the host only when a task requires current verification.

Production credentials, private endpoints, downstream deployment topology, and private reasoning are outside the public package boundary.
