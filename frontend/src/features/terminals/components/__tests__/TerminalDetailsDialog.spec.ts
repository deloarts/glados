import { describe, it, expect, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeDevice, makeTerminal } from './terminalFixtures'
import TerminalDetailsDialog from '../TerminalDetailsDialog.vue'

import type { TerminalResponse } from '../../types/terminalResponse'

const NOW = Date.parse('2026-11-03T10:00:00Z')

let wrapper: VueWrapper | null = null

async function openDetails(terminal: TerminalResponse) {
  wrapper = mountWithApp(TerminalDetailsDialog, {
    attachTo: document.body,
    props: { visible: false, terminal, now: NOW },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function detail(key: string): string {
  return document.body.querySelector(`[data-testid="terminal-detail-${key}"]`)?.textContent?.trim() ?? ''
}

describe('TerminalDetailsDialog', () => {
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('shows every reported detail to someone who may manage terminals', async () => {
    await openDetails(makeTerminal({ device: makeDevice(), location: 'North wall' }))

    expect(document.body.querySelector('[data-testid="terminal-details-hidden-note"]')).toBeNull()
    expect(detail('location')).toBe('North wall')
    expect(detail('fingerprint')).toBe('0123456789abcdef')
    expect(detail('lastIp')).toBe('192.168.10.21')
    expect(detail('model')).toBe('Raspberry Pi 4 Model B Rev 1.5')
    expect(detail('serial')).toBe('10000000abcdef01')
    expect(detail('ram')).toBe('4 GB')
    expect(detail('hostname')).toBe('IND-SBC-0001')
    expect(detail('os')).toBe('Debian GNU/Linux 13 (trixie)')
    expect(detail('monitor')).toBe('Samsung S27D390')
    expect(detail('monitorSerial')).toBe('H4ZK123456')
    expect(detail('resolution')).toBe('1920 × 1080')
    expect(detail('size')).toContain('27″')
    expect(detail('uptime')).toBe('1 d 2 h')
    expect(detail('cec')).toBe(i18n.global.t('common.yes'))
  })

  it('marks the identifying details as hidden for a reader without the permission', async () => {
    await openDetails(
      makeTerminal({
        identifying_details_visible: false,
        public_key_fingerprint: null,
        last_ip: null,
        last_session_ip: null,
        device: makeDevice({ computer_serial: null, display_serial: null, hostname: null }),
      }),
    )

    expect(
      document.body.querySelector('[data-testid="terminal-details-hidden-note"]')!.textContent,
    ).toContain(i18n.global.t('settings.users.permissions.manageTerminals'))
    for (const key of ['fingerprint', 'lastIp', 'sessionIp', 'serial', 'hostname', 'monitorSerial']) {
      expect(detail(key)).toBe(i18n.global.t('terminals.details.hidden'))
    }
    expect(detail('model')).toBe('Raspberry Pi 4 Model B Rev 1.5')
  })

  it('says when the display has not reported its devices yet', async () => {
    await openDetails(makeTerminal({ device: null }))

    expect(document.body.textContent).toContain(i18n.global.t('terminals.details.notReported'))
    expect(detail('fingerprint')).toBe('0123456789abcdef')
  })
})
