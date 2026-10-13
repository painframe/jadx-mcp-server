# Paired analysis benchmark

Load the same checked fixture into an upstream-baseline plugin and the integrated
plugin using the same JADX/JVM version and machine settings. Do not use a project
with unsaved modifications. The harness does not load, rename, clear caches or
change either project.

```sh
uv run -m scripts.benchmark_analysis \
  --baseline-url http://127.0.0.1:8650 --baseline-revision BASE_SHA \
  --candidate-url http://127.0.0.1:8652 --candidate-revision CANDIDATE_SHA \
  --fixture tests/fixtures/jadx-test-library-1.0.0.jar \
  --class-name com.jadxtest.library.Calculator \
  --iterations 10 --concurrency 4 --output comparison.json
```

Supply runtime bearer credentials through JADX_BASELINE_TOKEN and
JADX_CANDIDATE_TOKEN (or alternate environment names through the corresponding
`--*-token-env` options). URLs/credentials are not written to the report.

The matrix covers repeated source reads, repeated class searches, source batching,
cache statistics and runtime diagnostics. It records per-request failures, partial
results, byte counts, latency median/p95 and supported numeric JVM metrics. It
checks identical source SHA256 sets before returning success. The report identifies
the local fixture hash and user-supplied revisions. It does not independently prove
that the remote processes loaded that file: confirm this before running.

Run concurrency1 and4 against the same versions/fixture. Unsupported baseline batch
or diagnostic endpoints remain failed samples, not speedup evidence. No cold-cache,
RSS, peak-memory or performance improvement is claimed by this harness alone.
Output creation fails rather than overwriting an earlier report.
