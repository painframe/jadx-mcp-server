# Recorded benchmark evidence

`benchmark-final-metrics.json` is the final comparison. It compares the original
production source (fixture/build branch `885e5b1d4e82a6218794eb10a74b041879480239`,
production-identical to `7e22ae7`) with the completed Java stack
`c4abfbb47a8be4045593d84702674d9f49289e09`. Its companion provenance file records
exact compiled-class hashes. All 30 candidate diagnostics samples retain actual
heap used/max and live-thread metrics from the shared Java endpoint.

These are actual local measurements of real JADX and HTTP handlers with a
test-only mocked GUI window, using the tiny donor Calculator JAR, 30 samples
per case and concurrency 4. Source hashes match. The separate headless and
container acceptance tests are functional checks, not this benchmark.

| Case | Baseline successful | Candidate successful | Baseline median / p95 (ms) | Candidate median / p95 (ms) |
|---|---:|---:|---:|---:|
| source_warm | 30/30 | 30/30 | 2.038 / 2.832 | 2.199 / 4.590 |
| search_repeated | 30/30 | 30/30 | 2.217 / 5.125 | 1.808 / 2.705 |
| batch_source | 0/30 | 30/30 | unsupported | 2.185 / 3.117 |
| cache_stats | 30/30 | 30/30 | 1.394 / 2.095 | 1.698 / 2.936 |
| runtime_diagnostics | 0/30 | 30/30 | unsupported | 1.728 / 2.586 |

Timings are mixed. This does not establish a general speedup, large-APK scaling,
cold-cache behavior, peak RSS or production concurrency reliability. Unsupported
baseline operations remain failed samples with null successful latency; quick
errors and partial responses are never counted as successful work.

Earlier checkpoint reports remain intact: `benchmark-through14.json` and
`benchmark-final.json` (Java feature22). The latter measured valid latency and
success counts but omitted nested JVM metrics; the final metrics run corrects
that omission and has its own source revision and provenance. Raw samples and
failure/partial counts are retained in every report.
