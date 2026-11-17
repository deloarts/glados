#!/usr/bin/env bash
# Delete the oldest release candidate images from GHCR. Every push to a
# release branch publishes the backend and frontend images with an
# immutable `sha-<commit>` tag (ci.yml), and nothing else ever removes them.
# This keeps the newest GHCR_KEEP versions per package whose tags all start
# with `sha-` and deletes the older ones. A version that carries any other
# tag is never touched: a release tag (vX.Y.Z, vX.Y, latest) means a release
# promoted that very digest, and a channel tag (staging, release-candidate)
# means a test server may be running it. Untagged versions are left alone,
# except the platform and attestation manifests of a deleted image index,
# which go with it unless a version that stays references them too. Used by
# ghcr-retention.yml; runs locally with a token that may delete packages.
#
# Usage: scripts/ghcr_retention.sh OWNER [PACKAGE...]
#
#   OWNER            the lowercase GHCR owner, a user or an organization
#   PACKAGE          package names under ghcr.io/OWNER/ (default
#                    glados/backend glados/frontend)
#   GHCR_KEEP        sha-only versions kept per package (default 30)
#   GHCR_DRY_RUN     "true" prints what would be deleted and deletes nothing
#
# Needs `gh` authenticated (GH_TOKEN) with read and delete access to the
# packages, `jq`, and `docker buildx` able to read the images' manifests.
set -euo pipefail

USAGE="usage: ghcr_retention.sh OWNER [PACKAGE...]"
OWNER="${1:?$USAGE}"
shift
if (($# > 0)); then
  PACKAGES=("$@")
else
  PACKAGES=(glados/backend glados/frontend)
fi
KEEP="${GHCR_KEEP:-30}"
DRY_RUN="${GHCR_DRY_RUN:-false}"

if ! [[ "$KEEP" =~ ^[0-9]+$ ]] || ((KEEP < 1)); then
  echo "::error::GHCR_KEEP must be a whole number of at least 1, not '$KEEP'." >&2
  exit 1
fi

if [[ "$(gh api "users/$OWNER" --jq .type)" == "Organization" ]]; then
  SCOPE="orgs/$OWNER"
else
  SCOPE="users/$OWNER"
fi

# The digests an image index lists as its manifests, none for a plain image
# manifest. The registry answers by digest, so a deleted tag does not matter.
child_digests() {
  docker buildx imagetools inspect --raw "ghcr.io/$OWNER/$1@$2" </dev/null \
    | jq -r '.manifests[]?.digest'
}

failures=0
summary=""

for package in "${PACKAGES[@]}"; do
  encoded="${package//\//%2F}"
  endpoint="$SCOPE/packages/container/$encoded/versions"
  versions="$(gh api --paginate "$endpoint?per_page=100" \
    --jq '.[] | {id, digest: .name, created_at, tags: (.metadata.container.tags // [])}' | jq -s .)"

  # Versions whose every tag starts with sha-, newest first; the ones past
  # the first GHCR_KEEP are deleted. Every other tagged version stays.
  doomed="$(jq --argjson keep "$KEEP" '
    [.[] | select((.tags | length) > 0 and all(.tags[]; startswith("sha-")))]
    | sort_by(.created_at) | reverse | .[$keep:]' <<<"$versions")"
  doomed_count="$(jq length <<<"$doomed")"
  if ((doomed_count == 0)); then
    echo "$package: nothing to delete."
    summary+="| $package | 0 | 0 |"$'\n'
    continue
  fi

  # Manifests a remaining tagged version still references must stay, even
  # when a doomed index lists them as well.
  declare -A referenced=()
  while read -r digest; do
    while read -r child; do
      if [[ -n "$child" ]]; then
        referenced["$child"]=1
      fi
    done < <(child_digests "$package" "$digest")
  done < <(jq -r --argjson doomed "$doomed" '
    ($doomed | map(.id)) as $ids
    | .[] | select((.tags | length) > 0 and (.id as $id | $ids | any(. == $id) | not))
    | .digest' \
    <<<"$versions")

  deleted=0
  deleted_children=0
  while read -r entry; do
    id="$(jq -r .id <<<"$entry")"
    digest="$(jq -r .digest <<<"$entry")"
    tags="$(jq -r '.tags | join(", ")' <<<"$entry")"
    children="$(child_digests "$package" "$digest")"

    if [[ "$DRY_RUN" == "true" ]]; then
      echo "$package: would delete $digest ($tags)"
    elif gh api -X DELETE "$endpoint/$id" </dev/null >/dev/null; then
      echo "$package: deleted $digest ($tags)"
    else
      echo "::warning::$package: could not delete $digest ($tags)." >&2
      failures=$((failures + 1))
      continue
    fi
    deleted=$((deleted + 1))

    while read -r child; do
      if [[ -z "$child" || -n "${referenced[$child]:-}" ]]; then
        continue
      fi
      child_id="$(jq -r --arg digest "$child" \
        '.[] | select(.digest == $digest and (.tags | length) == 0) | .id' <<<"$versions")"
      if [[ -z "$child_id" ]]; then
        continue
      fi
      if [[ "$DRY_RUN" == "true" ]]; then
        echo "$package:   would delete its manifest $child"
      elif gh api -X DELETE "$endpoint/$child_id" </dev/null >/dev/null; then
        echo "$package:   deleted its manifest $child"
      else
        echo "::warning::$package: could not delete the manifest $child of $digest." >&2
        failures=$((failures + 1))
        continue
      fi
      deleted_children=$((deleted_children + 1))
    done <<<"$children"
  done < <(jq -c '.[]' <<<"$doomed")
  unset referenced

  summary+="| $package | $deleted | $deleted_children |"$'\n'
done

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    if [[ "$DRY_RUN" == "true" ]]; then
      echo "Dry run, nothing was deleted. Kept the newest $KEEP sha-only versions per package."
    else
      echo "Kept the newest $KEEP sha-only versions per package."
    fi
    echo
    echo "| Package | Tagged versions | Their manifests |"
    echo "| ------- | --------------- | --------------- |"
    printf '%s' "$summary"
  } >>"$GITHUB_STEP_SUMMARY"
fi

if ((failures > 0)); then
  echo "::error::$failures deletions failed; check that the repository has the Admin role in each package's Manage Actions access." >&2
  exit 1
fi
