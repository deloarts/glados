import type { TerminalResponse } from '../types/terminalResponse'

/** An approved terminal that has not been heard from for this long counts as offline. */
export const OFFLINE_AFTER_MS = 5 * 60 * 1000

/** The server keeps a terminal's location to this many characters. */
export const LOCATION_MAX_LENGTH = 200

/** Pairing codes are this long, from an alphabet without 0, O, 1, I and L. */
export const PAIRING_CODE_LENGTH = 6
const PAIRING_CODE_PATTERN = /^[A-HJKMNP-Z2-9]{6}$/

export function isPending(terminal: TerminalResponse): boolean {
  return terminal.status === 'pending'
}

export function isOffline(terminal: TerminalResponse, now: number): boolean {
  if (terminal.status !== 'approved') return false
  if (!terminal.last_seen_at) return true
  return now - Date.parse(terminal.last_seen_at) > OFFLINE_AFTER_MS
}

/**
 * The code as the person typed it, in the form the server compares: upper
 * case, without the spaces or dashes someone may type to group it.
 */
export function normalisePairingCode(input: string): string {
  return input.toUpperCase().replace(/[\s-]/g, '')
}

/**
 * Whether a normalised code can be a pairing code at all. Only the format is
 * checked here; whether it matches the code on the TV is the server's call.
 */
export function isPairingCodeFormat(code: string): boolean {
  return PAIRING_CODE_PATTERN.test(code)
}

export function screenSize(terminal: TerminalResponse): string | null {
  if (terminal.screen_width == null || terminal.screen_height == null) return null
  return `${terminal.screen_width} × ${terminal.screen_height}`
}

/**
 * The manual display override that still holds at `now`. The server clears
 * it once it has ended, but a list loaded earlier can outlive that moment.
 */
export function activeOverride(
  terminal: TerminalResponse,
  now: number,
): { power: TerminalResponse['display_power']; until: string } | null {
  const power = terminal.display_override
  const until = terminal.display_override_until
  if (!power || !until || Date.parse(until) <= now) return null
  return { power, until }
}

/** What the table shows of a terminal's display power, or null when it does not apply. */
export function displayPowerState(
  terminal: TerminalResponse,
  now: number,
): { power: TerminalResponse['display_power']; until: string | null; manual: boolean } | null {
  if (terminal.status !== 'approved') return null
  const override = activeOverride(terminal, now)
  if (override) return { power: override.power, until: override.until, manual: true }
  const changesAt = terminal.display_power_changes_at
  const until = changesAt && Date.parse(changesAt) > now ? changesAt : null
  return { power: terminal.display_power, until, manual: false }
}

/** Whether a row matches the search box: name, location, screen and the reported devices. */
export function matchesTerminalSearch(terminal: TerminalResponse, needle: string): boolean {
  const query = needle.trim().toLowerCase()
  if (!query) return true
  const device = terminal.device
  return [
    terminal.name,
    terminal.location,
    terminal.infoscreen_name,
    terminal.pairing_code,
    device?.computer_model,
    device?.display_make,
    device?.display_model,
    device?.os_name,
    device?.hostname,
  ].some((value) => value?.toLowerCase().includes(query))
}
