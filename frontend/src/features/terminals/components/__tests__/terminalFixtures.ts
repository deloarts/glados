import type {
  TerminalBroadcastResponse,
  TerminalDeviceDetails,
  TerminalResponse,
  TerminalScreenOption,
} from '../../types/terminalResponse'

/** What a Pi 4 with a Samsung monitor reports, with the identifying fields filled in. */
export function makeDevice(overrides: Partial<TerminalDeviceDetails> = {}): TerminalDeviceDetails {
  return {
    cec_available: true,
    computer_model: 'Raspberry Pi 4 Model B Rev 1.5',
    computer_serial: '10000000abcdef01',
    cpu_temperature_c: 50.1,
    display_connected: true,
    display_connector: 'HDMI-A-1',
    display_height_mm: 340,
    display_height_px: 1080,
    display_make: 'Samsung',
    display_model: 'S27D390',
    display_power_state: 'on',
    display_serial: 'H4ZK123456',
    display_width_mm: 600,
    display_width_px: 1920,
    hostname: 'IND-SBC-0001',
    kernel: '6.18.50+rpt-rpi-v8',
    os_name: 'Debian GNU/Linux 13 (trixie)',
    ram_mb: 3796,
    reported_at: '2026-11-03T08:00:00Z',
    throttled: false,
    under_voltage: false,
    uptime_seconds: 93_784,
    ...overrides,
  }
}

/** An approved terminal seen just now; tests override what they depend on. */
export function makeTerminal(overrides: Partial<TerminalResponse> = {}): TerminalResponse {
  return {
    id: 1,
    name: 'Hall 1',
    status: 'approved',
    mode: 'infoscreen',
    pairing_code: null,
    pairing_expires_at: null,
    infoscreen_id: 3,
    infoscreen_name: 'Hall board',
    api_key_id: 9,
    api_key_name: 'Hall displays',
    public_key_fingerprint: '0123456789abcdef',
    first_seen_at: '2026-10-29T08:00:00Z',
    last_seen_at: new Date().toISOString(),
    last_ip: '192.168.10.21',
    user_agent: 'Mozilla/5.0 (X11; Linux aarch64) Chromium/130',
    screen_width: 1920,
    screen_height: 1080,
    frontend_version: '1.4.0',
    bridge_version: '0.2.0',
    approved_at: '2026-10-29T08:05:00Z',
    approved_by: null,
    revoked_at: null,
    reload_requested_at: null,
    identify_requested_at: null,
    duplicate_detected_at: null,
    public_id: '7f1c2a9e-0000-4000-8000-000000000001',
    location: null,
    last_session_ip: '192.168.10.21',
    identifying_details_visible: true,
    device: null,
    display_power: 'on',
    display_power_changes_at: null,
    display_override: null,
    display_override_until: null,
    ...overrides,
  } as TerminalResponse
}

export function makePendingTerminal(overrides: Partial<TerminalResponse> = {}): TerminalResponse {
  return makeTerminal({
    id: 2,
    name: null,
    status: 'pending',
    pairing_code: 'K7M2QX',
    pairing_expires_at: '2026-10-30T11:00:00Z',
    infoscreen_id: null,
    infoscreen_name: null,
    last_seen_at: '2026-10-30T10:00:00Z',
    approved_at: null,
    frontend_version: null,
    bridge_version: null,
    ...overrides,
  })
}

export function makeScreen(overrides: Partial<TerminalScreenOption> = {}): TerminalScreenOption {
  return {
    id: 3,
    name: 'Hall board',
    description: null,
    color_mode: 'dark',
    theme_preset: null,
    primary_color: null,
    rotation_seconds: 30,
    show_banner: true,
    pages: [],
    shown_on: [],
    archived: false,
    ...overrides,
  } as TerminalScreenOption
}

export function makeBroadcast(
  overrides: Partial<TerminalBroadcastResponse> = {},
): TerminalBroadcastResponse {
  return {
    id: 11,
    public_id: '7f1c2a9e-0000-4000-8000-000000000011',
    text: 'Fire drill at **10:00**',
    severity: 'warning',
    style: 'banner',
    show_until: new Date(Date.now() + 60 * 60_000).toISOString(),
    all_terminals: true,
    terminal_ids: [],
    infoscreen_ids: [],
    reach_count: 3,
    created: '2026-11-03T08:00:00Z',
    created_by: null,
    ended_at: null,
    ...overrides,
  }
}
