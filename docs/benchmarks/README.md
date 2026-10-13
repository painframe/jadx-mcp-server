# Recorded benchmark evidence

`benchmark-through14.json` is an actual local comparison using real JADX and HTTP
handlers with a test-only mocked GUI window. It compares the initial Java fixture
branch885e5b1d4e82a6218794eb10a74b041879480239 against the feature14 Java revision
63e21dfc37b8b8a2ca92e301c79e1db4afe6170a. Compiled-class hashes are in the companion
provenance file. The small donor Calculator JAR fixture, class, iterations and
concurrency are recorded in the report; both source hash sets match.

This is neither a final-stack benchmark nor a production GUI/headless workload.
It uses a tiny fixture and warmed repeated reads. Unsupported batch/diagnostic
features in the baseline remain failed samples. Source latency was approximately
1.88ms on both sides; search results vary. This evidence does not establish an
overall speedup, large-APK scaling, cold-cache behavior, peak RSS or production
concurrency reliability. Later feature21/25 runtime results must be recorded
separately with their own revisions rather than relabeling this report.
