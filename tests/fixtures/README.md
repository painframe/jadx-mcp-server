# Analysis fixtures

Copied from xjoker/jadx-ai-mcp at
30337f6f072aa360e9099c99e99fb330d44e8986 (`tests/fixtures`).
The Apache-2.0 repository license applies. Checksums in `checksums.json`
pin the original archives. `test_fixture_contracts.py` verifies ZIP integrity,
the JAR Calculator class, APK classes.dex and the existing MCP tool inventory.

- `jadx-test-library-1.0.0.jar`: donor Java library for class, method, field and code-search analysis.
- `jadx-test-app-1.0.0.apk`: donor Android application for class and manifest analysis.
- `test-app-sources`: donor reference sources. They have not been rebuilt or verified to reproduce these binaries. No unsafe donor build scripts are included.

These fixtures do not cover all tools, native-method discovery, SPI, debugging,
or overload handling. Dedicated fixtures/tests must cover those capabilities.
The API_KEY strings in StringUtils.java and ApiManager.java are synthetic donor
test data, not operational credentials; they intentionally exercise code search.
No live execution is implied by the archive-integrity checks.

Run `uv run python -m unittest discover -s tests -v` from the repository root.
