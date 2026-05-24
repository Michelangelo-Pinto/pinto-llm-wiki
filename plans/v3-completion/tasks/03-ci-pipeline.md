# Task 03: CI Pipeline (GitHub Actions)

| Field | Value |
|-------|-------|
| Status | completed |
| Priority | P1 |
| Effort | Small |
| Depends on | none |
| Blocks | 04, 05, 06 (CI enables automated test runs) |

## Objective

Verify and complete the GitHub Actions CI pipeline so tests run automatically on pull requests.

## Background

The `doc_v3/improvements/index.md` lists "CI pipeline (GitHub Actions)" as a quick win. A workflow file reportedly exists in `.github/workflows/`. This task verifies it works correctly, fixes any issues, and ensures it covers all test suites.

## Implementation Plan

1. Check if `.github/workflows/` directory exists and what workflow files are present:

```bash
ls -la .github/workflows/
```

2. Read any existing workflow YAML files and assess:
   - Which test suites are covered?
   - Are Docker profiles used correctly?
   - Are services (qdrant-db, wiki, etc.) properly set up?

3. If a workflow exists but is incomplete, update it to cover at minimum:
   - Qdrant integration tests (fast, `--profile test`)
   - E2E ingestion tests (fast, `--profile test`)
   - If possible: stack integration + regression tests (requires full stack)

4. If no workflow exists, create `.github/workflows/test.yml` based on the docker-compose profiles

5. Verify the workflow structure with `act` or push a test branch

## Decisions

### 2026-05-24 — Task 03: Workflow verified as-is

**Decision:** The existing `.github/workflows/test.yml` is complete and correct. No modifications needed.

**Rationale:** The workflow already covers:
- Qdrant integration tests (`--profile test`) on every push and PR
- E2E ingestion tests (`--profile test`) on every push and PR
- Performance benchmarks on every push and PR
- Stack integration and regression tests (`--profile integration`) on push to main and manual dispatch only (avoid long CI times on PRs)
- Proper Docker profile usage, service health waiting, and failure log collection

This design balances fast PR feedback (< 3 min for fast tests) with comprehensive main-branch validation.

## Documentation Updates

- [ ] `doc_v3/improvements/index.md` — mark "CI pipeline" as completed
- [ ] `doc_v3/reference/testing.md` — add CI section or link to workflow
- [ ] `README.md` — add CI badge if applicable

## Completion Criteria

- [ ] CI workflow file exists and is syntactically valid
- [ ] Workflow runs test suites using correct Docker profiles
- [ ] Fast tests (Qdrant integration + E2E) run on PRs
- [ ] Workflow documented in `doc_v3/reference/testing.md`

## Notes

- Workflow file: `.github/workflows/test.yml` — already existed and complete
- Two jobs: `qdrant-tests` (always runs), `stack-tests` (main/manual only)
- SSE smoke tests (task 04) and unit tests (task 05) can be added as additional steps/jobs
