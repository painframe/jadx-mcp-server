# Fork integration ledger

Each feature is a separate stacked branch. Java counterparts are in painframe/jadx-ai-mcp.

## 01 analysis-test-fixtures

- Donor: xjoker/jadx-ai-mcp @ 30337f6f072aa360e9099c99e99fb330d44e8986, tests/fixtures and integration fixture expectations.
- Adaptation: preserve the small original APK/JAR archives, pin SHA256 checksums, test ZIP integrity and expected payloads, and enforce baseline MCP tool preservation through real FastMCP discovery. Avoid donor endpoint assumptions.
- Validation: Python unittest suite, import smoke, Ruff and Bandit for added test code.
- Limits: archive integrity and tool discovery do not prove APK runtime behavior; live paired integration follows each feature.
