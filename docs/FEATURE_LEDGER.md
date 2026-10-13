# Fork integration ledger

Each feature is a separate stacked branch. Java counterparts are in painframe/jadx-ai-mcp.

## 01 analysis-test-fixtures

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986, tests/fixtures and integration fixture expectations.
- Adaptation: preserve the small original APK/JAR archives, pin SHA256 checksums, test ZIP integrity and expected payloads, and enforce baseline MCP tool preservation through real FastMCP discovery. Avoid donor endpoint assumptions.
- Validation: Python unittest suite, import smoke, Ruff and Bandit for added test code.
- Limits: archive integrity and tool discovery do not prove APK runtime behavior; live paired integration follows each feature.

## 02 python-packaging

- Donor: mugiwarix/jadx-mcp-server @ 9ffc764e682792605b6b1657008e5724d9b6322e, setuptools package discovery.
- Adaptation: standard setuptools build backend; explicitly include existing src namespace packages, align script/project Python minimum with approved 3.13 and lockfile. No Nix dependency.
- Validation: build wheel, install into isolated Python3.13 environment, import module and run console --help outside checkout; existing unittest suite.
- Limits: installation verified on Linux only.

## 03 structured-error-contract

- Donor: ai-repo-save/jadx-mcp-server @ 2636d049d57649f0dfb80c054f882a827611116c.
- Adaptation: shared GET/POST decoder preserves error strings and successful objects/lists; adds code, retryability, source, endpoint and status. Raw HTML error bodies are omitted. Legacy plain text remains under response. JSON null/scalars and malformed pagination become typed errors. Existing long search timeout overrides remain.
- Validation: 9 unittest cases (GET/POST error parity, null JSON, legacy text, no malformed pagination dispatch, malformed result shapes, error-body omission, baseline tests), import smoke, Ruff and Bandit on all changed Python files.
- Limits: mock HTTP contract tests do not prove running Java plugin behavior.

## 04 transport-resilience

- Donor: ai-repo-save/jadx-mcp-server @ 2636d049d57649f0dfb80c054f882a827611116c.
- Adaptation: five-second connection/pool deadline, caller-selected read timeout (including 3600-second searches), overall deadline of read+connection allowance, bounded three-second per-backend connection-failure cooldown. HTTP errors/read timeouts do not disable unrelated operations; cancellation propagates and mutations are never retried. Health/progress share failure tracking.
- Validation: 13 unittest cases including timeout extensions, cancellation, backend isolation and 404 cooldown exclusion; changed-file Ruff/Bandit and import smoke.
- Limits: process-local cooldown; no application retry or Java cancellation guarantee.

## 05 search-patterns

- Donors: odell0111/jadx-ai-mcp @ 951d6d964ae194a45bd4735bd8839d455d0607ba (matching contract); ngkz/jadx-mcp-server @ 3878515e039fb088ef5f4bb45a49ef52fa318efb (regex parameter plumbing).
- Adaptation: additive regex and case_sensitive flags default false; preserve the expression verbatim and use lowercase boolean query values. Actual FastMCP calls verify forwarding and defaults. Module-level registration imports replace duplicate unused function imports; rejected progress notifications are debug logged.
- Validation: 19 unittest cases; Ruff/Bandit clean on all changed Python files; import exercised by MCP tests.
- Limits: execution deadlines and pattern evaluation live in the paired Java PR; older plugins ignore flags and cannot provide these search semantics.

## 07 analysis-metadata

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- New MCP tools get_class_info and get_method_signature call class-info/method-signature; descriptor remains nullable and optional. Responses preserve Java metadata, overload lists and Frida names.
- Validation: 20 unittest cases including actual MCP metadata dispatch and nullable schemas; changed-file Ruff/Bandit/import pass.
- Limits: requires paired Java routes; backend metadata correctness covered there, not by wrapper mocks.

## 08 native-method-search

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- New search_native_methods MCP tool forwards package and validated offset/count to search-native-methods, normalizing method items through existing pagination.
- Validation: 21 unittest cases including paginated dispatch and invalid pagination no-dispatch through actual MCP; changed-file Ruff/Bandit clean.
- Limits: declaration discovery does not analyze native implementation binaries; requires paired Java route.

## 09 human-method-signatures

- Donors: ngkz/jadx-ai-mcp @ e8d11033a6751f0174ad7b4b00a886d9d3df972d and included MrWeigx signature changes.
- Adaptation: advertise human signatures alongside existing JVM descriptors; forward exact strings and renamed identifiers through existing tools without a duplicate Python parser. Preserve backend ambiguity diagnostics and nullable arguments.
- Validation: 22 unittest cases, including actual MCP rename with a human signature and unchanged overload error payload; changed-file Ruff/Bandit clean.
- Limits: parsing and original/alias lookup require the paired Java feature. This bridge does not guess overloads.
