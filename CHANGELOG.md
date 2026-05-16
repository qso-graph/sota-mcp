# Changelog

All notable changes to `sota-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
