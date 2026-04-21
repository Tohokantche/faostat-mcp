# Changelog

All notable changes to this project are documented here.
Releases from v1.1.0 onwards are generated automatically from [conventional commits](https://www.conventionalcommits.org) by [release-please](https://github.com/googleapis/release-please).

## [1.3.0](https://github.com/Tohokantche/faostat-mcp/compare/v1.2.2...v1.3.0) (2026-04-21)


### Features

* add hybrid server-side caching (in-memory + Redis) ([a16656a](https://github.com/Tohokantche/faostat-mcp/commit/a16656a0c9f72467267fd3f56c1a77e944c1f309))
* add initial pyproject.toml for project configuration ([09b619f](https://github.com/Tohokantche/faostat-mcp/commit/09b619f441d326c50a2bfc8ae6ad05b1882af4b9))
* add issue templates for bug reports and feature requests for ease if use in github issues ([7cdf736](https://github.com/Tohokantche/faostat-mcp/commit/7cdf736c9b9321ce5aa8b90b7830a8bc196e0879))
* **client:** add hybrid-caching class implementation ([4ace71b](https://github.com/Tohokantche/faostat-mcp/commit/4ace71b42dfb13803e6df7e68d596e24b430f630))
* enhance data formatting and response handling in server API ([b92462a](https://github.com/Tohokantche/faostat-mcp/commit/b92462a9164de24f1a4040ff18a1681c9f823fa7))
* enhance data formatting and response handling in server API ([320fdfa](https://github.com/Tohokantche/faostat-mcp/commit/320fdfa8abcc00e0eaceb028c046bea332238995))
* implement FAOSTAT MCP server and client with token management and API endpoints ([cda7c9d](https://github.com/Tohokantche/faostat-mcp/commit/cda7c9d46528424f7231ae78fc91a966c148d355))
* implement token refresh using the /auth/login endpoint ([8ccbdae](https://github.com/Tohokantche/faostat-mcp/commit/8ccbdaeb815b3b00c46505a647bfe2372a9e37b8))
* **server:** add hybrid-caching to tools ([0e5323b](https://github.com/Tohokantche/faostat-mcp/commit/0e5323b409ef64116a7ad5dcae0fd8c4e6ca89c9))
* unit tests for token refresh via the /auth/login endpoint ([dbb2bc6](https://github.com/Tohokantche/faostat-mcp/commit/dbb2bc62457726d84e7c8fa5ae933eff68f22a7b))
* Upgrade version to 1.2.0 and implement SQLite disk caching ([901e01a](https://github.com/Tohokantche/faostat-mcp/commit/901e01adc0e56afd95cf695bad553cdd9666412c))
* Upgrade version to 1.2.0 and implement SQLite disk caching ([f579ce6](https://github.com/Tohokantche/faostat-mcp/commit/f579ce6a11e0aa6524d8c4b84804b7dd964abb3d))


### Bug Fixes

* add MCP Registry server.json and ownership verification comment ([e822734](https://github.com/Tohokantche/faostat-mcp/commit/e8227346cb74856504c6ff5b982e8910a8b26508))
* add workflow_dispatch to allow manual PyPI publish trigger ([487f44e](https://github.com/Tohokantche/faostat-mcp/commit/487f44e35f3862f10469a06500d25b9534176f61))
* **client:** __remove_expired_mem_cache nethod loop ([5f1aa08](https://github.com/Tohokantche/faostat-mcp/commit/5f1aa0861705cf20893c298aad862fbb71980678))
* consolidate publish into release-please workflow to bypass GITHUB_TOKEN event restriction ([cf5f7d2](https://github.com/Tohokantche/faostat-mcp/commit/cf5f7d2c943bc766ba93bc6bd8acf6b4fba76e3d))
* faostat_get_codes limit applies to dict API response and is part of cache key ([1dc45df](https://github.com/Tohokantche/faostat-mcp/commit/1dc45dfb31575e3584126235f1bf1ec884c9bda8))
* patch caching_manager in test_faostat_get_codes_no_limits_returns_all to prevent cahce bleed-through from previous test ([e217add](https://github.com/Tohokantche/faostat-mcp/commit/e217add5f9eb89b4161c6b8637e5fa6cd017956c))


### Code Refactoring

* **client:** add flexible setting of caching ttl ([56901f7](https://github.com/Tohokantche/faostat-mcp/commit/56901f73200dedc8e6bf6acb23b5524bf2400344))

## [1.2.2](https://github.com/berba-q/faostat-mcp/compare/v1.2.1...v1.2.2) (2026-04-13)


### Bug Fixes

* add MCP Registry server.json and ownership verification comment ([e822734](https://github.com/berba-q/faostat-mcp/commit/e8227346cb74856504c6ff5b982e8910a8b26508))

## [1.2.1](https://github.com/berba-q/faostat-mcp/compare/v1.2.0...v1.2.1) (2026-04-13)


### Bug Fixes

* add workflow_dispatch to allow manual PyPI publish trigger ([487f44e](https://github.com/berba-q/faostat-mcp/commit/487f44e35f3862f10469a06500d25b9534176f61))
* consolidate publish into release-please workflow to bypass GITHUB_TOKEN event restriction ([cf5f7d2](https://github.com/berba-q/faostat-mcp/commit/cf5f7d2c943bc766ba93bc6bd8acf6b4fba76e3d))

## [1.2.0](https://github.com/berba-q/faostat-mcp/compare/v1.1.1...v1.2.0) (2026-04-13)


### Features

* Upgrade version to 1.2.0 and implement SQLite disk caching ([901e01a](https://github.com/berba-q/faostat-mcp/commit/901e01adc0e56afd95cf695bad553cdd9666412c))

## [1.1.1](https://github.com/berba-q/faostat-mcp/compare/v1.1.0...v1.1.1) (2026-04-13)


### Documentation

* add CHANGELOG.md as baseline for release-please automation ([dacc4b8](https://github.com/berba-q/faostat-mcp/commit/dacc4b8e47943bedca7d7d2f8f3a08a6ed483bdc))

## [1.1.0](https://github.com/berba-q/faostat-mcp/releases/tag/v1.1.0) — 2026-04-13

### Features

* Hybrid server-side caching — in-memory (dict + min-heap TTL tracking) and optional Redis tier, with graceful fallback when Redis is unavailable ([Tohokantche](https://github.com/Tohokantche))
* `faostat_get_data`: new `response_format` parameter (`objects` / `compact` / `csv`) and `fields` filter for column selection
* `faostat_get_codes`: new `limit` parameter for large dimensions (e.g. `item` with 1000+ entries)
* `faostat_get_rankings`: inherits `response_format` and `fields` support
* Token auto-refresh via `/auth/login` endpoint — tokens are renewed transparently when expired
* Issue templates for bug reports and feature requests

### Bug Fixes

* `faostat_get_codes`: `limit` was silently skipped because the FAOSTAT API returns `{"data": [...]}` (a dict), not a plain list — extracted `data` key before applying the limit
* `faostat_get_codes`: `limit` was not part of the cache key, causing a `limit=0` call to return a cached truncated result from a prior `limit=5` call
* `faostat_get_codes`: `set_data` call was missing `arg_dict`, which would have raised `TypeError` on every successful API response
* `HybridCaching.__remove_expired_mem_cache`: fixed TTL-refresh race — now checks expiry matches before deleting

### Code Refactoring

* Extracted `_get_redis_connector()` as a standalone module-level function, making `HybridCaching` reusable independently of Redis configuration
* Replaced `sys._getframe()` with string literals for tool name references throughout server

## [1.0.1](https://github.com/berba-q/faostat-mcp/releases/tag/v1.0.1) — Initial production release

* 18 MCP tools covering the full FAOSTAT API surface
* Rate-limited HTTP client (2 req/s) with exponential backoff auto-retry
* Compatible with Claude Desktop, Claude Code, Cursor, Windsurf, Zed, and any MCP stdio client
* FastMCP-based server with rich tool descriptions for automatic AI tool selection
