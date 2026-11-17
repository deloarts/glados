# github repository setup

The exact GitHub settings, rulesets and package settings the release flow relies on. Everything here is configured by hand in the repository settings, and no workflow changes it. [RELEASING.md](../RELEASING.md) explains the flow these settings protect.

- [github repository setup](#github-repository-setup)
  - [1 pull requests](#1-pull-requests)
  - [2 actions](#2-actions)
  - [3 rulesets](#3-rulesets)
    - [3.1 main](#31-main)
    - [3.2 release tags](#32-release-tags)
    - [3.3 staging](#33-staging)
  - [4 code security and dependency updates](#4-code-security-and-dependency-updates)
  - [5 packages](#5-packages)

## 1 pull requests

Settings → General → Pull Requests:

- *Allow merge commits* is off.
- *Allow squash merging* is on, with the default message "Pull request title and commit details". Squash is the only merge method, because the release guard relies on a merge commit with a single parent.
- *Allow rebase merging* is off.
- *Always suggest updating pull request branches* is on, which shows the "Update branch" button that release pull requests need.
- *Automatically delete head branches* is on.

## 2 actions

Settings → Actions → General:

- *Workflow permissions* is "Read repository contents and packages permissions". Jobs that write tags, releases or images request it themselves.
- *Allow GitHub Actions to create and approve pull requests* is off.
- *Fork pull request workflows* require approval for all external contributors.

## 3 rulesets

Settings → Rules → Rulesets. Rulesets need a public repository, or a paid plan for a private one.

### 3.1 main

A branch ruleset targeting the default branch:

- It sets *Restrict deletions*, *Block force pushes* and *Require linear history*.
- It sets *Require a pull request before merging* with 0 approvals and Squash as the only allowed merge method.
- It sets *Require status checks to pass* with *Require branches to be up to date before merging* enabled and the checks `backend-verify`, `frontend-verify`, `plan-refs`, `version-parity`, `api-types`, `gitleaks` and `release-check`. A check can only be picked once it has run at least once.
- `plan-refs` is a separate job that no other job depends on, so it blocks a merge only when the ruleset lists it, and it has to be added to the ruleset by hand.
- The up-to-date requirement is what keeps a release branch from being merged behind `main`.

### 3.2 release tags

A tag ruleset named `release tags`, targeting `v*`:

- It sets *Restrict updates*, *Restrict deletions* and *Block force pushes*, with Repository admin as bypass.
- Creation stays unrestricted because the release workflow creates the tags, and a tag created by hand publishes nothing.
- Release tags are immutable once pushed. If a release turns out to be wrong, the fix is a new patch, not touching the tag.

### 3.3 staging

A branch ruleset targeting `staging`:

- It sets *Restrict creations*, *Restrict updates* and *Restrict deletions*, with Repository admin as bypass set to *Always allow*, so only maintainers can deploy to staging.
- It does not require a pull request and does not block force pushes, because force-pushing is the deploy mechanism ([RELEASING.md section 4.2](../RELEASING.md#42-deploying-to-staging)).
- `release/**` branches need no ruleset of their own, because they end in a pull request into `main` gated by the `main` ruleset.

## 4 code security and dependency updates

- Settings → Code security has Dependabot alerts, secret scanning with push protection, and private vulnerability reporting on.
- Dependabot security updates stay off and the repository has no `dependabot.yml`. Dependabot only raises alerts and never opens pull requests, and dependencies are updated by hand, with CI's audits failing on known vulnerabilities.
- `xlsx` is the exception the audits miss. `frontend/package.json` installs it from the SheetJS CDN tarball, not from the npm registry, so `npm audit` and Dependabot never see it. Check the SheetJS releases and advisories by hand whenever the frontend dependencies are updated, and move the tarball URL to the new version when one is out.

## 5 packages

- Pushed images land under the repository owner's GHCR packages, at `ghcr.io/<owner>/glados/backend` and `ghcr.io/<owner>/glados/frontend`.
- Each package's visibility is set once in its package settings and kept for every later tag. Both must be public, so a deployment pulls them without credentials. A container package that a workflow's first push creates usually starts out private even when the repository is public, so after the first push of `glados/backend` and `glados/frontend` open each package's settings and change its visibility to public.
- `ghcr-retention.yml` deletes old `sha-<commit>` versions with the workflow token ([releasing-ci.md section 1.5](releasing-ci.md#15-the-ghcr-retention-workflow)). The job asks for `packages: write`, but the token can delete a version only when the repository holds the Admin role on the package. Set it in each package's settings under *Manage Actions access* for `glados/backend` and `glados/frontend`. Admin includes the Write role the publishing jobs need to push.
