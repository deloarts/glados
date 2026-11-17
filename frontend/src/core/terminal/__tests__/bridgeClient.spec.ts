import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import {
  BRIDGE_TIMEOUT_MS,
  BRIDGE_URL,
  BridgeError,
  deviceDetailsFromBridge,
  getBridgeDeviceDetails,
  getBridgeDisplay,
  getBridgeHealth,
  getBridgeIdentity,
  setBridgeDisplayPower,
  signWithBridge,
} from '../bridgeClient'

// The bridge's `GET /display` answer, as its API document shows it.
function displayPayload(overrides: Record<string, unknown> = {}) {
  return {
    power: 'on',
    requested_power: 'off',
    changed_at: '2026-11-03T22:00:00.123456Z',
    sway_reachable: true,
    cec_available: true,
    cec_responding: true,
    last_error: null,
    ...overrides,
  }
}

// The bridge's `GET /device` answer, as its API document shows it.
function devicePayload() {
  return {
    computer: {
      model: 'Raspberry Pi 4 Model B Rev 1.5',
      serial: '100000009f349633',
      memory_total_bytes: 3927805952,
      memory_installed_bytes: 4294967296,
      kernel: '6.18.50+rpt-rpi-v8',
      architecture: 'aarch64',
      cpu_temperature_celsius: 49.2,
      under_voltage: false,
      uptime_seconds: 20392,
    },
    host: {
      hostname: 'IND-SBC-0001',
      os_name: 'Debian GNU/Linux 13 (trixie)',
      os_id: 'debian',
      os_version_id: '13',
    },
    connectors: [
      { connector: 'HDMI-A-2', connected: false, enabled: false, dpms: null, edid: null },
      {
        connector: 'HDMI-A-1',
        connected: true,
        enabled: true,
        dpms: 'on',
        edid: {
          manufacturer_id: 'SAM',
          make: 'Samsung',
          model: 'S27D390',
          product_code: 2919,
          serial: '808662579',
          manufacture_year: 2015,
          native_width: 1920,
          native_height: 1080,
          native_refresh_hz: 60.0,
          width_mm: 598,
          height_mm: 336,
        },
      },
    ],
    display: displayPayload({ requested_power: null, changed_at: null, cec_responding: null }),
  }
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

async function bridgeErrorOf(promise: Promise<unknown>): Promise<string | null> {
  try {
    await promise
    return null
  } catch (error) {
    return error instanceof BridgeError ? error.kind : 'other'
  }
}

describe('bridgeClient', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('reads the identity from the bridge without credentials', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { public_key: 'pk', api_key: 'key' }))

    await expect(getBridgeIdentity()).resolves.toEqual({ publicKey: 'pk', apiKey: 'key' })

    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe(`${BRIDGE_URL}/identity`)
    expect(init?.credentials).toBe('omit')
  })

  it('reads a missing terminal key as null', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { public_key: 'pk', api_key: null }))

    await expect(getBridgeIdentity()).resolves.toEqual({ publicKey: 'pk', apiKey: null })
  })

  it('reports a bridge that does not answer as bridge_missing', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    expect(await bridgeErrorOf(getBridgeIdentity())).toBe('bridge_missing')
  })

  it('gives up after the timeout and reports bridge_missing', async () => {
    vi.useFakeTimers()
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted')))
        }),
    )

    const result = bridgeErrorOf(getBridgeIdentity())
    await vi.advanceTimersByTimeAsync(BRIDGE_TIMEOUT_MS)

    expect(await result).toBe('bridge_missing')
  })

  it('maps a 503 to identity_unavailable and a 403 to origin_refused', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(503, {}))
    expect(await bridgeErrorOf(getBridgeIdentity())).toBe('identity_unavailable')

    fetchMock.mockResolvedValueOnce(jsonResponse(403, {}))
    expect(await bridgeErrorOf(getBridgeIdentity())).toBe('origin_refused')
  })

  it('has the bridge sign the nonce', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { signature: 'sig' }))

    await expect(signWithBridge('n-1')).resolves.toBe('sig')

    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe(`${BRIDGE_URL}/identity/sign`)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ nonce: 'n-1' })
  })

  it('returns the bridge version, or null when the bridge is missing', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: 'ok', version: '0.2.0', devices: [] }))
    await expect(getBridgeHealth()).resolves.toEqual({ status: 'ok', version: '0.2.0' })

    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(getBridgeHealth()).resolves.toBeNull()
  })

  describe('display power', () => {
    it('reads the display state', async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, displayPayload({ last_error: 'CEC timeout' })))

      await expect(getBridgeDisplay()).resolves.toEqual({
        power: 'on',
        requestedPower: 'off',
        swayReachable: true,
        lastError: 'CEC timeout',
      })
      expect(fetchMock.mock.calls[0]![0]).toBe(`${BRIDGE_URL}/display`)
    })

    it('reads a power the bridge does not know as null', async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, displayPayload({ power: null, requested_power: null })))

      await expect(getBridgeDisplay()).resolves.toMatchObject({ power: null, requestedPower: null })
    })

    it('switches the display through a POST and answers the state after it', async () => {
      fetchMock.mockResolvedValue(jsonResponse(200, displayPayload({ power: 'off' })))

      await expect(setBridgeDisplayPower('off')).resolves.toMatchObject({
        power: 'off',
        requestedPower: 'off',
      })

      const [url, init] = fetchMock.mock.calls[0]!
      expect(url).toBe(`${BRIDGE_URL}/display`)
      expect(init?.method).toBe('POST')
      expect(init?.credentials).toBe('omit')
      expect(JSON.parse(String(init?.body))).toEqual({ power: 'off' })
    })

    it('answers null when the bridge is missing or cannot switch, instead of failing', async () => {
      fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
      await expect(getBridgeDisplay()).resolves.toBeNull()

      fetchMock.mockResolvedValueOnce(
        jsonResponse(503, { detail: 'Could not switch the display off: sway not running' }),
      )
      await expect(setBridgeDisplayPower('off')).resolves.toBeNull()

      fetchMock.mockResolvedValueOnce(jsonResponse(403, {}))
      await expect(setBridgeDisplayPower('on')).resolves.toBeNull()
    })
  })

  describe('device details', () => {
    it('maps the bridge report onto the details Glados keeps', () => {
      expect(deviceDetailsFromBridge(devicePayload())).toEqual({
        computer_model: 'Raspberry Pi 4 Model B Rev 1.5',
        computer_serial: '100000009f349633',
        ram_mb: 4096,
        kernel: '6.18.50+rpt-rpi-v8',
        cpu_temperature_c: 49.2,
        under_voltage: false,
        throttled: null,
        uptime_seconds: 20392,
        hostname: 'IND-SBC-0001',
        os_name: 'Debian GNU/Linux 13 (trixie)',
        display_connected: true,
        display_connector: 'HDMI-A-1',
        display_make: 'Samsung',
        display_model: 'S27D390',
        display_serial: '808662579',
        display_width_px: 1920,
        display_height_px: 1080,
        display_width_mm: 598,
        display_height_mm: 336,
        display_power_state: 'on',
        cec_available: true,
      })
    })

    it('falls back to the usable memory and reports a device without a display', () => {
      const payload = devicePayload()
      payload.computer.memory_installed_bytes = null as unknown as number
      payload.connectors = [payload.connectors[0]!]

      const details = deviceDetailsFromBridge(payload)!

      expect(details.ram_mb).toBe(3746)
      expect(details.display_connected).toBe(false)
      expect(details.display_connector).toBeNull()
      expect(details.display_model).toBeNull()
      // Without a connected display, the power the bridge reports stands in.
      expect(details.display_power_state).toBe('on')
    })

    it('leaves out what the bridge cannot tell', () => {
      const details = deviceDetailsFromBridge({ computer: null, host: null, connectors: [], display: null })!

      expect(Object.values(details).every((value) => value === null || value === false)).toBe(true)
      expect(deviceDetailsFromBridge('nonsense')).toBeNull()
    })

    it('reads the details from the bridge, or null when it does not answer', async () => {
      fetchMock.mockResolvedValueOnce(jsonResponse(200, devicePayload()))
      await expect(getBridgeDeviceDetails()).resolves.toMatchObject({ hostname: 'IND-SBC-0001' })
      expect(fetchMock.mock.calls[0]![0]).toBe(`${BRIDGE_URL}/device`)

      fetchMock.mockResolvedValueOnce(jsonResponse(503, { detail: 'no device details' }))
      await expect(getBridgeDeviceDetails()).resolves.toBeNull()

      fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
      await expect(getBridgeDeviceDetails()).resolves.toBeNull()
    })
  })
})
