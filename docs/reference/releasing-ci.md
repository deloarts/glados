# ci and release workflows

What `ci.yml`, `nightly.yml` and `release.yml` check and publish on each trigger, and the exact rules of the `pat` snapshot check. [RELEASING.md](../RELEASING.md) explains the release flow these workflows serve, and [ADR 0004](../adr/0004-trunk-based-release-flow.md) explains why it is trunk-based.

- [ci and release workflows](#ci-and-release-workflows)
  - [1 the ci workflow](#1-the-ci-workflow)
    - [1.1 triggers and path filters](#11-triggers-and-path-filters)
    - [1.2 jobs](#12-jobs)
    - [1.3 channel images](#13-channel-images)
    - [1.4 the nightly workflow](#14-the-nightly-workflow)
    - [1.5 the ghcr retention workflow](#15-the-ghcr-retention-workflow)
  - [2 the pat snapshot check](#2-the-pat-snapshot-check)
    - [2.1 the snapshots](#21-the-snapshots)
    - [2.2 step a, snapshot against the live schema](#22-step-a-snapshot-against-the-live-schema)
    - [2.3 step b, snapshot against the released minor](#23-step-b-snapshot-against-the-released-minor)
    - [2.4 the frontend half](#24-the-frontend-half)
  - [3 the release workflow](#3-the-release-workflow)
  - [4 release scripts](#4-release-scripts)

## 1 the ci workflow

### 1.1 triggers and path filters

- `ci.yml` runs on every pull request and on pushes to `staging` and `release/**`.
- `main` has no push trigger, since every change reaches it as a squash-merged pull request whose checks already ran. The `main` ruleset only merges a pull request whose checks passed against the current `main`, so the squash commit's tree is exactly what was tested.
- A pull request that touches only `docs/` or the root `scripts/` runs no code job (`backend-*`, `frontend-*`, `api-types`). A skipped job counts as passing for a required check, and `plan-refs` still scans the docs.
- A push to `staging` or a `release/**` branch runs every check job regardless of the path filter.
- A red check does not close the pull request. Fix it and push again, and CI re-runs.

### 1.2 jobs

| Job | What it does |
| --- | ------------ |
| `backend-tests` | Runs pytest in four parallel shards. The first shard then runs the backup and restore drill (`tests/pg/test_backup_restore_drill.py`) against its Postgres service on every run, and the rest of `tests/pg`, the race tests and the Postgres-only queries, only for a `release/**` branch. |
| `backend-verify` | Requires all shards to have passed and runs pip-audit, ruff, the format check, mypy, import-linter, the complexipy ceiling of 25 per function, a report-only function length listing, the combined coverage gate, the [pat snapshot check](#2-the-pat-snapshot-check) with `--strict` and a check for a single Alembic head. |
| `frontend-tests` | Runs the frontend unit tests with coverage in three parallel shards. Vitest assigns whole spec files to a shard; each shard writes a blob report and leaves the coverage thresholds off, since it covers only part of `src`. |
| `frontend-verify` | Requires all shards to have passed, runs npm audit and type-check, merges the shard reports with `npm run test:coverage:merge` so the coverage thresholds apply to the whole suite, and builds. Lint and the i18n parity check, which fails on a key missing in either locale, ran in `quick-checks`. |
| `plan-refs` | Runs `scripts/check_plan_refs.py`, which rejects planning labels in comments and docs. |
| `version-parity` | Checks that `backend/pyproject.toml` and `frontend/package.json` carry the same version. |
| `api-types` | Checks that the frontend's generated types match the committed `web` snapshot. |
| `gitleaks` | Scans the history for secrets. |
| `release-check` | Runs on release branches only and is skipped, which counts as passing, for every other branch. It runs `scripts/check_release_version.sh` (the version is `0.Y.Z`, both version files carry it, `CHANGELOG.md` has its section and the tag is still free) and verifies that the branch contains the current `main`. |
| `publish-channel-image` | Publishes a channel image after a push to `staging` or `release/**` ([section 1.3](#13-channel-images)). |

The race tests run only on release branches because, at over 20 minutes, they are the longest step. `nightly.yml` runs them on `main` every night ([section 1.4](#14-the-nightly-workflow)).

### 1.3 channel images

- On a push to `staging` or `release/**`, `publish-channel-image` runs only once every check job has passed, plus `release-check` for a release branch.
- It publishes the `staging` or `release-candidate` channel tag for the backend and frontend images.
- A release branch's images also get the tag `sha-<commit>`, the full hash of the branch head they were built from. Unlike the channel tag it never moves to another build, and it exists only once every check passed for that commit, so `release.yml` finds the tested images by it ([section 3](#3-the-release-workflow)).
- A red run publishes nothing, so the server keeps running whatever it had before.
- A channel is not a release: there is no `guard` job and no version tag, and `vX.Y` and `latest` stay untouched.

### 1.4 the nightly workflow

- `nightly.yml` runs every night at 02:17 UTC on `main`, and on demand on any branch through *Run workflow*.
- It runs every test in `backend/tests/pg` against an empty `postgres:16` service: the backup and restore drill in one step, then the race tests and the tests of Postgres-only queries, such as the global search's trigram tier, in another.
- GitHub mails a failed scheduled run to whoever last changed the workflow's schedule.

### 1.5 the ghcr retention workflow

- `ghcr-retention.yml` runs every Monday at 03:43 UTC and runs `scripts/ghcr_retention.sh` for `glados/backend` and `glados/frontend`.
- In each package it keeps the newest 30 versions whose tags all start with `sha-` ([section 1.3](#13-channel-images)) and deletes the older ones.
- A version that carries any other tag is never deleted. A release tag (`vX.Y.Z`, `vX.Y`, `latest`) means a release promoted that very digest ([section 3](#3-the-release-workflow)), and a channel tag (`staging`, `release-candidate`) means a test server may run it. Every released image therefore stays, since its `vX.Y.Z` tag never moves.
- An image index is published with its platform manifest and its provenance attestation as untagged versions. Those go with a deleted index, unless a version that stays lists them too. Other untagged versions, such as a `staging` build the channel tag has moved past, are left alone.
- A release pull request whose candidate has fallen out of the newest 30 cannot be released, because `resolve` no longer finds its `sha-<candidate>` tags. Push the release branch again to publish a new candidate.
- *Run workflow* starts it on demand on any branch, as a dry run that only lists the versions unless the box is cleared. The step summary counts what was deleted per package.
- A deleted version can be restored from the package settings for 30 days. The token needs the Admin role on each package ([releasing-github-setup.md section 5](releasing-github-setup.md#5-packages)); without it the deletions fail and the run fails.

## 2 the pat snapshot check

`backend/scripts/check_openapi.py` runs in `backend-verify` and enforces that a patch release does not change the `pat` contract. It runs step A, then step B.

### 2.1 the snapshots

- `backend/openapi/pat-v{major}.{minor}.json` holds the `pat`, `key` and `public` surfaces combined. It is the frozen external contract used by outside integrations such as the SolidWorks add-in.
- `backend/openapi/web-v{major}.{minor}.json` holds the `web` surface, which only `frontend/` consumes.
- Only the current minor's pair exists in the tree at a time.
- `poetry run python scripts/export_openapi.py` (from `backend/`) always overwrites both tracked snapshot files for the current minor and deletes any other minor's leftover files, so after a minor bump only the new minor's `openapi/pat-vX.Y.json` and `openapi/web-vX.Y.json` remain committed.
- The `export-openapi` pre-commit hook re-exports the snapshots and regenerates the frontend's API types on every commit that touches `backend/`.

### 2.2 step a, snapshot against the live schema

- Each committed snapshot must equal the live `app.openapi()` schema for its own surface exactly, for both surfaces.
- It fails whenever a route or schema change has not been re-exported yet.
- The fix is `poetry run python scripts/export_openapi.py`, then committing the updated files.

### 2.3 step b, snapshot against the released minor

- Once any `v{major}.{minor}.*` tag exists (for example once `v0.2.0` has been released), the `pat` snapshot must be byte-identical to what it was at the first tag for that minor.
- It fails when the `pat` contract changed after that minor was already released, which means someone is trying to ship an API change as a patch.
- The `web` snapshot is exempt from this step and may change on any commit.
- The fix is not a re-export. The change needs a minor bump, `scripts/bump_version.sh 0.Y.0` for the next minor, which has no release tag yet so step B does not apply to it, followed by `poetry run python scripts/export_openapi.py`, in the same pull request ([RELEASING.md section 3](../RELEASING.md#3-minor-releases)). The failure message names the exact bump command.
- Step B fails closed under `--strict`, which `backend-verify` passes and which a `CI` or `GITHUB_ACTIONS` environment variable set to `true` turns on as well. A failed `git fetch --tags` or a `pat` snapshot missing at the released tag then fails the check, since either would otherwise skip the freeze unseen.
- Without `--strict`, as when run locally, both only print a warning and the check passes, so it still works offline.

### 2.4 the frontend half

`npm run check:api-types`, run from `frontend/` in the `api-types` job, regenerates `src/core/api/generated/webSchema.ts` from the committed `web` snapshot and fails if the result is not what is already committed. No backend needs to be running for it. `npm run generate:api-types` performs the same regeneration and writes the file.

## 3 the release workflow

`release.yml` runs when a release pull request is merged, in six jobs. It publishes the release candidate's images, never a rebuild:

- `guard` accepts only a merged pull request from a `release/0.Y.Z` branch of this repository and reruns `check_release_version.sh` on the merge commit. It takes the pull request's head commit as the candidate and checks that the release branch contained `main` as it was right before the merge and that the merge commit holds the same tree as the candidate, so the candidate's images are exactly the tagged code.
- `resolve` finds the candidate's images by their `sha-<candidate>` tags ([section 1.3](#13-channel-images)) and reads their digests. A release pull request can be merged while the release branch's own push run is still building, so it waits up to 50 minutes for the tags to appear and fails after that.
- `smoke` runs `scripts/smoke_release_images.sh` with the two digests: it starts the release `docker-compose.yml` with an empty Postgres and Redis and throwaway secrets, lets the entrypoint migrate, and requires the backend to report the release version on `/health` and answer `/ready` with 200, nginx to accept its configuration, and the frontend to serve the app and proxy `/health` and `/ready`. The script runs locally against any two images as well.
- `tag` creates the annotated tag `vX.Y.Z` on the merge commit, only once `smoke` passed, so a failing guard, resolve or smoke tags nothing.
- `publish` gives each digest the tags `vX.Y.Z`, `vX.Y` and `latest` on `ghcr.io/<owner>/glados/backend` and `ghcr.io/<owner>/glados/frontend` with `docker buildx imagetools create --prefer-index=false`, which copies the manifest as it is, and checks that each tag then names the tested digest.
- `github-release` creates the GitHub Release for the tag, its notes taken from the matching `CHANGELOG.md` section.

The recovery dispatch on `main` takes the candidate from the merged `release/X.Y.Z` pull request whose squash commit is `main`'s head, and refuses when `main` has moved on, since no tested candidate exists for any other commit.

Tagging and publishing run in one workflow because a tag pushed with the workflow token does not start other workflows. For the same reason a tag pushed by hand publishes nothing. Every image, channel and release alike, carries OCI labels set by `docker/metadata-action` when the channel image is built, which [RELEASING.md section 4.5](../RELEASING.md#45-which-commit-is-running) uses to find the running commit; a release image keeps the labels of its candidate.

## 4 release scripts

- `scripts/bump_version.sh X.Y.Z` runs `poetry version X.Y.Z` in `backend/` and `npm version X.Y.Z --no-git-tag-version` in `frontend/`, so both version files change together.
- The bump script accepts any `X.Y.Z`, the major included. Only `scripts/release_start.sh` and `scripts/check_release_version.sh` insist on `0.Y.Z`, so a wrong major passes the bump and fails once the release branch is started or checked.
- The major stays `0` until a deliberate `1.0`. That step changes the `0.Y.Z` pattern in both scripts, in the `guard` job of `.github/workflows/release.yml` and in the release branch check of `.github/workflows/ci.yml` together.
