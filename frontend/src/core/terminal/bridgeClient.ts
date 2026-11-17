/**
 * Talks to the glados-terminal bridge, the local service on a terminal device
 * that holds the device's Ed25519 key pair. The private key never leaves the
 * bridge: the page asks it for the public key and has it sign the backend's
 * challenge nonce, and the bridge itself checks and decides nothing. The
 * bridge also switches the display on and off when the page asks, and
 * describes the device for the terminal list in Glados.
 *
 * Plain fetch without credentials, since the bridge is a different origin
 * (it allows the Glados origin through its own CORS list) and must never see
 * the Glados session cookie. Every call has a short timeout, because a
 * missing bridge should show its message quickly instead of hanging.
 */

import type { Schemas } from '@/core/api/generated'

// The page's Content Security Policy (docker/nginx.conf) allows exactly this
// origin in connect-src, so a change here needs the same change there.
export const BRIDGE_URL = 'http://localhost:8600'
export const BRIDGE_TIMEOUT_MS = 3000

/**
 * Why a bridge call failed: no bridge answered (not a terminal, or the
 * service is still starting), the bridge has no identity yet (503), or it
 * refused this page's origin (403, `BRIDGE__ALLOWED_ORIGINS`).
 */
export type BridgeErrorKind = 'bridge_missing' | 'identity_unavailable' | 'origin_refused'

export class BridgeError extends Error {
  constructor(public readonly kind: BridgeErrorKind) {
    super(`Terminal bridge call failed: ${kind}`)
    this.name = 'BridgeError'
  }
}

export interface BridgeIdentity {
  /** Raw 32-byte Ed25519 public key, base64url without padding. */
  publicKey: string
  /** The terminal key configured on the device, needed only to register an unknown device. */
  apiKey: string | null
}

export interface BridgeHealth {
  status: string
  version: string | null
}

export type BridgeDisplayPower = 'on' | 'off'

/** What the bridge reports about the display power (`GET /display`). */
export interface BridgeDisplay {
  /** The power right now, null when no display is known. */
  power: BridgeDisplayPower | null
  /** What the page asked for last since the bridge started, null before the first request. */
  requestedPower: BridgeDisplayPower | null
  /** Whether the bridge reaches sway, without which it cannot switch the display. */
  swayReachable: boolean
  /** What went wrong at the last switch, null when it fully worked. */
  lastError: string | null
}

/**
 * The device details the session sends to Glados, in the backend's shape.
 * Every field is optional, since the bridge reports null for anything it
 * cannot determine.
 */
export type BridgeDeviceDetails = Schemas['TerminalDeviceDetailsRequest']

async function bridgeFetch(path: string, init: RequestInit = {}): Promise<unknown> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), BRIDGE_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${BRIDGE_URL}${path}`, {
      ...init,
      credentials: 'omit',
      signal: controller.signal,
    })
  } catch {
    throw new BridgeError('bridge_missing')
  } finally {
    clearTimeout(timeout)
  }

  if (response.status === 403) throw new BridgeError('origin_refused')
  // Any other refusal means the bridge is there but cannot vouch for this
  // device right now, which the page treats like a missing identity.
  if (!response.ok) throw new BridgeError('identity_unavailable')

  try {
    return await response.json()
  } catch {
    throw new BridgeError('identity_unavailable')
  }
}

function stringField(payload: unknown, name: string): string | null {
  if (!payload || typeof payload !== 'object') return null
  const value = (payload as Record<string, unknown>)[name]
  return typeof value === 'string' && value !== '' ? value : null
}

/** The device's public key and, when configured, its terminal key. */
export async function getBridgeIdentity(): Promise<BridgeIdentity> {
  const payload = await bridgeFetch('/identity')
  const publicKey = stringField(payload, 'public_key')
  if (!publicKey) throw new BridgeError('identity_unavailable')
  return { publicKey, apiKey: stringField(payload, 'api_key') }
}

/** Has the bridge sign a challenge nonce and returns the signature as the bridge encodes it. */
export async function signWithBridge(nonce: string): Promise<string> {
  const payload = await bridgeFetch('/identity/sign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nonce }),
  })
  const signature = stringField(payload, 'signature')
  if (!signature) throw new BridgeError('identity_unavailable')
  return signature
}

/**
 * The bridge's status and version, for the device telemetry. Null when the
 * bridge does not answer, since the version is informational only.
 */
export async function getBridgeHealth(): Promise<BridgeHealth | null> {
  try {
    const payload = await bridgeFetch('/health')
    return {
      status: stringField(payload, 'status') ?? 'unknown',
      version: stringField(payload, 'version'),
    }
  } catch {
    return null
  }
}

function displayPowerField(payload: unknown, name: string): BridgeDisplayPower | null {
  const value = stringField(payload, name)
  return value === 'on' || value === 'off' ? value : null
}

function displayFrom(payload: unknown): BridgeDisplay | null {
  if (!payload || typeof payload !== 'object') return null
  return {
    power: displayPowerField(payload, 'power'),
    requestedPower: displayPowerField(payload, 'requested_power'),
    swayReachable: (payload as Record<string, unknown>).sway_reachable === true,
    lastError: stringField(payload, 'last_error'),
  }
}

/** The display power as the bridge sees it, or null when the bridge does not answer. */
export async function getBridgeDisplay(): Promise<BridgeDisplay | null> {
  try {
    return displayFrom(await bridgeFetch('/display'))
  } catch {
    return null
  }
}

/**
 * Asks the bridge to switch the display on or off. Answers the display state
 * after the change, or null when the bridge is missing or could not switch,
 * in which case the display stays as it is.
 */
export async function setBridgeDisplayPower(power: BridgeDisplayPower): Promise<BridgeDisplay | null> {
  try {
    const payload = await bridgeFetch('/display', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ power }),
    })
    return displayFrom(payload)
  } catch {
    return null
  }
}

function objectField(payload: unknown, name: string): Record<string, unknown> | null {
  if (!payload || typeof payload !== 'object') return null
  const value = (payload as Record<string, unknown>)[name]
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function numberField(payload: unknown, name: string): number | null {
  if (!payload || typeof payload !== 'object') return null
  const value = (payload as Record<string, unknown>)[name]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function booleanField(payload: unknown, name: string): boolean | null {
  if (!payload || typeof payload !== 'object') return null
  const value = (payload as Record<string, unknown>)[name]
  return typeof value === 'boolean' ? value : null
}

const BYTES_PER_MB = 1024 * 1024

/**
 * The connector that drives the display: the first one with a display
 * connected that is enabled, else the first one with a display connected.
 */
function displayConnector(payload: unknown): Record<string, unknown> | null {
  const connectors = (payload as Record<string, unknown>).connectors
  if (!Array.isArray(connectors)) return null
  const connected = connectors.filter(
    (item): item is Record<string, unknown> =>
      !!item && typeof item === 'object' && (item as Record<string, unknown>).connected === true,
  )
  return connected.find((item) => item.enabled === true) ?? connected[0] ?? null
}

/**
 * Maps the bridge's `GET /device` answer onto the details Glados keeps:
 * the computer, the host and the display on the connector in use. The
 * installed memory is preferred over what the kernel can use, since that is
 * what the device is sold with.
 */
export function deviceDetailsFromBridge(payload: unknown): BridgeDeviceDetails | null {
  if (!payload || typeof payload !== 'object') return null
  const computer = objectField(payload, 'computer')
  const host = objectField(payload, 'host')
  const display = objectField(payload, 'display')
  const connector = displayConnector(payload)
  const edid = objectField(connector, 'edid')
  const memoryBytes =
    numberField(computer, 'memory_installed_bytes') ?? numberField(computer, 'memory_total_bytes')
  const connectors = (payload as Record<string, unknown>).connectors
  return {
    computer_model: stringField(computer, 'model'),
    computer_serial: stringField(computer, 'serial'),
    ram_mb: memoryBytes === null ? null : Math.round(memoryBytes / BYTES_PER_MB),
    kernel: stringField(computer, 'kernel'),
    cpu_temperature_c: numberField(computer, 'cpu_temperature_celsius'),
    under_voltage: booleanField(computer, 'under_voltage'),
    // The bridge cannot read the firmware's throttling flags on these boards.
    throttled: null,
    uptime_seconds: numberField(computer, 'uptime_seconds'),
    hostname: stringField(host, 'hostname'),
    os_name: stringField(host, 'os_name'),
    display_connected: connector !== null ? true : Array.isArray(connectors) ? false : null,
    display_connector: stringField(connector, 'connector'),
    display_make: stringField(edid, 'make'),
    display_model: stringField(edid, 'model'),
    display_serial: stringField(edid, 'serial'),
    display_width_px: numberField(edid, 'native_width'),
    display_height_px: numberField(edid, 'native_height'),
    display_width_mm: numberField(edid, 'width_mm'),
    display_height_mm: numberField(edid, 'height_mm'),
    display_power_state: stringField(connector, 'dpms') ?? stringField(display, 'power'),
    cec_available: booleanField(display, 'cec_available'),
  }
}

/**
 * The device details for the session, or null when the bridge does not
 * answer or has no details to give. Never throws, so a missing report never
 * holds up signing in.
 */
export async function getBridgeDeviceDetails(): Promise<BridgeDeviceDetails | null> {
  try {
    return deviceDetailsFromBridge(await bridgeFetch('/device'))
  } catch {
    return null
  }
}
