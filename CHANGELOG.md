# Changelog

All notable changes to this project are documented here.
Releases from v1.1.0 onwards are generated automatically from [conventional commits](https://www.conventionalcommits.org) by [release-please](https://github.com/googleapis/release-please).

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
