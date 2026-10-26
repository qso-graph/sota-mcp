# Changelog

All notable changes to `sota-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Python 3.11 is the minimum.** 3.10 reached end of life in October 2026
  ([PEP 619](https://peps.python.org/pep-0619/)), so it gets no further security
  releases on any platform. On Windows it was worse than unsupported: `uv`'s 3.10
  is built against OpenSSL 1.1.1w, end of life since September 2023, so HTTPS
  from this server ran over an unmaintained TLS library. `certifi` does not help
  with that — it supplies the root store, not the implementation.

  3.10 support was already nominal. This package has linted with
  `ruff target-version = "py311"` and type-checked with `mypy python_version =
  "3.11"` for some time, so nothing ever verified the 3.10 claim.

  `uv.lock` is regenerated and the diff is large, but **nothing is upgraded** —
  it is the 3.10 resolution branch disappearing. Packages that carried two pins,
  one per Python branch, now carry the single 3.11+ pin they already resolved to.
  An install on 3.11 or later is unchanged.

## [0.2.3] — 2026-10-26

### Changed

- `--transport streamable-http` now says where it bound, and the help text says
  it too. It binds `127.0.0.1`, and FastMCP takes no host option, so it was
  never reachable from another machine or from outside a container — and nothing
  said so. The bind address is unchanged: loopback-only is deliberate for a
  server that holds credentials and has no authentication of its own.

## [0.2.2] — 2026-10-26

### Fixed

- `--version` and `--help` now print and exit. They were ignored, so the
  command started the MCP server on stdio and waited for JSON-RPC — leaving a
  FastMCP banner on screen and an apparently hung terminal. Seven servers in
  this fleet already behaved correctly; this brings the rest in line, and a
  test asserts it.

## [0.2.1] — 2026-10-26

- A release should appear on the Releases page
- Move every Node 20 action to its first Node 24 major
- The locked-dependency audit blocked every release
- Four upgrades arrived as 57 pull requests
- Nothing was auditing the lockfile
- Close every open security advisory in the lockfile
- A release is a workflow, not a merge
- Make the publish gate's http:// check portable
- Assert that certifi is declared, not merely imported

## [0.2.0] — 2026-10-12

**Upgrading:** a tool that fails now returns `isError: true` instead of a successful result whose
payload contained an `error` key. Anything reading `result["error"]` should read the error flag.

**Behaviour change worth knowing about:** `sota_summit_info` used to answer "Not found" whenever
anything went wrong — SOTA unreachable, SOTA answering 500, or the summit genuinely not existing.
It now tells those apart. A caller that treated "Not found" as proof a summit does not exist was
being misled during an outage, and will now be told the request failed instead.


- **`E501` is adopted** (#21, qso-graph-devel#70). It reported **one line**, in `tests/conftest.py`,
  and it reflowed. No defect, no exemption, no `noqa` anywhere in the repo. Formatting and config
  only; the suite is unchanged.

- **`certifi` is carried, and the fetch verifies against it** (#20, qso-graph-devel#73). It used
  `urllib` with no context, so it trusted whichever root store the running Python was built
  against. On macOS that is `/etc/ssl/cert.pem`, a deliberately *reduced* OpenSSL file — 128 roots
  against the system keychain's 158, and current rather than stale. **api2.sota.org.uk verifies
  fine against it today**, so this was latent rather than an outage.
- This server carries no credential, so a trust failure costs an answer rather than a secret — but
  it would cost it **invisibly**, with the user told only that the request failed and nothing
  pointing at trust. Verification is never disabled: `ssl.CERT_NONE` would accept any certificate
  from anyone, which is a worse defect than the one being fixed.
- **`urllib.error` is imported** rather than relied on as a side effect of importing
  `urllib.request`. It was already being caught, after #22 added the 404 handling.
- **`tests/test_release_gate.py`** asserts the gate suite imports nothing but the standard library
  and pytest. solar-mcp's 0.3.0 publish failed on exactly that, from the same change.

- **Fixed: a SOTA outage was reported as "no such summit"** (#22). `summit_info` wrapped its fetch
  in `except RuntimeError: data = None` and then answered `{"summitCode": ..., "error": "Not
  found"}`, so three different facts arrived identically: SOTA unreachable, SOTA answering 500, and
  the summit genuinely not existing. The one reported was wrong for two of them, and a caller told
  "no such summit" during an outage concludes the summit does not exist. **The catch was doing real
  work** — SOTA answers 404 for an unknown summit — so 404 is now told apart from everything else
  rather than the catch being deleted.
- **Tool execution errors are flagged `isError`** (#22). Every tool returned `{"error": "..."}` on
  failure, which reaches a client as a *successful* call whose payload happens to contain the word
  "error". They now raise `ToolError`.
- **A failed fetch names what it could not reach**, and why: `SOTA API request failed (<url>):
  <reason>` rather than a bare `SOTA API request failed`.
- **Every tool declares all four annotation hints** (#22). All five are read-only, non-destructive
  and idempotent — this server writes nothing and holds no credential at all. `openWorldHint` is
  true for the four that reach `api2.sota.org.uk` and false for `get_version_info`.
- **`tests/test_mcp_conformance.py`** asserts all of the above, including both directions of the
  outage/absence distinction: an unreachable API and a 500 must *not* say "no such summit", and a
  404 and an empty body must.

## [0.1.10] — 2026-10-11

- **ruff and mypy run in CI** (qso-graph-devel#66), as a job the `ci-all-green` gate requires.
  Settings follow `adif-mcp`, the reference for every qso-graph Python repo, rather than a style of
  this repo's own. They run once rather than per Python version: both read the source, and neither
  answer changes with the interpreter.
- Typed what mypy could not check: the `_MOCK_*` constants are JSON stand-ins and were being
  inferred as `dict[str, object]`, which made every `.get()` on a mock unusable — `object` has no
  `.upper()`. Six cache reads and a `.get()` on an untyped response were handing back `Any` from
  functions promising a list or a dict.
- `E501` is deferred rather than adopted (qso-graph-devel#70): what it reports in these repos are
  widths, not defects, and some lines are long because they name a publisher's field exactly.
- `mcp.run` is given the literal fastmcp asks for rather than a `str` that happens to hold the
  right word.
- **`fastmcp` is bounded: `>=4.0,<5`** (qso-graph-devel#60). It was `>=3.0` with no upper bound, and
  these servers are run with `uvx`, which resolves fresh — so a `fastmcp` 5.0 would have reached
  every user automatically, before anything here had been run against it. The floor rises to 4.0
  because that is what is actually tested: every lock in the fleet held a 4.x, and nothing in CI
  has ever exercised 3.x. A claim of 3.x support that no test backs is not support.
- `fastmcp` is locked at 4.1.0, the current release, so CI runs against what a new install gets.
- **The published contact is `maintainers@qso-graph.io`** (qso-graph-devel#69). The `authors` field
  carried a personal address, and that field is what PyPI shows on the package page. Everything in
  qso-graph is open source and open to contribution, so the contact is the project's.

## [0.1.9] — 2026-10-07

- LICENSE: the full GPL-3.0 text. The file held only its opening and a link, so GitHub detected no licence.

## [0.1.8] — 2026-10-06

- PyPI: the Documentation link goes to this package's own page, https://qso-graph.io/servers/sota/ (qso-graph/.github#15).
- CI: the release flow (qso-graph/.github TEMPLATES.md). Work lands on `develop`; a release is a
  PR from `develop` into `main`, and merging it publishes to PyPI and the MCP Registry, verifies both
  and tags the release. CI runs on `develop` too, and PRs into `main` must come from `develop` or a
  `security/` branch.

## [0.1.7] — 2026-09-28

### Added (CI hygiene)

- **MCP Registry sync** — `publish.yml` publishes to the [Official MCP Registry](https://registry.modelcontextprotocol.io)
  after each PyPI publish, using GitHub OIDC for auth. Triggered on
  `v*` tag push; no manual steps. The Registry job waits until PyPI
  serves the version, and retries. Pattern documented in
  [qso-graph/.github/TEMPLATES.md](https://github.com/qso-graph/.github/blob/main/TEMPLATES.md).
- **Registry version badge** in README — PyPI and Registry versions
  are visible side-by-side so any drift between publishing surfaces
  is immediately apparent.
- **Release gates** — the tag must match `pyproject.toml`, and a
  `verify` job fails the release unless PyPI and the MCP Registry
  both serve the new version.

### Fixed

- The Official MCP Registry listed sota-mcp at 0.1.1. This release brings it current.

## [0.1.6] — 2026-05-15

### Added
- New tool `get_version_info` — returns `{service_name, service_version, spec_version}`
  for fleet identity attestation. Lets agents detect version drift across MCP
  deployments without going outside the protocol. Tracks
  [IONIS-AI/ionis-devel#49](https://github.com/IONIS-AI/ionis-devel/issues/49).
- `__spec_version__` constant pinned to `sota-api2-v1`.
- L2 unit tests SOTA-L2-036 through SOTA-L2-040.
- `.github/workflows/ci.yml` — PR-gating CI (py3.10-3.13 matrix).

### Changed
- `__init__.py` modernized to the fleet pattern (`Final` types,
  explicit `PackageNotFoundError` handling).

## [0.1.5] — Previous release
- See git history for changes prior to the changelog being introduced.
