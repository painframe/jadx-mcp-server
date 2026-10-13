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
