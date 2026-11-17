import type { TerminalDeviceDetails } from '../types/terminalResponse'

const MB_PER_GB = 1024
const MM_PER_INCH = 25.4

/**
 * A computer model as short as a table column needs it. The Raspberry Pi
 * firmware reports names such as "Raspberry Pi 4 Model B Rev 1.5", which
 * becomes "Pi 4 B"; any other name is kept apart from its revision suffix.
 */
export function shortComputerModel(model: string): string {
  return model
    .replace(/\s+Rev\s+[\w.]+$/i, '')
    .replace(/^Raspberry Pi\b/i, 'Pi')
    .replace(/\s+Model\s+/i, ' ')
    .trim()
}

/**
 * Memory in whole gigabytes, the size it was sold as: the kernel reports a
 * little less than the module holds, so 3796 MB reads as 4 GB. Less than a
 * gigabyte stays in megabytes.
 */
export function formatRam(ramMb: number): string {
  if (ramMb < MB_PER_GB) return `${Math.round(ramMb)} MB`
  return `${Math.round(ramMb / MB_PER_GB)} GB`
}

/**
 * An operating system name without the words a column does not need:
 * "Debian GNU/Linux 13 (trixie)" becomes "Debian 13".
 */
export function shortOsName(name: string): string {
  return name
    .replace(/\s*\([^)]*\)\s*$/, '')
    .replace(/\bGNU\/Linux\s+/i, '')
    .trim()
}

/** "Pi 4 B · 4 GB", or null when the display reported neither part. */
export function hardwareSummary(device: TerminalDeviceDetails | null): string | null {
  if (!device) return null
  const parts = [
    device.computer_model ? shortComputerModel(device.computer_model) : null,
    device.ram_mb != null ? formatRam(device.ram_mb) : null,
  ].filter((part): part is string => !!part)
  return parts.length > 0 ? parts.join(' · ') : null
}

/** The native resolution of the monitor, such as "1920 × 1080". */
export function displayResolution(device: TerminalDeviceDetails): string | null {
  if (device.display_width_px == null || device.display_height_px == null) return null
  return `${device.display_width_px} × ${device.display_height_px}`
}

/** The monitor's make and model, "Samsung S27D390". */
export function displayName(device: TerminalDeviceDetails): string | null {
  const name = [device.display_make, device.display_model].filter(Boolean).join(' ').trim()
  return name || null
}

/** "Samsung S27D390 · 1920 × 1080", or null when the display reported neither part. */
export function displaySummary(device: TerminalDeviceDetails | null): string | null {
  if (!device) return null
  const parts = [displayName(device), displayResolution(device)].filter(
    (part): part is string => !!part,
  )
  return parts.length > 0 ? parts.join(' · ') : null
}

/** "Debian 13", or null when the display did not report its system. */
export function osSummary(device: TerminalDeviceDetails | null): string | null {
  if (!device?.os_name) return null
  return shortOsName(device.os_name) || null
}

/**
 * The visible size of the monitor as its diagonal in inches, the way
 * monitors are sold, with the width and height in centimetres.
 */
export function displaySize(device: TerminalDeviceDetails): {
  inches: number
  widthCm: number
  heightCm: number
} | null {
  const width = device.display_width_mm
  const height = device.display_height_mm
  if (width == null || height == null) return null
  return {
    inches: Math.round(Math.hypot(width, height) / MM_PER_INCH),
    widthCm: Math.round(width / 10),
    heightCm: Math.round(height / 10),
  }
}

/** An uptime in its largest units: days and hours, or hours and minutes. */
export function uptimeParts(seconds: number): { days: number; hours: number; minutes: number } {
  const total = Math.max(0, Math.floor(seconds))
  return {
    days: Math.floor(total / 86_400),
    hours: Math.floor((total % 86_400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
  }
}
