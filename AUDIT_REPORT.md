# PentAGI audit — 13 October 2026

Reviewed the current fork (`07309c4`) and local changes. This report separates
confirmed runtime defects from test-environment limitations. It is not a
claim that every possible bug in the repository has been found.

## Confirmed defects and fixes

| Area | Before | After | Evidence |
| --- | --- | --- | --- |
| Startup cancellation | Worker construction replaced the preparation context with a background context. A Stop arriving during registration could be ignored and the first turn could run anyway. | Preserve the preparation context, check it after registration, stop the unused worker, and use it for submitting the initial turn. | `TestAssistant_CancelledPreparationCannotStartItsFirstTurn` failed before the fix and passed afterward. |
| Muse streaming completion | The bridge kept reading after `response.completed` or `response.incomplete`. An upstream connection kept alive after that event delayed `[DONE]` and readiness. | Return immediately after emitting the terminal chunk; closing the upstream response releases the connection. | A synthetic stream raises if read past completion. The regression failed before the fix and passed afterward. |
| Installer packaging | The base Compose descriptor mounted gateway Python scripts that the stock installer does not embed or extract. | Put the gateway service in `docker-compose.override.yml`; the normal base descriptor remains compatible with installer packaging. | The stack-integrity test detected the extra unpackaged mounts before the move and passed afterward. Effective local Compose configuration remains valid. |
| File-tool writes | Host `filepath` semantics were used for Linux container paths; directory-shaped names could reach Docker, with directory-to-file replacement enabled. | Use POSIX container paths, reject directory targets before Docker access, emit a regular-file archive entry, and disable replacing a directory with a file. | Directory-target regression cases failed before the fix. Tests also check the exact destination and overwrite option. |
| Turn context cleanup | Each turn created a cancelable context without canceling it on normal completion. Parent contexts could retain completed children. | Defer cancellation at the end of every turn. | Code-path review; the controller lifecycle suite covers normal completion and interruption. |

## Test portability corrections

The report golden fixture and shared version table used CRLF-sensitive
comparisons. Normalize line endings in those test readers; the report content
and production version rules are unchanged. Their package tests passed afterward.

## Verification and limits

- Frontend source suite: **107 test files, 2,429 tests passed** with two workers.
  The first more concurrent run had two timeouts; both passed in isolation and
  the full lower-concurrency run passed. No test timeout was loosened.
- Gateway unit tests: **9 passed**, including terminal-event completion.
- The broad native Windows backend run recorded **7,117 passing tests/subtests**,
  but was **not fully green**: 14 packages had failures. Many depend on SQLite
  with CGO, POSIX paths/permissions, Linux Docker bind paths, or Linux-specific
  error text. Native `CGO_ENABLED=0` is unsuitable for those SQLite fixtures.
- Generated the installer's embedded descriptors before checking packaging.
- Final controller, provider, GraphQL, installer-checker, file-tool, report and
  version package tests passed. The targeted installer stack-integrity test
  passed, and the Linux application cross-build and Docker image build succeeded.
- Deployed the rebuilt backend and restarted the gateway after verifying that
  no assistant requests were active. HTTPS returned 200, gateway health returned
  `ok`, and the running backend image ID matched the freshly built image.

The local deletion of `backend/pkg/tools/searchers/testdata/sploitus_result_nginx.json`
predates this audit and was preserved. It is not included in the audit fixes.

## Operational notes

Docker and PentAGI are running with these local audit fixes. The gateway and
database are healthy. Conversation history and database volumes were preserved.
These audit fixes and the Markdown code-block copy button are included in the
fork update. The copy button passed six Markdown tests, focused lint, and the
production frontend build. This audit does not change provider credentials or
Windows memory settings.
