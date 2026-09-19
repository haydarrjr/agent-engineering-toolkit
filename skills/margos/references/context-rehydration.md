# Context rehydration

KEEP_REF, KEEP_HEAD, and OMIT_REHYDRATABLE require deterministic recovery metadata.

Supported v1 methods are READ_FILE, REPEAT_REPO_SEARCH, READ_EVIDENCE_ARTIFACT, REPEAT_TEST, REPEAT_BUILD, REFETCH_PUBLIC_DOC, READ_CHILD_RESULT_STORE, HOST_TRANSCRIPT_HANDLE, and UNAVAILABLE.

UNAVAILABLE is not a compactable recovery path. Unknown or non-replayable items therefore stay KEEP_FULL.

Rehydration cannot silently repeat an external mutation. The v1 method set contains no remote-write or destructive replay method, every contract records may_repeat_external_effect=false, and recompute/refetch methods can require current authority/freshness checks.

Recovery is content-addressed. rehydrate_item verifies recovered text against content_sha256 and rejects mismatches. Rehydration is an execution mechanism, not a source of permission.
