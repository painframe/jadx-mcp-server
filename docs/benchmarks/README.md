# Recorded benchmark evidence

`benchmark-final.json` compares the original production source (fixture/build branch
`885e5b1d4e82a6218794eb10a74b041879480239`, production-identical to `7e22ae7`)
with candidate `cb89e99121bff052c574687ed961ca2993a3c054`. The candidate includes
the shared GUI/headless analysis implementation and container-image feature.
The companion provenance file records exact compiled-class hashes.

These are actual local measurements of real JADX and HTTP handlers with a
test-only mocked GUI window, using the tiny donor Calculator JAR, 30 samples
per case and concurrency 4. Source hashes match. The separate headless and
container acceptance tests are functional checks, not this benchmark.

| Case | Baseline successful | Candidate successful | Baseline median / p95 (ms) | Candidate median / p95 (ms) |
|---|---:|---:|---:|---:|
| source_warm | 30/30 | 30/30 | 1.930 / 3.231 | 2.324 / 4.845 |
| search_repeated | 30/30 | 30/30 | 1.870 / 3.173 | 1.794 / 2.564 |
| batch_source | 0/30 | 30/30 | unsupported | 1.749 / 3.210 |
| cache_stats | 30/30 | 30/30 | 1.619 / 2.369 | 1.707 / 2.443 |
| runtime_diagnostics | 0/30 | 30/30 | unsupported | 1.591 / 2.526 |

Timings are mixed. This does not establish a general speedup, large-APK scaling,
cold-cache behavior, peak RSS or production concurrency reliability. Unsupported
baseline operations remain failed samples with null successful latency; quick
errors and partial responses are never counted as successful work.

`benchmark-through14.json` and its provenance preserve the earlier checkpoint
measurement. They are not relabeled as final-stack evidence. Raw samples and
failure/partial counts are retained in both reports.
