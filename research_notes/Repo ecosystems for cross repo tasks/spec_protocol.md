# Spec- and protocol-driven open-source ecosystems as sources of cross-repo RL tasks

Method note: PR numbers, merge dates and titles below come from the GitHub search API (queried 18 Nov 2026). Diff sizes (+added/-deleted lines, files, test files) were counted from each PR's `.diff` at patch-diff.githubusercontent.com. Merge dates are UTC, so a few show 19 Nov 2026. The core API rate limit (60/hour, unauthenticated) ran out partway through, so some ecosystems were only checked through search. Search result URLs follow `https://github.com/<repo>/pull/<n>`. Each PR link below is the source for that PR's number, date, title and size.

## Q1. Which ecosystems are strong candidates (repos, languages, licence)?

### Takeaway
Four ecosystems best fit "one contract repo plus several implementation repos in different languages, merged close together, each with its own tests". **Model Context Protocol (MCP)** is clearly the strongest: a spec repo, Tier-1 SDKs in TS/Python/Go/C#/Rust/Ruby/PHP, and a shared conformance suite. Next come **OpenFeature/flagd** (spec, a Go daemon and providers in Java/Python/Go/JS/.NET/Rust, plus a shared Gherkin testbed), **gRPC** (gRFC proposals, then C++/Go/Java with interop tests) and **OpenTelemetry** (specification, then Go/Java/JS/.NET SDKs). Iceberg and Prometheus are good secondary sources. Kubernetes/client-go and Envoy/go-control-plane are mostly mirrors or codegen and are weak.

### Cited Findings
- MCP repos: modelcontextprotocol/modelcontextprotocol (spec), typescript-sdk, python-sdk, go-sdk and conformance carry a LICENSE saying "The MCP project is undergoing a licensing transition from the MIT License to the Apache License, Version 2.0". python-sdk's LICENSE is still plain MIT ("Copyright (c) 2024 Anthropic, PBC"). Both are permissive. — [spec LICENSE](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/LICENSE), [python-sdk LICENSE](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE)
- More MCP SDKs implementing the same SEPs in 2026: csharp-sdk, rust-sdk, ruby-sdk and php-sdk (see SEP-2549 PRs in Q3). — [csharp-sdk#1623](https://github.com/modelcontextprotocol/csharp-sdk/pull/1623), [rust-sdk#889](https://github.com/modelcontextprotocol/rust-sdk/pull/889), [ruby-sdk#436](https://github.com/modelcontextprotocol/ruby-sdk/pull/436), [php-sdk#450](https://github.com/modelcontextprotocol/php-sdk/pull/450)
- OpenFeature: open-feature/spec and open-feature/flagd are Apache-2.0. — [spec LICENSE](https://github.com/open-feature/spec/blob/main/LICENSE), [flagd LICENSE](https://github.com/open-feature/flagd/blob/main/LICENSE)
- OpenFeature implementation repos active in 2026: java-sdk, go-sdk, js-sdk, dotnet-sdk, kotlin-sdk, php-sdk, ruby-sdk, dart-sdk, cpp-sdk; plus provider "contrib" repos java-, python-, go-, js-, dotnet-, rust- and cpp-sdk-contrib. — search results, e.g. [java-sdk#1928](https://github.com/open-feature/java-sdk/pull/1928), [rust-sdk-contrib#165](https://github.com/open-feature/rust-sdk-contrib/pull/165)
- flagd-testbed: "a Docker image to support the Gherkin test suites defined in the OpenFeature specification", bundling flagd and a "launchpad" utility. Its LICENSE was not at `main/LICENSE` (404), so it still needs checking. — [flagd-testbed README](https://github.com/open-feature/flagd-testbed)
- gRPC: grpc/grpc-go and grpc/grpc-java are Apache-2.0. Proposals (gRFCs: A* = cross-language, L* = language-specific, G* = HTTP/transport) live in grpc/proposal. — [grpc-go LICENSE](https://github.com/grpc/grpc-go/blob/master/LICENSE), [grpc/proposal](https://github.com/grpc/proposal)
- OpenTelemetry specification, Iceberg (iceberg-python, iceberg-go, iceberg-rust), Prometheus and kubernetes-sigs/gateway-api are Apache-2.0. — [otel-spec LICENSE](https://github.com/open-telemetry/opentelemetry-specification/blob/main/LICENSE), [iceberg-go LICENSE](https://github.com/apache/iceberg-go/blob/main/LICENSE), [iceberg-rust LICENSE](https://github.com/apache/iceberg-rust/blob/main/LICENSE), [prometheus LICENSE](https://github.com/prometheus/prometheus/blob/main/LICENSE), [gateway-api LICENSE](https://github.com/kubernetes-sigs/gateway-api/blob/main/LICENSE)
- Kubernetes client-go: "This is an automatically published staged repository for Kubernetes. This repository is read-only for importing, and not used for direct contributions… the code development is still done in the staging area" (kubernetes/kubernetes/staging). — [client-go README](https://github.com/kubernetes/client-go)
- Envoy: data-plane-api is a "read-only mirror" of envoy/api. In go-control-plane, "The Go proto files are synced from the upstream Envoy repository on every upstream commit" through the `envoy-sync.yaml` workflow. — [data-plane-api README](https://github.com/envoyproxy/data-plane-api), [go-control-plane README](https://github.com/envoyproxy/go-control-plane)

### Inferences
- Kubernetes (k/k + client-go + kubectl) is in practice one monorepo. A KEP lands in kubernetes/kubernetes, and client-go/kubectl changes are mirrored copies, so "multi-repo" there is fake. Gateway API is a better K8s-family source: the API and conformance repo is separate from the implementations (Envoy Gateway, Istio, kgateway, NGINX Gateway Fabric).
- In Envoy, go-control-plane and data-plane-api get proto changes by automated sync, so they are codegen-only. A real Envoy task would be envoy (C++) plus a control plane's logic, which is not a spec-to-implementation propagation.

### Gaps
- I did not verify licences for LSP (vscode-languageserver-node), Jupyter, CloudEvents SDKs, AsyncAPI, Sigstore, Dapr, OPA, containerd, OpenSearch, elasticsearch-specification or Delta. I also found no 2026 multi-repo examples for them; see Q5.

## Q2. How do spec changes propagate, and how fast? Is it close enough in time to make one task?

### Takeaway
MCP has the most formal and fastest propagation. A SEP is merged into the spec, SDKs implement it in 2–8 weeks against a dated spec release (2026-07-28), and since 2026 a SEP needs conformance tests to reach Final. OpenFeature's flagd changes are coordinated: the same PR title is merged into flagd and 5–7 provider repos on the same day. OpenFeature spec changes, by contrast, reach SDKs in 1–6 months. gRPC gRFCs are often implemented in Go and Java within days to weeks, sometimes before the gRFC merges. OTel spec-to-SDK lag runs from days to about 2 months.

### Cited Findings
- MCP process docs and changes merged in 2026: "SEP-2484: Require Conformance Tests for Standards Track SEPs to Reach Final Status" (17 May 2026); "SEP-2596: Specification Feature Lifecycle and Deprecation Policy" (18 May 2026); "SEP-1730: SDK tiers definition" (2 Feb 2026); "SEP-3398: Release Cycle Updates" (27 Oct 2026); "docs: working-group sponsored SEP process" (12 Nov 2026). — [spec#2484](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2484), [spec#2596](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2596), [spec#1777](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1777), [spec#3398](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/3398), [spec#3529](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/3529)
- MCP SDKs target a dated spec revision. typescript-sdk "Implement MCP 2026-07-28" was merged 26 Jun 2026. SDK PRs reference SEPs by number in the title (e.g. "feat(client): SEP-2549 — honor cacheHints…"). — [typescript-sdk#2286](https://github.com/modelcontextprotocol/typescript-sdk/pull/2286), [typescript-sdk#2340](https://github.com/modelcontextprotocol/typescript-sdk/pull/2340)
- MCP conformance has a "tier-check" that counts "an SDK release in the 24h before a spec release as tracking it" (conformance#458, 17 Aug 2026). It runs the SDKs through an sdk-runner ("expand KNOWN_SDKS to all tier 1 SDKs", #417, 27 Jul 2026). — [conformance#458](https://github.com/modelcontextprotocol/conformance/pull/458), [conformance#417](https://github.com/modelcontextprotocol/conformance/pull/417)
- OpenFeature flagd: "feat!: fractional bucketing improvements" was merged 1 Apr 2026 into flagd#1909, java-sdk-contrib#1740, python-sdk-contrib#373, go-sdk-contrib#866, js-sdk-contrib#1501 and dotnet-sdk-contrib#622. "feat!: bucket on any context type; (fractional re-assignment)" was merged 15 Oct 2026 into flagd#2011, java#1831, python#415, go#932, js#1636, dotnet#748, rust#165 and cpp#131. — [flagd#1909](https://github.com/open-feature/flagd/pull/1909), [flagd#2011](https://github.com/open-feature/flagd/pull/2011)
- OpenFeature spec to SDKs, slower: spec "feat: add isolated instance" (#368, 8 Apr 2026) reached dotnet-sdk#740 (30 Apr), php-sdk#171 (10 Jun), go-sdk#492 (12 Jun), java-sdk#1928 (15 Jun), kotlin-sdk#243 (17 Jun) and ruby-sdk#354 (23 Oct 2026). — [spec#368](https://github.com/open-feature/spec/pull/368), [go-sdk#492](https://github.com/open-feature/go-sdk/pull/492), [java-sdk#1928](https://github.com/open-feature/java-sdk/pull/1928), [dotnet-sdk#740](https://github.com/open-feature/dotnet-sdk/pull/740)
- gRPC: the A113 gRFC "pick_first: Weighted Random Shuffling" merged 18 Feb 2026, after grpc-java#12623 (28 Jan 2026) and grpc-go#8864 (30 Jan 2026) had already implemented it. A105 "MAX_CONCURRENT_STREAMS Connection Scaling" merged 31 Jan 2026, the same day as grpc-proto#171 ("service config and channelz changes for connection scaling"). C-core fixes followed in March (grpc#41853, #41935) and Java interop tests in June (grpc-java#12651). — [proposal#535](https://github.com/grpc/proposal/pull/535), [grpc-go#8864](https://github.com/grpc/grpc-go/pull/8864), [grpc-java#12623](https://github.com/grpc/grpc-java/pull/12623), [proposal#516](https://github.com/grpc/proposal/pull/516), [grpc-proto#171](https://github.com/grpc/grpc-proto/pull/171), [grpc-java#12651](https://github.com/grpc/grpc-java/pull/12651)
- OTel: the spec's compliance matrix is a set of per-language YAML files (spec-compliance-matrix/go.yaml, js.yaml…), and spec PRs edit them. Spec#5291 "Stabilize maxExportBatchSize for Periodic exporting MetricReader" (11 Sep 2026) touched go.yaml and js.yaml. Spec#5378 "Add span type to Trace API and SDK" (19 Nov 2026 UTC) touched 16 language matrix files. — [spec#5291](https://github.com/open-telemetry/opentelemetry-specification/pull/5291), [spec#5378](https://github.com/open-telemetry/opentelemetry-specification/pull/5378)
- Iceberg: the REST spec "Add unregister table endpoint" (iceberg#16400, 26 May 2026) was implemented in iceberg-python#3419 (13 Sep 2026) and the Java core (iceberg#18203, 1 Oct 2026): a 3.5–4 month lag. — [iceberg#16400](https://github.com/apache/iceberg/pull/16400), [iceberg-python#3419](https://github.com/apache/iceberg-python/pull/3419), [iceberg#18203](https://github.com/apache/iceberg/pull/18203)
- Prometheus: proposals live in prometheus/proposals (e.g. #72, 9 Jul 2026), and the Remote-Write 2.0 spec lives in prometheus/docs. "rw2: add stateless and stateless-st modes (rc.6)" (docs#3147, 22 Oct 2026) was implemented in prometheus#20098 "add remote_write mode for stateless and stateless-st" (30 Oct 2026). — [proposals#72](https://github.com/prometheus/proposals/pull/72), [docs#3147](https://github.com/prometheus/docs/pull/3147), [prometheus#20098](https://github.com/prometheus/prometheus/pull/20098)

### Inferences
- "Close in time" (comparable to Saleor's two weeks): MCP's SDK burst (mid-June to early July 2026), OpenFeature flagd's same-day merges, gRPC A113 (two days apart in Go and Java) and Prometheus RW2 stateless (8 days apart) all fit. OpenFeature spec-to-SDK and Iceberg spec-to-impl fit less well; frame those as "contract already merged, implement it in N languages".
- Same-day OpenFeature flagd merges mean one author made coordinated changes across repos. That is closest to the "one company, several teams" story.

### Gaps
- I did not fetch PR bodies, so I could not confirm that every SDK PR links its spec PR. Titles reference SEP numbers for MCP and gRFC numbers for gRPC; for OpenFeature, links are probably in the PR bodies but unverified.

## Q3. Concrete multi-repo feature examples (2026 unless marked)

### Takeaway
Thirteen concrete 2026 features are listed below, each with a contract PR and 2+ implementation PRs with tests. MCP and OpenFeature supply most of them. All post-date a mid-2026 training cutoff, or come close to it.

### Cited Findings

**MCP (spec → TS / Python / Go, plus C#/Rust/Ruby/PHP)**
1. SEP-2549 "TTL for List Results": spec#2549 merged 15 May 2026 (+865/-43, 20 files); conformance#275 added SEP-2549 tests on 22 May 2026 (+649). Implementations:
   - go-sdk#1008, 18 Jun (+356/-70, 11 files)
   - typescript-sdk#2340, 23 Jun (+1822/-166, 15 files)
   - python-sdk#3015, 29 Jun (+519/-4) and python-sdk#3023, 30 Jun (+3789/-88, 18 files)
   - csharp-sdk#1623, 15 Jun (+1193/-147, 7 test files, including CachingConformanceTests.cs)
   - rust-sdk#889, 10 Jul (+407/-11, including tests/test_cache_hints.rs)

   Sources: [spec#2549](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2549), [conformance#275](https://github.com/modelcontextprotocol/conformance/pull/275), [go#1008](https://github.com/modelcontextprotocol/go-sdk/pull/1008), [ts#2340](https://github.com/modelcontextprotocol/typescript-sdk/pull/2340), [py#3015](https://github.com/modelcontextprotocol/python-sdk/pull/3015), [py#3023](https://github.com/modelcontextprotocol/python-sdk/pull/3023), [cs#1623](https://github.com/modelcontextprotocol/csharp-sdk/pull/1623), [rs#889](https://github.com/modelcontextprotocol/rust-sdk/pull/889)
2. SEP-2164 "Standardize resource not found error code (-32602)": spec#2164 merged 18 May 2026 (+196/-3). Implementations: go-sdk#931, 5 May (+62/-2, before the spec merged); python-sdk#2920, 20 Jun (+113/-43); TS bundled it into typescript-sdk#2333, 23 Jun (+1575/-28). Small; works as an easy-tier task. Sources: [spec#2164](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2164), [go#931](https://github.com/modelcontextprotocol/go-sdk/pull/931), [py#2920](https://github.com/modelcontextprotocol/python-sdk/pull/2920), [ts#2333](https://github.com/modelcontextprotocol/typescript-sdk/pull/2333)
3. SEP-2577 "Deprecate Roots, Sampling, and Logging": spec#2577 merged 15 May 2026 (+657/-1). Implementations: typescript-sdk#2268, 15 Jun (+124/-2); python-sdk#2926, 20 Jun (+206/-123, 44 files); go-sdk#1017, 23 Jun (+320/-25). Mostly deprecation annotations, so it is low on behaviour. Sources: [spec#2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577), [ts#2268](https://github.com/modelcontextprotocol/typescript-sdk/pull/2268), [py#2926](https://github.com/modelcontextprotocol/python-sdk/pull/2926), [go#1017](https://github.com/modelcontextprotocol/go-sdk/pull/1017)
4. SEP-2243 "HTTP Standardization" (Mcp-Method/Mcp-Name/Mcp-Param-* headers): spec#2243 merged 15 Apr 2026 (+2688/-14). Implementations:
   - go-sdk#907, 29 Apr ("HTTP Header Standardization for method and name") and go-sdk#915, 8 May (x-mcp-header, +1512/-15)
   - typescript-sdk#2327, 22 Jun (+1956/-46, 29 files) and #2328, 22 Jun
   - python-sdk#2990, 26 Jun (+393/-14) and #3033, 30 Jun (server-side validation)

   Rich behaviour (header codec plus server validation). Sources: [spec#2243](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2243), [go#915](https://github.com/modelcontextprotocol/go-sdk/pull/915), [ts#2327](https://github.com/modelcontextprotocol/typescript-sdk/pull/2327), [py#2990](https://github.com/modelcontextprotocol/python-sdk/pull/2990)
5. SEP-2575 "Make MCP Stateless": spec#2575, 11 May 2026. Implementations: go-sdk#975, 2 Jun (client), #987, 8 Jun (server discover) and #1007, 22 Jun (subscriptions/listen); python-sdk#3035, 30 Jun ("Serve subscriptions/listen with a pluggable event bus") and #3047, 7 Jul (client listen driver). Large; probably multi-PR. Sources: [spec#2575](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575), [go#975](https://github.com/modelcontextprotocol/go-sdk/pull/975), [py#3035](https://github.com/modelcontextprotocol/python-sdk/pull/3035)
6. SEP-2322 "Multi Round-Trip Requests": spec#2322, 6 May 2026. Implementations: go-sdk#950, 29 May; python-sdk#2998, 26 Jun (client auto-resolves InputRequiredResult); ruby-sdk#481, 8 Aug; php-sdk#449, 18 Aug. Sources: [spec#2322](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2322), [go#950](https://github.com/modelcontextprotocol/go-sdk/pull/950), [py#2998](https://github.com/modelcontextprotocol/python-sdk/pull/2998)
7. SEP-2640 "Skills Extension": spec#2640, 13 Sep 2026 (+1321). Implementations: python-sdk#3485, 11 Oct (+2047/-2, 17 files); typescript-sdk#3047, 20 Oct (+7854/-75, 110 files: too big); conformance#330, 11 Sep. Sources: [spec#2640](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2640), [py#3485](https://github.com/modelcontextprotocol/python-sdk/pull/3485), [ts#3047](https://github.com/modelcontextprotocol/typescript-sdk/pull/3047), [conf#330](https://github.com/modelcontextprotocol/conformance/pull/330)
- More MCP SEPs with SDK PRs on 3+ SDKs (titles from search): SEP-2468 (iss parameter; ts#2344/#2357, py#2921, go#859), SEP-2350 (scope step-up; ts#2346, py#2931, go#944), SEP-2352 (credential isolation; ts#2358, py#2933, go#946), SEP-2106 (JSON Schema 2020-12; ts#2337, py#2924, go#1009) and SEP-837 (application_type; ts#2345, py#2930, go#904). — [MCP SDK search results](https://github.com/modelcontextprotocol/python-sdk/pulls?q=is%3Apr+is%3Amerged+SEP)

**OpenFeature / flagd (Go daemon + Java/Python/Go/JS/.NET providers + shared Gherkin testbed)**

8. "fractional bucketing improvements" (high-resolution integer bucketing, v1/v2 algorithm). The testbed added Gherkin scenarios first: flagd-testbed#340 (18 Mar 2026, +82/-4 in gherkin/targeting.feature) and #345 (nested fractional, 18 Mar). flagd-evaluator#18 "high-resolution integer-based fractional bucketing" followed (12 Mar 2026). Then on 1 Apr 2026:
   - flagd#1909 (+895/-750, 11 files, including core/pkg/evaluator/fractional_test.go and a test-harness submodule bump)
   - java-sdk-contrib#1740 (+361/-46, 18 test files)
   - python-sdk-contrib#373 (+353/-112)
   - go-sdk-contrib#866 (+82/-83)
   - js-sdk-contrib#1501 (+277/-41, including targeting.spec.ts)
   - dotnet-sdk-contrib#622

   Sources: [testbed#340](https://github.com/open-feature/flagd-testbed/pull/340), [flagd#1909](https://github.com/open-feature/flagd/pull/1909), [java#1740](https://github.com/open-feature/java-sdk-contrib/pull/1740), [py#373](https://github.com/open-feature/python-sdk-contrib/pull/373), [go#866](https://github.com/open-feature/go-sdk-contrib/pull/866), [js#1501](https://github.com/open-feature/js-sdk-contrib/pull/1501)
9. "bucket on any context type (fractional re-assignment)", 15 Oct 2026, eight repos:
   - flagd#2011 (+266/-206)
   - java-sdk-contrib#1831 (+582/-70)
   - python-sdk-contrib#415 (+205/-26)
   - go-sdk-contrib#932 (+183/-164)
   - js-sdk-contrib#1636
   - dotnet-sdk-contrib#748
   - rust-sdk-contrib#165
   - cpp-sdk-contrib#131

   The testbed precursor was flagd-testbed#380 "test non-string attributes in fractional" (30 Jul 2026). Sources: [flagd#2011](https://github.com/open-feature/flagd/pull/2011), [java#1831](https://github.com/open-feature/java-sdk-contrib/pull/1831), [py#415](https://github.com/open-feature/python-sdk-contrib/pull/415), [go#932](https://github.com/open-feature/go-sdk-contrib/pull/932), [testbed#380](https://github.com/open-feature/flagd-testbed/pull/380)
10. Isolated API instances: spec#368 (8 Apr 2026, +84). Implementations: go-sdk#492, 12 Jun (+834/-462, 13 test files); java-sdk#1928, 15 Jun (+575/-43); dotnet-sdk#740, 30 Apr (+589/-4); php-sdk#171 and kotlin-sdk#243 in June. Sources: [spec#368](https://github.com/open-feature/spec/pull/368), [go#492](https://github.com/open-feature/go-sdk/pull/492), [java#1928](https://github.com/open-feature/java-sdk/pull/1928), [dotnet#740](https://github.com/open-feature/dotnet-sdk/pull/740)
11. Supply bound domain to provider initialization: spec#393 (25 Jun 2026, +70/-7). Implementations: js-sdk#1433, 27 Jul (+393/-13); java-sdk#1982, 28 Jul (+769/-64, 14 test files); ruby-sdk#345, 23 Oct. A good Java+TS pair about one month after the spec. Sources: [spec#393](https://github.com/open-feature/spec/pull/393), [js#1433](https://github.com/open-feature/js-sdk/pull/1433), [java#1982](https://github.com/open-feature/java-sdk/pull/1982)
- More OpenFeature testbed-driven items: "make default variant optional" (flagd-testbed#333/#331, 4 Mar 2026) and "flags and scenarios for numeric precision" (testbed#392, 22 Oct 2026; flagd#2100 "strict numeric range opt, TYPE_MISMATCH on precision loss", 23 Oct). — [testbed#333](https://github.com/open-feature/flagd-testbed/pull/333), [testbed#392](https://github.com/open-feature/flagd-testbed/pull/392), [flagd#2100](https://github.com/open-feature/flagd/pull/2100)

**gRPC (gRFC → grpc-go + grpc-java [+ C-core])**

12. A113 pick_first weighted random shuffling: proposal#535 (18 Feb 2026, +107). grpc-java#12623 (28 Jan 2026, +526/-24, tests in PickFirstLeafLoadBalancerTest) and grpc-go#8864 (30 Jan 2026, +591/-141, tests in pickfirst_ext_test.go and ringhash_e2e_test.go). A clean Go + Java pair with real load-balancer behaviour. Sources: [proposal#535](https://github.com/grpc/proposal/pull/535), [go#8864](https://github.com/grpc/grpc-go/pull/8864), [java#12623](https://github.com/grpc/grpc-java/pull/12623)
- Other 2026 gRFCs to mine (implementation PRs not verified): A105 MCS connection scaling (proposal#516, 31 Jan; grpc-proto#171; C-core grpc#41853/#41935; grpc-java#12651 interop), A103 xDS Composite Filter (#511, 27 Feb), A108 OTel per-call metric label (#525, 17 Mar), A107 TLS private key offloading (#524, 3 Apr), A114 WRR custom backend metrics (#536, 12 May), A118 TLS telemetry (#550, 16 Jun), A120 post-quantum crypto (#553, 15 Jul), A110 child channel options (#529, 5 Aug), A102 xDS GrpcService (#510, 10 Sep), A93 xDS ExtProc (#484, 6 Nov 2026). — [grpc/proposal PRs](https://github.com/grpc/proposal/pulls?q=is%3Apr+is%3Amerged)

**OpenTelemetry (specification → Go/Java/JS/.NET SDKs)**

13. maxExportBatchSize for PeriodicExportingMetricReader: spec#5265 "Clarify…" (24 Aug 2026), spec#5291 "Stabilize…" (11 Sep 2026, +18/-17) and spec#5359 "Add OTEL_METRIC_EXPORT_MAX_BATCH_SIZE env var" (27 Oct 2026). Implementations:
   - opentelemetry-go#8960, 15 Sep (+119/-101, periodic_reader_test.go)
   - opentelemetry-js#7092, 17 Sep (+25/-3, no test files: trivial)
   - opentelemetry-java#8935, 28 Oct (+57/-3, autoconfigure test)
   - opentelemetry-dotnet#8053, 9 Nov (+937/-39, 22 files)

   Sources: [spec#5291](https://github.com/open-telemetry/opentelemetry-specification/pull/5291), [spec#5359](https://github.com/open-telemetry/opentelemetry-specification/pull/5359), [go#8960](https://github.com/open-telemetry/opentelemetry-go/pull/8960), [js#7092](https://github.com/open-telemetry/opentelemetry-js/pull/7092), [java#8935](https://github.com/open-telemetry/opentelemetry-java/pull/8935), [dotnet#8053](https://github.com/open-telemetry/opentelemetry-dotnet/pull/8053)
- OTel span type: proto#884 "add span type field" (18 Nov 2026, +16/-2) and spec#5378 (19 Nov 2026 UTC, +92). SDK implementations are not merged yet, so this is a candidate for a forward-looking task later in 2026–27. — [proto#884](https://github.com/open-telemetry/opentelemetry-proto/pull/884), [spec#5378](https://github.com/open-telemetry/opentelemetry-specification/pull/5378)
- More 2026 OTel spec changes (SDK side not checked): sampler shutdown (#5335, 16 Oct), configurable SDK component names (#5300, 13 Nov), Prometheus target_info conversion (#5368, 30 Oct), ProcessContext from OTEP 4719 (proto#783, 16 Jun 2026). — [spec#5335](https://github.com/open-telemetry/opentelemetry-specification/pull/5335), [proto#783](https://github.com/open-telemetry/opentelemetry-proto/pull/783)
- opentelemetry-proto merged 111 PRs in 2026, mostly dependency bumps and docs clarifications. Only a few were field additions (ProcessContext #783, span type #884). — [proto PR search](https://github.com/open-telemetry/opentelemetry-proto/pulls?q=is%3Apr+is%3Amerged+merged%3A%3E%3D2026-01-01)

**Iceberg / Prometheus / Gateway API (secondary)**
- Iceberg unregister table: REST spec iceberg#16400 (26 May 2026, +87, no tests), iceberg-python#3419 (13 Sep 2026, +79, tests/catalog/test_rest.py), Java iceberg#18203 (1 Oct 2026, +550, CatalogTests/JdbcCatalog tests). — links in Q2
- Iceberg v3 features in 2026 across python, go, rust and cpp (row lineage, variant, default values). Examples: iceberg-python#3972 "Add row-lineage support with Spark tests" (11 Nov 2026, +171/-12); iceberg-cpp#822 (17 Jul); iceberg-go#1250 (24 Jun); iceberg-rust#2188 "Variant Support" (16 Jul); iceberg-go#1607 variant pushdown (4 Sep). The v3 spec itself is older (2025), so the spec side is not in the same window. — [py#3972](https://github.com/apache/iceberg-python/pull/3972), [rust#2188](https://github.com/apache/iceberg-rust/pull/2188), [go#1607](https://github.com/apache/iceberg-go/pull/1607)
- Iceberg v4 spec work in Oct–Nov 2026 (implementations still to come): "Spec: Add support for default expression values" (#16777, 6 Nov), "V4 Adaptive Metadata Tree" (#16025, 14 Oct), "Forbid writing new equality deletes in v4" (#17783, 29 Sep). — [iceberg#16777](https://github.com/apache/iceberg/pull/16777), [iceberg#16025](https://github.com/apache/iceberg/pull/16025)
- Prometheus RW2 stateless modes: docs#3147 (22 Oct 2026, +65/-16), then prometheus#20098 (30 Oct 2026, +802/-52, 12 test files). Also prometheus/compliance#194 "Add remote write 2 sender compliance tests" (12 Jan 2026) and client_golang exp/api/remote fixes (#2158, 12 Oct; #2087, 26 Oct). — [docs#3147](https://github.com/prometheus/docs/pull/3147), [prometheus#20098](https://github.com/prometheus/prometheus/pull/20098), [compliance#194](https://github.com/prometheus/compliance/pull/194), [client_golang#2158](https://github.com/prometheus/client_golang/pull/2158)
- Gateway API 2026 GEPs: GEP-4768 TelemetryPolicy (#5308, 1 Oct 2026, +4556 lines, mostly generated swagger and applyconfiguration), GEP-1731 retries promoted to Standard (#5347, 8 Oct; #5418, 23 Oct), GEP-5224 pre-routing (#5271, 28 Sep), GEP-1619 session persistence on Backend (#5298, 28 Sep). Implementer conformance reports are filed back into the repo (kgateway #5454, NGINX Gateway Fabric #5376, Kong #5313). — [gw#5308](https://github.com/kubernetes-sigs/gateway-api/pull/5308), [gw#5347](https://github.com/kubernetes-sigs/gateway-api/pull/5347), [gw#5454](https://github.com/kubernetes-sigs/gateway-api/pull/5454)
- Temporal (brief): temporalio/api merged 44 PRs from 1 Aug to 18 Nov 2026, e.g. "support workflow heartbeat notification" (#901, 17 Nov), "Add RPC definitions for namespace soft deletion and restoration" (#899, 3 Nov), "Add eager standalone activity start API" (#876, 8 Oct). — [temporalio/api PRs](https://github.com/temporalio/api/pulls?q=is%3Apr+is%3Amerged)
- Arrow format changes in 2026 were mostly documentation clarifications: e.g. "Deprecate IPC tensor/sparse tensor messages" (arrow#51102, 10 Sep 2026) and "Clarify Union type ids" (#50839, 6 Oct). — [arrow#51102](https://github.com/apache/arrow/pull/51102), [arrow#50839](https://github.com/apache/arrow/pull/50839)

### Inferences
- The top picks are SEP-2549 (TTL/cache hints) and SEP-2243 (HTTP headers) for MCP, the two flagd fractional features, isolated instances / bound domain for OpenFeature, and A113 for gRPC. Each has real behaviour on every side, PRs of 100–2,000 lines, and tests in each repo.
- A task "team" could be a spec agent plus Go/TS/Python SDK agents for MCP, or a Go (flagd) agent plus Java/Python/TS provider agents for OpenFeature.
- In several MCP and gRPC cases, one implementation merged before the spec PR (go-sdk#931 before spec#2164; grpc-java/go before proposal#535). The task "start" commit should take the latest parent across repos, or give the spec text as the contract.
- The TS Skills PR (#3047, 110 files) and Gateway API TelemetryPolicy (#5308, mostly generated) are too large or too mechanical.

### Gaps
- Sizes for go-sdk#907/#975/#987, python-sdk#3033/#3035, js-sdk-contrib#1636, dotnet-sdk-contrib#622/#748 and the gRPC A105 implementations were not fetched because of the rate limit.
- I did not find which Gateway API implementations (Envoy Gateway, Istio) shipped TelemetryPolicy or retry backoff, or when. A search for envoyproxy PRs on these GEPs returned nothing relevant.

## Q4. Test suites, conformance verifiers and Docker runnability

### Takeaway
MCP's conformance package and OpenFeature's flagd-testbed are ready-made shared hidden verifiers that run the same scenarios against every language's implementation. gRPC interop tests and Prometheus compliance are similar but heavier. OTel and Iceberg have no shared cross-language behavioural verifier. Their verifiers would be each repo's own unit tests (or Spark-based integration tests for Iceberg, which are heavy in Docker).

### Cited Findings
- The MCP conformance framework runs as `npx @modelcontextprotocol/conformance client --command "<your client>" --scenario initialize` or `server --url http://localhost:3000/mcp`, and has an SDK integration guide. — [conformance README](https://github.com/modelcontextprotocol/conformance)
- MCP SDKs pin conformance versions and keep expected-failures baselines:
  - TS: "pin conformance 0.2.0-alpha.1 and baseline the draft-spec suites" (#2227, 1 Jun 2026)
  - Python: "Repin conformance harness to the published 0.2.0-alpha.10" (#3184, 27 Jul 2026) and "ci(conformance): run server --suite draft" (#2878)

  Conformance "Validate all wire messages against the per-version spec JSON schema" (#399, 27 Jul 2026) and "Freeze conformance requirements per spec revision" (#447, 7 Aug 2026). — [ts#2227](https://github.com/modelcontextprotocol/typescript-sdk/pull/2227), [py#3184](https://github.com/modelcontextprotocol/python-sdk/pull/3184), [conf#399](https://github.com/modelcontextprotocol/conformance/pull/399), [conf#447](https://github.com/modelcontextprotocol/conformance/pull/447)
- In OpenFeature, flagd and providers embed flagd-testbed as a git submodule ("test-harness" bumps appear in flagd#1909, python-sdk-contrib#373 and #415). Provider e2e tests live in java-sdk-contrib (RunInProcessTest.java), go-sdk-contrib (providers/flagd/e2e/inprocess_test.go) and js-sdk-contrib (src/e2e/tests/in-process.spec.ts). In Oct–Nov 2026 the suite moved to "tck-extensions/" (testbed#450 "drop the legacy gherkin/ suite", 16 Nov 2026), and the spec added "provider conformance assets" (spec#423, 14 Oct 2026). — [diffs of flagd#1909](https://github.com/open-feature/flagd/pull/1909), [testbed#450](https://github.com/open-feature/flagd-testbed/pull/450), [spec#423](https://github.com/open-feature/spec/pull/423)
- flagd-java e2e "speed up e2e test execution via container pool and parallel scenarios" (java-sdk-contrib#1752, 24 Jun 2026): the e2e tests use containers (Testcontainers). — [java-sdk-contrib#1752](https://github.com/open-feature/java-sdk-contrib/pull/1752)
- gRPC: interop test fields live in grpc-proto ("Add fields for max connection streaming connection scaling interop tests", #175, 31 Mar 2026), and Java added "MCS connection scaling interop tests" (#12651). — [grpc-proto#175](https://github.com/grpc/grpc-proto/pull/175), [grpc-java#12651](https://github.com/grpc/grpc-java/pull/12651)
- prometheus/compliance has remote write sender/receiver compliance tests (#194, #206 in 2026). — [compliance#194](https://github.com/prometheus/compliance/pull/194), [compliance#206](https://github.com/prometheus/compliance/pull/206)
- Gateway API conformance: implementers submit conformance reports, and the repo generates per-release features YAML "for conformance test validation" (#5443, 2 Nov 2026). — [gw#5443](https://github.com/kubernetes-sigs/gateway-api/pull/5443)
- Iceberg-python#3972 adds row lineage "with Spark tests" (tests/integration/test_reads.py), so its integration tests need a Spark/REST-catalog Docker stack. — [py#3972](https://github.com/apache/iceberg-python/pull/3972)

### Inferences
- MCP: a hidden verifier could be (a) each SDK's new unit tests plus (b) the conformance scenario for the SEP (e.g. conformance#275 for SEP-2549), run through Node in Docker. It needs no network beyond localhost. SDK unit tests are vitest (TS), pytest (Python) and go test; all are fast.
- OpenFeature: the flagd-testbed container plus each provider's Gherkin e2e test is a natural shared verifier. Java e2e needs Docker-in-Docker (Testcontainers), which adds environment complexity. Unit tests (go test, JUnit/Maven, pytest, vitest/jest) are lightweight.
- gRPC-java builds with Gradle and grpc-go with go test. Both are runnable offline once dependencies are cached. C-core (Bazel) is heavy; avoid it.

### Gaps
- I did not verify exact test-runner commands or offline runtimes per repo. I also did not check whether the MCP conformance npm package can run fully offline (it is published to npm, so it can be pre-installed).

## Q5. Activity, number of minable features per year, and codegen risk

### Takeaway
Estimated yield of multi-repo features with real behaviour per year (2026 rates):
- MCP: about 15–25 (SEP-driven, 3–7 SDKs each)
- OpenFeature: about 8–12 (flagd/testbed-coordinated plus spec-driven)
- gRPC: about 5–10 gRFCs with Go+Java implementations
- OTel spec-to-SDK: about 5–10, though many are small
- Iceberg: about 5 (lagged)
- Prometheus RW2: about 2–4

Codegen risk is low for MCP, OpenFeature and gRPC; SDK changes are handwritten behaviour. It is high for Envoy go-control-plane/data-plane-api, Kubernetes client-go/kubectl, Gateway API's generated clients, and proto-only OTel changes.

### Cited Findings
- MCP spec repo: 107 merged PRs matching "SEP" in title in 2026 alone. typescript-sdk had 101 merged PRs mentioning SEP in 2026, python-sdk 75 and go-sdk 43. — [GitHub search, spec](https://github.com/modelcontextprotocol/modelcontextprotocol/pulls?q=is%3Apr+is%3Amerged+SEP), [ts](https://github.com/modelcontextprotocol/typescript-sdk/pulls?q=is%3Apr+is%3Amerged+SEP), [py](https://github.com/modelcontextprotocol/python-sdk/pulls?q=is%3Apr+is%3Amerged+SEP), [go](https://github.com/modelcontextprotocol/go-sdk/pulls?q=is%3Apr+is%3Amerged+SEP)
- OpenFeature: 144 merged PRs across the org mention "fractional" in 2026; spec had 71 merged PRs since Oct 2025; flagd-testbed had 90 in 2026. — [org search](https://github.com/search?q=org%3Aopen-feature+fractional&type=pullrequests)
- OTel specification: 323 merged PRs from 1 Mar to 18 Nov 2026, many of them dependency/lock maintenance. — [spec PRs](https://github.com/open-telemetry/opentelemetry-specification/pulls?q=is%3Apr+is%3Amerged)
- gRPC proposal: 44 merged PRs in 2026, about 12 of them new gRFCs (A102–A120, L125). — [grpc/proposal](https://github.com/grpc/proposal/pulls?q=is%3Apr+is%3Amerged)
- Iceberg: 61 merged PRs with "spec" in the title in 2026. — [apache/iceberg](https://github.com/apache/iceberg/pulls?q=is%3Apr+is%3Amerged+spec+in%3Atitle)
- Gateway API: 255 merged PRs matching "GEP" from Mar to Nov 2026. #5308 (TelemetryPolicy) is +4556 lines, mostly openapi swagger and generated applyconfiguration Go. — [gw#5308](https://github.com/kubernetes-sigs/gateway-api/pull/5308)
- The Envoy and Kubernetes mirror/codegen facts are in Q1. — [go-control-plane README](https://github.com/envoyproxy/go-control-plane), [client-go README](https://github.com/kubernetes/client-go)

### Inferences
- Risk of easy tasks: some MCP SEPs are deprecations or error-code swaps (SEP-2577, SEP-2164), and OTel JS#7092 (+25 lines) is trivial. Filter for implementation PRs over about 150 lines with new tests on at least two sides.
- In the MCP spec repo, the "contract" is schema.ts/schema.json plus MDX docs; SDK types are partly generated from the schema, but caching/header/stateless logic is handwritten. For OpenFeature, the contract is the Gherkin feature file plus spec markdown (specification.json is generated from the markdown).
- The spec-side PR often has no executable tests (iceberg#16400, proposal#535, prometheus docs#3147). So hidden tests come from the implementation repos, and the spec repo acts as the contract, not a test target. MCP (conformance repo) and OpenFeature (testbed) are the exceptions, where the "spec side" has executable tests.

### Gaps
- No 2026 evidence was gathered for LSP, Jupyter (jupyter_server/jupyterlab/ipykernel), CloudEvents, AsyncAPI, Sigstore, Dapr, OPA, containerd/CRI, OpenSearch, elasticsearch-specification clients, Delta/delta-rs, or Arrow split repos (arrow-rs, arrow-go). I prioritised the stronger candidates within the query budget. Elasticsearch clients are known to be generated from elasticsearch-specification, which would make them codegen-heavy, but I did not verify this here.
- The per-year yields above are my estimates from 2026 PR counts, not measured.
