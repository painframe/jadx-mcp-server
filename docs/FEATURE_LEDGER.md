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
