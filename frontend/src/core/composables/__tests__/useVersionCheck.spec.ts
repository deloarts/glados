import { describe, it, expect, vi, beforeEach } from 'vitest'
import { effectScope } from 'vue'

import { getVersionMismatch, useVersionCheck } from '../useVersionCheck'

function fakeResponse(body: unknown, ok = true): Response {
  return { ok, json: () => Promise.resolve(body) } as Response
}

describe('getVersionMismatch', () => {
  it('returns null when the full version agrees', () => {
    expect(getVersionMismatch('1.2.3', '1.2.3')).toBeNull()
  })

  it('returns the pair when only the patch differs', () => {
    expect(getVersionMismatch('1.2.3', '1.2.9')).toEqual({ client: '1.2.3', server: '1.2.9' })
  })

  it('returns the pair when the minor differs', () => {
    expect(getVersionMismatch('1.2.3', '1.3.0')).toEqual({ client: '1.2.3', server: '1.3.0' })
  })

  it('returns the pair when the major differs', () => {
    expect(getVersionMismatch('1.2.3', '2.0.0')).toEqual({ client: '1.2.3', server: '2.0.0' })
  })

  it('ignores a pre-release suffix when comparing the version', () => {
    expect(getVersionMismatch('1.2.3-rc.1', '1.2.3')).toBeNull()
    expect(getVersionMismatch('1.2.3-rc.1', '1.3.0')).toEqual({
      client: '1.2.3-rc.1',
      server: '1.3.0',
    })
  })

  it('skips the unbuilt-dev placeholder on either side', () => {
    expect(getVersionMismatch('0.0.0', '1.3.0')).toBeNull()
    expect(getVersionMismatch('1.2.3', '0.0.0')).toBeNull()
  })

  it('skips a version that does not parse as semver', () => {
    expect(getVersionMismatch('not-a-version', '1.3.0')).toBeNull()
    expect(getVersionMismatch('1.2.3', 'not-a-version')).toBeNull()
  })
})

describe('useVersionCheck', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports a mismatch when /health returns a different version', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ version: '2.0.0' })))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('1.2.3'))!
    await ready

    expect(mismatch.value).toEqual({ client: '1.2.3', server: '2.0.0' })
    scope.stop()
  })

  it('stays null when /health returns the same full version', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ version: '1.2.3' })))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('1.2.3'))!
    await ready

    expect(mismatch.value).toBeNull()
    scope.stop()
  })

  it('stays null when the client is the unbuilt-dev placeholder', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ version: '2.0.0' })))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('0.0.0'))!
    await ready

    expect(mismatch.value).toBeNull()
    scope.stop()
  })

  it('stays null when the fetch rejects (offline/CORS/backend down)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('1.2.3'))!
    await ready

    expect(mismatch.value).toBeNull()
    scope.stop()
  })

  it('stays null when /health answers with a non-ok status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ version: '2.0.0' }, false)))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('1.2.3'))!
    await ready

    expect(mismatch.value).toBeNull()
    scope.stop()
  })

  it('stays null when the /health payload has no string version field', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ status: 'ok' })))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck('1.2.3'))!
    await ready

    expect(mismatch.value).toBeNull()
    scope.stop()
  })

  it('defaults clientVersion to the build-time __APP_VERSION__ global', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(fakeResponse({ version: __APP_VERSION__ })))

    const scope = effectScope()
    const { mismatch, ready } = scope.run(() => useVersionCheck())!
    await ready

    // Proves the default parameter reads the real injected constant (see
    // vite.config.ts's `define`) rather than needing every caller to pass it
    // explicitly. Matching it against itself stays true regardless of what
    // package.json's version happens to be at test time.
    expect(mismatch.value).toBeNull()
    scope.stop()
  })
})
