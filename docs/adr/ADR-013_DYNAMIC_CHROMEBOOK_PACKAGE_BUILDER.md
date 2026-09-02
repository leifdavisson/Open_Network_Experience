# Architecture Decision Record (ADR)
**Decision ID:** ADR-013
**Title:** In-Memory Dynamic Chromebook Extension Packaging and Version Monotonicity
**Status:** Accepted
**Date:** September 02, 2026
**License:** [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Context & Problem Statement
ChromeOS enterprise force-installation via Google Workspace Admin Console requires packaged extension zip archives. Static pre-built zip files have hardcoded versions (e.g. `1.0.0`) and hardcoded fallback URLs (`localhost:8000`), preventing Google Admin from accepting subsequent update uploads (which mandate strict monotonic version increases) and burdening IT administrators with complex manual JSON policy configuration.

## Decision
1. **Dynamic In-Memory Assembly**: The CMP dynamically archives the `chromebook-sensor` extension directory in-memory via `io.BytesIO` and `zipfile`, stripping `.git`, `node_modules`, and test fixtures.
2. **Monotonic Version Injection**: The builder intercepts `manifest.json` on the fly, auto-bumping the version using `1.YYYY.MMDD.HHMM` formatting. This strictly complies with Chrome's 4-tuple versioning limit where each integer cannot exceed `65535`.
3. **Zero-Touch Config Embedding**: The builder intercepts `src/background/config_manager.js` and injects the admin-verified CMP server URL directly into `DEFAULT_CONFIG`.
4. **Pre-Flight Blast-Radius Validation**: The web dashboard executes a client-side pre-flight probe (`/api/v1/health`) against the admin-specified address before generation to verify reachability and alert against IP typos that could isolate the fleet.

## Alternatives Considered
- **Static Pre-Built Releases on Disk**: Rejected because every deployment requires distinct CMP endpoints and manual build steps.
- **Requiring Google Admin Managed Storage Policies**: Kept as an optional override, but rejected as a hard requirement due to administrative overhead for K-12 district IT staff.

## Consequences & Trade-offs
- **Pros**: Zero-touch deployment out of the box; eliminates version upload rejection in Google Admin Console; prevents fleet isolation due to configuration typos.
- **Cons**: Small CPU/memory overhead during dynamic zip construction on download requests.
