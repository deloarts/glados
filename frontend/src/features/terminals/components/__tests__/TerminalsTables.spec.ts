import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { OFFLINE_AFTER_MS } from '../../utils/terminalStatus'
import { makeDevice, makePendingTerminal, makeTerminal } from './terminalFixtures'
import PendingTerminalsTable from '../PendingTerminalsTable.vue'
import TerminalsTable from '../TerminalsTable.vue'

const NOW = Date.parse('2026-10-30T10:00:00Z')
const MISSING = 'This needs the permission Manage Terminals.'

function mountEnrolled(terminals = [makeTerminal()], canManage = true, showActions = true) {
  return mountWithApp(TerminalsTable, {
    props: { terminals, now: NOW, showActions, canManage, missingHint: canManage ? '' : MISSING },
  })
}

type MenuEntry = { label?: string; separator?: boolean; disabled?: boolean; title?: string; command?: () => void }

async function contextMenu(wrapper: ReturnType<typeof mountWithApp>): Promise<MenuEntry[]> {
  await wrapper.get('tbody tr').trigger('contextmenu')
  await flushPromises()
  return wrapper.findComponent({ name: 'ContextMenu' }).props('model') as MenuEntry[]
}

function shape(items: MenuEntry[]): (string | undefined)[] {
  return items.map((item) => (item.separator ? '---' : item.label))
}

describe('TerminalsTable', () => {
  it('shows an approved terminal seen just now without badges', async () => {
    const wrapper = mountEnrolled([makeTerminal({ last_seen_at: new Date(NOW - 1000).toISOString() })])
    await flushPromises()

    expect(wrapper.text()).toContain('Hall 1')
    expect(wrapper.text()).toContain(i18n.global.t('terminals.status.approved'))
    expect(wrapper.text()).toContain('Hall board')
    expect(wrapper.text()).toContain('Web 1.4.0')
    expect(wrapper.text()).toContain('Bridge 0.2.0')
    expect(wrapper.find('[data-testid="terminal-offline"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="terminal-duplicate"]').exists()).toBe(false)
  })

  it('marks a terminal offline after five minutes of silence', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({ last_seen_at: new Date(NOW - OFFLINE_AFTER_MS - 1000).toISOString() }),
    ])
    await flushPromises()

    expect(wrapper.find('[data-testid="terminal-offline"]').exists()).toBe(true)
  })

  it('flags duplicate use', async () => {
    const wrapper = mountEnrolled([makeTerminal({ duplicate_detected_at: '2026-10-30T09:30:00Z' })])
    await flushPromises()

    expect(wrapper.get('[data-testid="terminal-duplicate"]').text()).toContain(
      i18n.global.t('terminals.badges.duplicate'),
    )
  })

  it('leaves only Delete on a revoked terminal', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({ status: 'revoked', revoked_at: '2026-10-30T09:00:00Z', infoscreen_name: null }),
    ])
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('terminals.status.revoked'))
    expect(wrapper.find('[data-testid="terminal-delete"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="terminal-reload"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="terminal-revoke"]').exists()).toBe(false)
    // A revoked terminal is not offline, it is gone.
    expect(wrapper.find('[data-testid="terminal-offline"]').exists()).toBe(false)
  })

  it('emits each row action', async () => {
    const terminal = makeTerminal()
    const wrapper = mountEnrolled([terminal])
    await flushPromises()

    for (const action of ['rename', 'change-screen', 'reload', 'identify', 'revoke', 'delete']) {
      await wrapper.get(`[data-testid="terminal-${action}"]`).trigger('click')
      expect(wrapper.emitted(action)).toEqual([[terminal]])
    }
  })

  it('keeps every action visible but disabled without manage:terminals', async () => {
    const wrapper = mountEnrolled([makeTerminal()], false)
    await flushPromises()

    for (const action of ['rename', 'change-screen', 'reload', 'identify', 'revoke', 'delete']) {
      const button = wrapper.get(`[data-testid="terminal-${action}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      await button.trigger('click')
      expect(wrapper.emitted(action)).toBeUndefined()
    }
  })

  it('shows the empty state without terminals', async () => {
    const wrapper = mountEnrolled([])
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('terminals.enrolled.empty'))
  })
})

describe('TerminalsTable device and display columns', () => {
  it('shows the location and short hardware, monitor and system columns', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({ location: 'Hall 2, north wall above gate 3', device: makeDevice() }),
    ])
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Hall 2, north wall above gate 3')
    expect(text).toContain('Pi 4 B · 4 GB')
    expect(text).toContain('Samsung S27D390 · 1920 × 1080')
    expect(text).toContain('Debian 13')
    // Identifying details live in the details dialog, not in the table.
    expect(text).not.toContain('0123456789abcdef')
    expect(text).not.toContain('IND-SBC-0001')
  })

  it('shows the display power with the time the schedule changes it next', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({ display_power: 'on', display_power_changes_at: '2026-10-30T17:00:00Z' }),
    ])
    await flushPromises()

    const cell = wrapper.get('[data-testid="terminal-power"]')
    expect(cell.text()).toContain(i18n.global.t('terminals.power.on'))
    expect(cell.find('[data-testid="terminal-power-override"]').exists()).toBe(false)
  })

  it('marks a display switched by hand with the end of the override', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({
        display_power: 'off',
        display_override: 'off',
        display_override_until: '2026-10-30T12:00:00Z',
        display_power_changes_at: '2026-10-30T12:00:00Z',
      }),
    ])
    await flushPromises()

    expect(wrapper.get('[data-testid="terminal-power"]').text()).toContain(
      i18n.global.t('terminals.power.off'),
    )
    expect(wrapper.find('[data-testid="terminal-power-override"]').exists()).toBe(true)
  })

  it('ignores an override that ended before the list was refreshed', async () => {
    const wrapper = mountEnrolled([
      makeTerminal({ display_override: 'off', display_override_until: '2026-10-30T09:00:00Z' }),
    ])
    await flushPromises()

    expect(wrapper.find('[data-testid="terminal-power-override"]').exists()).toBe(false)
  })

  it('keeps the details open to everyone and the display switch behind the permission', async () => {
    const terminal = makeTerminal()
    const wrapper = mountEnrolled([terminal], false)
    await flushPromises()

    const details = wrapper.get('[data-testid="terminal-details"]')
    expect(details.attributes('disabled')).toBeUndefined()
    await details.trigger('click')
    expect(wrapper.emitted('details')).toEqual([[terminal]])

    const display = wrapper.get('[data-testid="terminal-display"]')
    expect(display.attributes('disabled')).toBeDefined()
    await display.trigger('click')
    expect(wrapper.emitted('display')).toBeUndefined()
  })

  it('opens the details when a row is clicked', async () => {
    const terminal = makeTerminal()
    const wrapper = mountEnrolled([terminal])
    await flushPromises()

    await wrapper.get('[data-testid="enrolled-terminals"] tbody tr td:nth-child(3)').trigger('click')

    expect(wrapper.emitted('details')).toEqual([[terminal]])
  })
})

describe('TerminalsTable actions', () => {
  it('leaves the actions column out while Show Actions is off', async () => {
    const wrapper = mountEnrolled([makeTerminal()], true, false)
    await flushPromises()

    expect(wrapper.text()).not.toContain(i18n.global.t('terminals.columns.actions'))
    expect(wrapper.find('[data-testid="terminal-details"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="terminal-reload"]').exists()).toBe(false)
  })

  it('offers every action from the context menu in the fixed shape', async () => {
    const terminal = makeTerminal()
    const wrapper = mountEnrolled([terminal], true, false)
    await flushPromises()

    const items = await contextMenu(wrapper)

    const t = i18n.global.t
    expect(shape(items)).toEqual([
      t('terminals.actions.details'),
      '---',
      t('terminals.actions.rename'),
      t('terminals.actions.changeScreen'),
      '---',
      t('terminals.actions.display'),
      t('terminals.actions.reload'),
      t('terminals.actions.identify'),
      t('terminals.actions.revoke'),
      '---',
      t('terminals.actions.delete'),
    ])
    expect(items.some((item) => item.disabled)).toBe(false)
    items.find((item) => item.label === t('terminals.actions.reload'))!.command!()
    expect(wrapper.emitted('reload')).toEqual([[terminal]])
  })

  it('disables the managing entries without manage:terminals and names the permission', async () => {
    const wrapper = mountEnrolled([makeTerminal()], false, false)
    await flushPromises()

    const items = (await contextMenu(wrapper)).filter((item) => !item.separator)

    const [details, ...managing] = items
    expect(details!.disabled).toBe(false)
    expect(details!.title).toBeUndefined()
    for (const item of managing) {
      expect(item.disabled).toBe(true)
      expect(item.title).toBe(MISSING)
    }
  })

  it('leaves only the details and Delete enabled for a revoked terminal', async () => {
    const wrapper = mountEnrolled(
      [makeTerminal({ status: 'revoked', revoked_at: '2026-10-30T09:00:00Z' })],
      true,
      false,
    )
    await flushPromises()

    const enabled = (await contextMenu(wrapper)).filter((item) => !item.separator && !item.disabled)
    expect(enabled.map((item) => item.label)).toEqual([
      i18n.global.t('terminals.actions.details'),
      i18n.global.t('terminals.actions.delete'),
    ])
  })
})

describe('PendingTerminalsTable', () => {
  it('shows the pairing code and what the device reported', async () => {
    const wrapper = mountWithApp(PendingTerminalsTable, {
      props: { terminals: [makePendingTerminal()], canManage: true, missingHint: '' },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('K7M2QX')
    expect(wrapper.text()).toContain('192.168.10.21')
    expect(wrapper.text()).toContain('1920 × 1080')
    expect(wrapper.text()).toContain('Chromium/130')
  })

  it('emits approve and delete', async () => {
    const terminal = makePendingTerminal()
    const wrapper = mountWithApp(PendingTerminalsTable, {
      props: { terminals: [terminal], canManage: true, missingHint: '' },
    })
    await flushPromises()

    await wrapper.get('[data-testid="terminal-approve"]').trigger('click')
    await wrapper.get('[data-testid="terminal-delete"]').trigger('click')

    expect(wrapper.emitted('approve')).toEqual([[terminal]])
    expect(wrapper.emitted('delete')).toEqual([[terminal]])
  })

  it('disables Approve without manage:terminals', async () => {
    const wrapper = mountWithApp(PendingTerminalsTable, {
      props: { terminals: [makePendingTerminal()], canManage: false, missingHint: MISSING },
    })
    await flushPromises()

    const approve = wrapper.get('[data-testid="terminal-approve"]')
    expect(approve.attributes('disabled')).toBeDefined()
    await approve.trigger('click')
    expect(wrapper.emitted('approve')).toBeUndefined()
  })

  it('offers Approve and Delete from the context menu', async () => {
    const terminal = makePendingTerminal()
    const wrapper = mountWithApp(PendingTerminalsTable, {
      props: { terminals: [terminal], canManage: true, missingHint: '' },
    })
    await flushPromises()

    const items = await contextMenu(wrapper)

    expect(shape(items)).toEqual([
      i18n.global.t('terminals.actions.approve'),
      '---',
      i18n.global.t('terminals.actions.delete'),
    ])
    for (const item of items) item.command?.()
    expect(wrapper.emitted('approve')).toEqual([[terminal]])
    expect(wrapper.emitted('delete')).toEqual([[terminal]])
    // The short list keeps its actions column.
    expect(wrapper.find('[data-testid="terminal-approve"]').exists()).toBe(true)
  })

  it('disables both context menu entries without manage:terminals', async () => {
    const wrapper = mountWithApp(PendingTerminalsTable, {
      props: { terminals: [makePendingTerminal()], canManage: false, missingHint: MISSING },
    })
    await flushPromises()

    const items = (await contextMenu(wrapper)).filter((item) => !item.separator)

    expect(items.map((item) => [item.disabled, item.title])).toEqual([
      [true, MISSING],
      [true, MISSING],
    ])
  })
})
