# Decision model

Delegate only when work is independently useful, scopes do not conflict, the host can actually run the child, and reconciliation cost is lower than doing the work directly. Define one writer per mutable scope. Parallel reads are usually safer than parallel writes.
