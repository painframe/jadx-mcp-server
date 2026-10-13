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
- Limits: execution deadlines and pattern evaluation live in the paired Java PR; older plugins lacking the search_options acknowledgment return unsupported_capability for opt-in flags.

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

## 10 response-continuations

- Donors: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986, mugiwarix/jadx-mcp-server @ 9ffc764e682792605b6b1657008e5724d9b6322e.
- Adaptation: nullable max_bytes/cursor on source, smali and resource tools; validate finite bounds and require backend continuation acknowledgment. Default complete response shapes unchanged. Do not number partial source lines or truncate identifiers locally.
- Security check found existing untrusted XML parser: added defusedxml>=0.7.1 consistently to project/script/requirements, a 4MiB input bound and entity rejection test.
- Validation: 29 unittest cases including actual MCP Unicode content/cursor forwarding, unsupported older peers, malformed bounds and XML entity rejection; changed-file Ruff/Bandit clean.
- Limits: backend owns cursor integrity/project generations and actual chunk bounds. Java runtime tests are separate; output byte ceiling applies to content, not protocol metadata.

## 11 batch-analysis

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- New batch_analysis MCP tool accepts one of five analysis operations, 1..50 parameter objects, and bounded per-item content bytes. POST body is structured JSON; per-item success/error responses are preserved. Reject unknown parameters and invalid identifiers/pagination before dispatch.
- Validation: 31 unittest cases, actual FastMCP to HTTP mock verifies POST JSON and mixed outcomes; oversized/malformed batch rejection; changed-file Ruff/Bandit clean.
- Limits: total response may include fifty bounded contents plus metadata; Java owns execution and continuation.

## 12 bounded-analysis-caches

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- Adaptation: retain backend-owned caches and existing MCP controls; expose bounded-cache policy and project-generation metadata without duplicating cached state in Python. Existing clear_cache remains POST and forwards invalidation results.
- Validation: 32 unittest cases; real MCP-to-HTTP stats/clear test preserves metadata and checks HTTP mutation method. Changed-file Ruff/Bandit clean.
- Limits: Python does not claim cache eviction/invalidation correctness; paired Java tests verify cache implementation. No new Python cache is introduced.

## 13 apk-loading

- Donor: hnhcsl/jadx-mcp-server @ b4d4298c79f5ebefb044c9bbc70e27d54caf6ff5 (paired plugin @ 50781c0987f008703ee0f0c735b8e3efb611b5cd).
- Adaptation: open_apk(path, replace=False) POSTs absolute backend-host paths; get_project_operation polls loading/ready/failed rather than treating scheduling as successful loading. Preserve backend unsaved-project safeguards.
- Validation: 34 unittest cases, actual MCP/HTTP scheduling+poll state and default replace=False checks; invalid paths rejected; changed-file Ruff/Bandit clean.
- Limits: GUI loading, cache invalidation and unsaved-state correctness require paired Java execution.

## 14 search-coalescing

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- Adaptation: backend-owned shared search execution/result reuse; expose bounded exclude_packages CSV and require explicit acknowledgment when used. Carry partial, timed_out, search_id and warnings through existing pagination/progress. No duplicated Python result cache.
- Validation: 36 unittest cases, partial-result and exclusion forwarding; changed-file Ruff/Bandit clean.
- Limits: Java owns coalescing cancellation and finite result storage; partial results explicitly remain partial.

## 15 request-scheduling

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- Adaptation: per-backend reader/exclusive-writer gate, max 16 concurrent readers and 64 waiting requests, bounded 128-backend table; waiting writers prevent starvation. Legacy GET mutations serialize; read-only batch POST remains a reader. Queue time counts against overall deadline; cancellation removes waiters and releases active permits.
- Validation: 39 unittest cases including writer exclusion, queued cancellation, saturation and independent backends; all changed-file Ruff/Bandit clean.
- Limits: process-local scheduling complements Java serialization; multiple bridge processes still depend on backend mutation coordination.

## 16 jvm-analysis-tools

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- New get_jvm_info section enum covers manifest, services/SPI, entry-points, dependencies, properties and packages through the agreed jvm-info backend route. Public description distinguishes bytecode references from resolved runtime dependencies.
- Validation: 40 unittest cases, all six sections through actual MCP/HTTP transport; changed-file Ruff/Bandit clean.
- Limits: JAR fixture runtime analysis and format capability checks require paired Java implementation.

## 17 authenticated-transport

- Donor: DongShuaike/jadx-mcp-server @ c8415e5e3fba142fa12338fa743f33762f04b8ea.
- Adaptation: full HTTP(S) backend URL (--jadx-url/JADX_API_URL), token from JADX_API_TOKEN or --jadx-token-file/JADX_API_TOKEN_FILE. File is reread per request for rotation; unreadable/invalid token fails closed. GET, POST, health and progress use the same bearer header. Tokens are not command-line values or logged; health logs only outcome. Proxy isolation remains.
- Validation: 44 unittest cases, all transport modes receive auth, file rotation/rejection, full URL parsing and prefix retention; changed-file Ruff/Bandit clean.
- Limits: this authenticates bridge-to-plugin traffic; MCP client identities and HTTP access policy are feature19. Use TLS termination for remote HTTP.

## 18 multi-instance-supervisor

- Donor: vv19ca0/jadx-mcp-server @ 910ff08e8dfe6832f01cc65767c3c390246a0e35.
- Adaptation: schema-visible optional instance on all current tools, ContextVar routing, canonical local-admin registry, distinct backend credential references, bounded opt-in loopback discovery, validated plugin health identity. Existing comments/debugging tools retained. No MCP URL registration.
- Validation: 47 unittest cases; actual concurrent FastMCP/HTTP calls select independent backends, schema checks cover every tool, alias collision/load atomicity and false health positives tested; changed-file Ruff/Bandit clean.
- Limits: administrator files are trusted; multi-user visibility/authorization arrives in feature19. Registry discovery does not bypass plugin authentication.

## 19 multiuser-authorization

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- Adaptation: FastMCP TokenVerifier backed by local administrator policy and environment-held credentials; constant-time comparisons, explicit canonical per-instance read/write grants, default-deny. HTTP requires a policy, stdio remains trusted local owner. Both routed tools and shared transport enforce permissions before credentials/caches/queues. Listing/refresh filter instances; GET mutations are writes and batch reads stay reads.
- Validation: 52 unittest cases; actual ASGI HTTP tests prove missing-token401, authorized dispatch, forbidden canonical/alias/port selection, read-only mutation rejection, filtered listing and absence of backend URLs/tokens; direct unauthenticated dispatch fails closed. Changed-file Ruff/Bandit clean.
- Limits: TLS termination and administrator policy/token lifecycle are external. MCP forbidden results carry status403 inside the standard result envelope, not an HTTP403 transport status. Client token rotation requires restart.

## 20 runtime-diagnostics

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986.
- New get_runtime_diagnostics tool and authenticated jadx://status MCP resource expose backend JVM/cache/thread metrics plus bridge queue occupancy and explicit degraded state. Status views filter permissions before each backend request and contain no backend addresses or credential references.
- Validation: 56 unittest cases; degraded errors retained and status dispatch limited to permitted instances; auth HTTP tests continue passing; changed-file Ruff/Bandit clean.
- Limits: status is an MCP resource, not a separate public web dashboard. Backend metrics require the paired Java diagnostic route.

## 21 headless-analysis

- Donor: DongShuaike/jadx-mcp-server @ c8415e5e3fba142fa12338fa743f33762f04b8ea (paired Java headless launcher).
- Adaptation: get_backend_capabilities exposes authenticated mode/route capabilities. Known registry capabilities reject unsupported GUI operations before dispatch. For new routes returning unstructured404, health negotiation distinguishes unavailable feature from missing entity in a supported route. No blanket404 conversion.
- Validation: 59 unittest cases; actual MCP/HTTP headless capability read, unsupported GUI action and supported-route404 distinction; changed-file Ruff/Bandit clean.
- Limits: actual headless startup/decompilation belongs to the Java PR; capability metadata refresh is explicit through refresh_instances/get_backend_capabilities.

## 22 container-images

- Donor: luminovaa/jadx-mcp-server @ 082fba3d9f99699ba64a8dfd31ffe080425c59c9.
- Adaptation: digest-pinned Python3.13 and uv0.9.3 multi-stage build, frozen lock, installed non-editable package, UID/GID10001, exec entrypoint. Docker --init provides signal forwarding/reaping without adding an unpinned apt dependency. Strict build-context allowlist excludes credentials, git and fixtures.
- Validation: actual Docker build succeeded (image sha256:54bfd4387df9854fb7846bb425f26eebbeb418b10ccffc0721f7fcf3cc575fe1); image UID10001/import and real stdio MCP initialize/list/call/unavailable-backend response passed. Container tests opt in via JADX_TEST_CONTAINER_IMAGE; Ruff/Bandit clean.
- Limits: no image publication; no production deployment, TLS proxy or headless-Java integration claimed by Python image smoke. Image runtime Python3.13.16; workstation tests Python3.13.15.
