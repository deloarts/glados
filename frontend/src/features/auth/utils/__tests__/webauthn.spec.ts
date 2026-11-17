import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  base64urlToBuffer,
  bufferToBase64url,
  createPasskey,
  getPasskey,
  passkeyPromptDismissed,
} from '../webauthn'

function bytes(...values: number[]): ArrayBuffer {
  return new Uint8Array(values).buffer
}

describe('webauthn conversions', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('round-trips base64url without padding', () => {
    const buffer = bytes(251, 255, 0, 1, 2)
    const encoded = bufferToBase64url(buffer)

    expect(encoded).toBe('-_8AAQI')
    expect(new Uint8Array(base64urlToBuffer(encoded))).toEqual(new Uint8Array(buffer))
  })

  it('treats a dismissed or aborted prompt as dismissed, other errors not', () => {
    expect(passkeyPromptDismissed(new DOMException('x', 'NotAllowedError'))).toBe(true)
    expect(passkeyPromptDismissed(new DOMException('x', 'AbortError'))).toBe(true)
    expect(passkeyPromptDismissed(new DOMException('x', 'SecurityError'))).toBe(false)
    expect(passkeyPromptDismissed(new Error('network'))).toBe(false)
  })

  it('decodes creation options and encodes the attestation', async () => {
    const create = vi.fn<(options: CredentialCreationOptions) => Promise<unknown>>()
    create.mockResolvedValue({
      id: 'AQI',
      rawId: bytes(1, 2),
      type: 'public-key',
      authenticatorAttachment: 'platform',
      getClientExtensionResults: () => ({}),
      response: {
        clientDataJSON: bytes(3),
        attestationObject: bytes(4),
        getTransports: () => ['internal'],
      },
    })
    vi.stubGlobal('navigator', { credentials: { create } })

    const result = await createPasskey({
      challenge: 'BQY',
      rp: { id: 'localhost', name: 'Glados' },
      user: { id: 'Bwg', name: 'alice', displayName: 'Alice' },
      excludeCredentials: [{ id: 'CQ', type: 'public-key' }],
    })

    const publicKey = create.mock.calls[0]?.[0].publicKey as PublicKeyCredentialCreationOptions
    expect(new Uint8Array(publicKey.challenge as ArrayBuffer)).toEqual(new Uint8Array([5, 6]))
    expect(new Uint8Array(publicKey.user.id as ArrayBuffer)).toEqual(new Uint8Array([7, 8]))
    expect(publicKey.excludeCredentials).toHaveLength(1)
    expect(result).toMatchObject({
      rawId: 'AQI',
      response: { clientDataJSON: 'Aw', attestationObject: 'BA', transports: ['internal'] },
    })
  })

  it('narrows the login prompt to the remembered passkey', async () => {
    const get = vi.fn<(options: CredentialRequestOptions) => Promise<unknown>>()
    get.mockResolvedValue({
      id: 'AQI',
      rawId: bytes(1, 2),
      type: 'public-key',
      authenticatorAttachment: 'platform',
      getClientExtensionResults: () => ({}),
      response: {
        clientDataJSON: bytes(3),
        authenticatorData: bytes(4),
        signature: bytes(5),
        userHandle: null,
      },
    })
    vi.stubGlobal('navigator', { credentials: { get } })

    const result = await getPasskey({ challenge: 'BQY', rpId: 'localhost' }, 'AQI')

    const publicKey = get.mock.calls[0]?.[0].publicKey as PublicKeyCredentialRequestOptions
    expect(publicKey.allowCredentials).toHaveLength(1)
    expect(new Uint8Array(publicKey.allowCredentials?.[0]?.id as ArrayBuffer)).toEqual(
      new Uint8Array([1, 2]),
    )
    expect(result).toMatchObject({
      rawId: 'AQI',
      response: { authenticatorData: 'BA', signature: 'BQ', userHandle: null },
    })
  })
})
