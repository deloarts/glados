# 0004 trunk-based flow with release PRs that tag on merge

- Status: accepted
- Date: 2026-10-05

## context

The repository used a GitFlow-style flow with a long-lived `development` branch, release branches and hand-pushed tags. For a small team this meant merge bookkeeping between long-lived branches and tags that could point at a commit nobody had tested.

## decision

Work branches start from `main` and are squash-merged into it through a pull request; squash is the only merge method. A release is a pull request from `release/X.Y.Z` that carries only the version bump. Merging it is the release: `release.yml` tags the squash commit `vX.Y.Z` and builds and publishes the images in the same run, after checking that the release branch contained the current `main`. Nobody pushes tags by hand. Backend and frontend share one version `0.Y.Z`, where the minor changes exactly when the `pat` API contract changes. gitleaks runs as a pre-commit hook and as a CI job.

## consequences

`main` always holds reviewed history that can ship, and the tagged commit is the one the release-candidate image was built from. Unfinished work has to stay on its branch or hide behind a host capability flag, and a branch that lives through a release must be rebased. The flow, the version policy and the recovery path for a failed tag run are in [RELEASING.md](../RELEASING.md).
