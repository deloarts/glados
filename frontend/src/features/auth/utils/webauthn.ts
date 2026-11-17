/**
 * Browser side of the passkey ceremonies. The backend sends WebAuthn
 * options as JSON with base64url strings where the browser API wants
 * binary, and expects the created or signed credential back in the same
 * JSON form. The conversions are written out here instead of relying on
 * PublicKeyCredential.parseCreationOptionsFromJSON and toJSON(), which
 * not every supported browser ships yet.
 */

type Json = Record<string, unknown>

export function base64urlToBuffer(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

export function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Whether this page may use WebAuthn at all: https or localhost, and a browser that has it. */
export function passkeysSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    typeof window.PublicKeyCredential !== 'undefined' &&
    typeof navigator.credentials !== 'undefined'
  )
}

/** Whether the device has a built-in authenticator (Windows Hello, Touch ID, a phone's screen lock). */
export async function platformAuthenticatorAvailable(): Promise<boolean> {
  if (!passkeysSupported()) return false
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
  } catch {
    return false
  }
}

export type PlatformAuthenticator = 'windowsHello' | 'touchId' | 'generic'

/** Which name the device's built-in authenticator goes by, for the labels. */
export function platformAuthenticatorKind(): PlatformAuthenticator {
  const agent = navigator.userAgent
  if (/Windows/i.test(agent)) return 'windowsHello'
  if (/Macintosh|Mac OS X/i.test(agent)) return 'touchId'
  return 'generic'
}

/** The user dismissed the prompt, it timed out, or no matching passkey exists on this device. */
export function passkeyPromptDismissed(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === 'NotAllowedError' || error.name === 'AbortError')
  )
}

function descriptors(list: unknown): PublicKeyCredentialDescriptor[] {
  if (!Array.isArray(list)) return []
  return list.map((entry: Json) => ({
    type: 'public-key',
    id: base64urlToBuffer(entry.id as string),
    transports: entry.transports as AuthenticatorTransport[] | undefined,
  }))
}

function attachment(credential: PublicKeyCredential): string | null {
  return credential.authenticatorAttachment ?? null
}

/** Runs navigator.credentials.create() and returns the result in the backend's JSON form. */
export async function createPasskey(options: Json): Promise<Json> {
  const user = options.user as Json
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...(options as unknown as PublicKeyCredentialCreationOptions),
    challenge: base64urlToBuffer(options.challenge as string),
    user: {
      id: base64urlToBuffer(user.id as string),
      name: user.name as string,
      displayName: user.displayName as string,
    },
    excludeCredentials: descriptors(options.excludeCredentials),
  }

  const credential = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential
  const response = credential.response as AuthenticatorAttestationResponse
  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: attachment(credential),
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      attestationObject: bufferToBase64url(response.attestationObject),
      transports: response.getTransports?.() ?? [],
    },
  }
}

/**
 * Runs navigator.credentials.get() and returns the result in the backend's
 * JSON form. `credentialId` narrows the prompt to the passkey this device
 * registered for the remembered user; without it the browser offers every
 * passkey it holds for this site.
 */
export async function getPasskey(options: Json, credentialId?: string | null): Promise<Json> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    ...(options as unknown as PublicKeyCredentialRequestOptions),
    challenge: base64urlToBuffer(options.challenge as string),
    allowCredentials: credentialId
      ? [{ type: 'public-key', id: base64urlToBuffer(credentialId) }]
      : descriptors(options.allowCredentials),
  }

  const credential = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential
  const response = credential.response as AuthenticatorAssertionResponse
  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: attachment(credential),
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      authenticatorData: bufferToBase64url(response.authenticatorData),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
    },
  }
}
