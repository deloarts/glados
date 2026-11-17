import { ref } from 'vue'

// Same base as connectionStore's PROBE_URL: dev talks straight to the
// backend via VITE_API_URL (no vite dev-server proxy exists in this repo),
// production leaves it empty and nginx proxies /health to the backend on
// the same origin (see docker/nginx.conf). Unauthenticated, so this never
// touches the api instance's Authorization header or 401 interceptor.
const HEALTH_URL = `${import.meta.env.VITE_API_URL ?? ''}/health`

// Captures the leading major.minor.patch triplet, so a pre-release suffix
// like '1.2.3-rc.1' still compares on '1.2.3'.
const SEMVER_RE = /^(\d+)\.(\d+)\.(\d+)/

function majorMinorPatch(version: string): string | null {
  const match = SEMVER_RE.exec(version)
  return match ? `${match[1]}.${match[2]}.${match[3]}` : null
}

export interface VersionMismatch {
  client: string
  server: string
}

/**
 * Pure version comparison, kept apart from the fetch below so the "what
 * counts as a mismatch" rule is unit-testable on its own. Returns null
 * whenever either version fails to parse as semver, either one is the
 * unbuilt-dev placeholder ('0.0.0', see vite.config.ts's `define`), or the
 * full major.minor.patch triplets agree. This is a monorepo with a single
 * version file for both halves (scripts/bump_version.sh bumps both
 * together), so any difference, patch included, means a stale cached
 * bundle or a BACKEND_VERSION/FRONTEND_VERSION image override that has
 * drifted out of sync, not an intentional skew to tolerate.
 */
export function getVersionMismatch(client: string, server: string): VersionMismatch | null {
  if (client === '0.0.0' || server === '0.0.0') return null

  const clientKey = majorMinorPatch(client)
  const serverKey = majorMinorPatch(server)
  if (!clientKey || !serverKey || clientKey === serverKey) return null

  return { client, server }
}

function readServerVersion(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const version = (payload as { version?: unknown }).version
  return typeof version === 'string' ? version : null
}

/**
 * Compares this build's version (`__APP_VERSION__`, injected from
 * package.json, see vite.config.ts) against whatever the currently-served
 * backend reports on `/health`, for the persistent version-mismatch banner
 * (VersionMismatchBanner.vue, mounted in AppLayout.vue).
 *
 * The check is fire-and-forget from the caller's point of view: nothing
 * about app boot ever waits on it, and a failed fetch (offline, CORS,
 * backend not up yet) just leaves `mismatch` at null. connectionStore
 * already owns surfacing connectivity problems, this composable's only job
 * is the version nudge, so it never throws or reports failure of its own.
 * `ready` is exposed only so callers (in practice, this composable's own
 * unit tests) can await the one-shot check deterministically; the banner
 * itself ignores it.
 */
export function useVersionCheck(clientVersion: string = __APP_VERSION__) {
  const mismatch = ref<VersionMismatch | null>(null)

  async function check(): Promise<void> {
    let payload: unknown
    try {
      const response = await fetch(HEALTH_URL)
      if (!response.ok) return
      payload = await response.json()
    } catch {
      return
    }

    const serverVersion = readServerVersion(payload)
    if (!serverVersion) return

    mismatch.value = getVersionMismatch(clientVersion, serverVersion)
  }

  const ready = check()

  return { mismatch, ready }
}
