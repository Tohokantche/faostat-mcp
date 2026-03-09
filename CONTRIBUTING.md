# Contributing to the FAOSTAT MCP project

**_"Two heads are better than one..."_** | **_"Too muxh meat does not spoil the soup"_** These are two sayings that guide my priniciple of contribution! I would be really happy to collaborate on making this an even better product. This document covers the guidelines contributions including submitting issues, proposing features, and opening pull requests.

## Table of Contents

- [Getting Started](#getting-started)
- [Conventional Commits](#conventional-commits)
- [Branch Naming](#branch-naming)
- [Pull Request Process](#pull-request-process)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)

---

## Getting Started

1. Fork the repository and clone your fork.
2. Create a new branch from `main` (see [Branch Naming](#branch-naming)).
3. Make your changes, following the code style and commit conventions below.
4. Open a pull request against `main`.

---

## Conventional Commits

All commits **must** follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification. This enables automated changelog generation and semantic versioning.

### Format

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types

| Type       | When to use                                                        |
|------------|--------------------------------------------------------------------|
| `feat`     | A new feature                                                      |
| `fix`      | A bug fix                                                          |
| `docs`     | Documentation changes only                                         |
| `style`    | Formatting, whitespace — no logic change                           |
| `refactor` | Code restructuring with no feature or bug change                   |
| `perf`     | A change that improves performance                                 |
| `test`     | Adding or correcting tests                                         |
| `chore`    | Build process, dependency updates, tooling                         |
| `ci`       | CI/CD configuration changes                                        |
| `revert`   | Reverts a previous commit                                          |

### Scopes (optional but encouraged)

Use a scope to narrow the area of change, e.g.:

```
feat(server): add bulk-download tool
fix(client): handle token expiry on 401 response
docs(readme): add Claude Desktop configuration example
```

### Breaking Changes

Append `!` after the type/scope, or add a `BREAKING CHANGE:` footer:

```
feat(auth)!: remove legacy API key support

BREAKING CHANGE: the `FAOSTAT_API_KEY` env variable is no longer read.
Use `FAOSTAT_USERNAME` and `FAOSTAT_PASSWORD` instead.
```

### Examples

```
feat(server): expose /data/bulk endpoint as MCP tool
fix(client): retry on transient 503 responses
docs: update MCP config example in README
chore: bump httpx to 0.28
test(client): add coverage for token refresh failure path
```

---

## Branch Naming

Use the pattern `<type>/<short-slug>`:

```
feat/bulk-download-tool
fix/token-refresh-loop
docs/contributing-guide
chore/upgrade-httpx
```

---

## Pull Request Process

1. Ensure all tests pass locally before opening a PR.
2. Write a clear PR title that also follows the Conventional Commits format.
3. Reference any related issues with `Closes #<issue-number>` in the PR body.
4. Keep PRs focused — one logical change per PR makes review faster.
5. A maintainer will review and may request changes before merging.

---

## Development Setup

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.\.venv\Scripts\activate         # Windows

# Install the package with dev dependencies
pip install -e ".[dev]"

# Copy and configure environment variables
cp .env.example .env
```

---

## Running Tests

```bash
pytest
```

To run only unit tests (no live API calls):

```bash
pytest tests/ -k "not prod"
```

---

## Reporting Issues & Requesting Features

Please use the GitHub issue templates:

- **Bug report** — for unexpected behaviour or errors.
- **Feature request** — for new tools, endpoints, or improvements.

Both templates are available when you click **New Issue** in the GitHub repository.
