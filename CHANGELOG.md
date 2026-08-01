# Changelog

## [0.4.0](https://github.com/doguskysilva/fundamentum/compare/v0.3.0...v0.4.0) (2026-08-01)


### ⚠ BREAKING CHANGES

* **observability:** Remove the homegrown trace context exports, including get_trace_id, set_trace_id, clear_trace_id, trace_id_ctx, trace segment helpers, and manual traceparent helpers. X-Trace-ID propagation is replaced by optional OpenTelemetry W3C Trace Context instrumentation.

### Features

* **observability:** replace homegrown tracing with OpenTelemetry ([d720b79](https://github.com/doguskysilva/fundamentum/commit/d720b795a3041a6617afae429e62dbb0bdf90c7e))

## [0.3.0](https://github.com/doguskysilva/fundamentum/compare/v0.2.1...v0.3.0) (2026-08-01)


### Features

* add liveness/readiness router helpers ([ae6235e](https://github.com/doguskysilva/fundamentum/commit/ae6235eac13b339062bbdd94b85345541006c0d5))
* **http:** harden ServiceClient — retries, pooling, typed responses ([ccd5c18](https://github.com/doguskysilva/fundamentum/commit/ccd5c189a93d52c42fd53b41f6cc75172cf83322))
* **observability:** propagate W3C traceparent, add pluggable metrics ([1274b4f](https://github.com/doguskysilva/fundamentum/commit/1274b4f058d68844c3c0821cda96403dcbf4f6c6))


### Bug Fixes

* correct pydantic-settings ConfigDict usage and formatter typing ([dee009d](https://github.com/doguskysilva/fundamentum/commit/dee009da58cf4f0454abf3ffcbc50c763659bd01))


### Documentation

* fix README doc drift, cover new retry/typing/health/metrics features ([421f6b7](https://github.com/doguskysilva/fundamentum/commit/421f6b7b0206085e2d284a8c12fd0195a81bad36))
* **http:** document and guard the global EndpointRegistry footgun ([4ca48f1](https://github.com/doguskysilva/fundamentum/commit/4ca48f12be48a47a092c65200e76ef7569d832be))

## [0.2.1](https://github.com/doguskysilva/fundamentum/compare/v0.2.0...v0.2.1) (2026-08-01)


### Bug Fixes

* pin Python 3.14 consistently in CI and via .python-version ([7364a28](https://github.com/doguskysilva/fundamentum/commit/7364a282e97137f92482b66b7a2bfc7e2862b29b))
