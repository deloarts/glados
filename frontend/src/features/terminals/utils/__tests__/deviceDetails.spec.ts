import { describe, it, expect } from 'vitest'

import { makeDevice } from '../../components/__tests__/terminalFixtures'
import {
  displaySize,
  displaySummary,
  formatRam,
  hardwareSummary,
  osSummary,
  shortComputerModel,
  shortOsName,
  uptimeParts,
} from '../deviceDetails'

describe('deviceDetails', () => {
  it('shortens Raspberry Pi model names and keeps others apart from their revision', () => {
    expect(shortComputerModel('Raspberry Pi 4 Model B Rev 1.5')).toBe('Pi 4 B')
    expect(shortComputerModel('Raspberry Pi 5 Model B Rev 1.0')).toBe('Pi 5 B')
    expect(shortComputerModel('Raspberry Pi Compute Module 4 Rev 1.1')).toBe('Pi Compute Module 4')
    expect(shortComputerModel('Intel NUC')).toBe('Intel NUC')
  })

  it('reads memory as the size it was sold as', () => {
    expect(formatRam(3796)).toBe('4 GB')
    expect(formatRam(7820)).toBe('8 GB')
    expect(formatRam(512)).toBe('512 MB')
  })

  it('shortens the operating system name', () => {
    expect(shortOsName('Debian GNU/Linux 13 (trixie)')).toBe('Debian 13')
    expect(shortOsName('Ubuntu 24.04 LTS')).toBe('Ubuntu 24.04 LTS')
  })

  it('builds the short table columns and leaves out what was not reported', () => {
    expect(hardwareSummary(makeDevice())).toBe('Pi 4 B · 4 GB')
    expect(hardwareSummary(makeDevice({ ram_mb: null }))).toBe('Pi 4 B')
    expect(displaySummary(makeDevice())).toBe('Samsung S27D390 · 1920 × 1080')
    expect(displaySummary(makeDevice({ display_make: null, display_model: null }))).toBe('1920 × 1080')
    expect(osSummary(makeDevice())).toBe('Debian 13')
    expect(hardwareSummary(null)).toBeNull()
    expect(displaySummary(makeDevice({ display_make: null, display_model: null, display_width_px: null }))).toBeNull()
    expect(osSummary(makeDevice({ os_name: null }))).toBeNull()
  })

  it('gives the monitor size as its diagonal in inches', () => {
    expect(displaySize(makeDevice())).toEqual({ inches: 27, widthCm: 60, heightCm: 34 })
    expect(displaySize(makeDevice({ display_width_mm: null }))).toBeNull()
  })

  it('splits an uptime into days, hours and minutes', () => {
    expect(uptimeParts(93_784)).toEqual({ days: 1, hours: 2, minutes: 3 })
    expect(uptimeParts(-5)).toEqual({ days: 0, hours: 0, minutes: 0 })
  })
})
