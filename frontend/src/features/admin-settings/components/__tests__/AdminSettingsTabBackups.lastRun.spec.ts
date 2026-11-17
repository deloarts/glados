import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

import type { BackupList, BackupRunEntry } from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabMaintenance.spec.ts's mount/permission-user pattern
// and Toast-alongside-the-component technique for asserting on toast
// content. Unlike that spec, the backups tab fetches its own data through
// `store.fetchBackups()` (GET /admin/settings/storage/backups) rather than
// reading `store.settings`, so the fixture goes through the mocked `api.get`
// instead of being seeded onto the store directly.

const getMock = vi.fn<(url: string, config?: unknown) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload?: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: unknown) => getMock(url, config),
    post: (url: string, payload?: unknown) => postMock(url, payload),
  },
}))

import AdminSettingsTabBackups from '../AdminSettingsTabBackups.vue'

function makeBackupRun(overrides: Partial<BackupRunEntry> = {}): BackupRunEntry {
  return {
    slot: '2026-08-20T12:00:00Z',
    trigger: 'scheduled',
    status: 'success',
    started_at: '2026-08-20T12:00:00Z',
    finished_at: '2026-08-20T12:01:30Z',
    error: null,
    ...overrides,
  }
}

function makeBackupList(overrides: Partial<BackupList> = {}): BackupList {
  return {
    db: [],
    files: [],
    warnings: [],
    last_run: null,
    runs: [],
    ...overrides,
  }
}

async function mountTab(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mount(
    {
      components: { AdminSettingsTabBackups, Toast },
      template: '<div><AdminSettingsTabBackups /><Toast /></div>',
    },
    {
      attachTo: document.body,
      global: {
        plugins: [pinia, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
      },
    },
  )
  await flushPromises()
  return wrapper
}

// DataTable doesn't declare a real `emptyMessage` prop (it's OpenVue
// pass-through-class terminology, not a data prop: `:empty-message` on the
// tag is just an unrecognised attribute, mirroring the db/files tables in
// this component), so the history table can't be picked out via
// `.props()`. Its "Slot" column header is unique among the tab's three
// tables, so match on rendered text instead.
function historyTable(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  const slotHeader = i18n.global.t('adminSettings.backups.history.slot') as string
  return wrapper.findAllComponents({ name: 'DataTable' }).find((t) => t.text().includes(slotHeader))!
}

// Same reasoning as historyTable: pick the table out by a header string
// that's unique to it. "Storage Key" (db) vs "Snapshot Key" (files): their
// "Timestamp" headers collide, but the key columns don't.
function dbTable(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  const keyHeader = i18n.global.t('adminSettings.backups.db.key') as string
  return wrapper.findAllComponents({ name: 'DataTable' }).find((t) => t.text().includes(keyHeader))!
}

function filesTable(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  const keyHeader = i18n.global.t('adminSettings.backups.files.key') as string
  return wrapper.findAllComponents({ name: 'DataTable' }).find((t) => t.text().includes(keyHeader))!
}

describe('AdminSettingsTabBackups - last run + history', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    // ToastService's teleported DOM lives in document.body and outlives one
    // test's wrapper.unmount(); see AppSidebar.spec.ts's own comment.
    document.body.innerHTML = ''
  })

  it('renders the last-run line with status, trigger, and date from the list', async () => {
    const lastRun = makeBackupRun({
      trigger: 'scheduled',
      status: 'success',
      started_at: '2026-08-20T12:00:00Z',
      finished_at: '2026-08-20T12:01:30Z',
    })
    getMock.mockResolvedValue({ data: makeBackupList({ last_run: lastRun, runs: [lastRun] }) })

    const wrapper = await mountTab(['write:settings'])

    expect(document.body.textContent).toContain('2026-08-20')
    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.backups.trigger.scheduled') as string,
    )
    const statusTag = wrapper
      .findAllComponents({ name: 'Tag' })
      .find((tag) => tag.props('value') === (i18n.global.t('adminSettings.backups.status.success') as string))
    expect(statusTag).toBeTruthy()
    expect(statusTag!.props('severity')).toBe('success')

    wrapper.unmount()
  })

  it('shows "never" when last_run is null', async () => {
    getMock.mockResolvedValue({ data: makeBackupList() })

    const wrapper = await mountTab(['write:settings'])

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.backups.lastRun.never') as string,
    )

    wrapper.unmount()
  })

  it('shows the error text for a failed run', async () => {
    const lastRun = makeBackupRun({
      status: 'failed',
      trigger: 'manual',
      finished_at: '2026-08-20T12:00:45Z',
      error: 'pg_dump exited with status 1',
    })
    getMock.mockResolvedValue({ data: makeBackupList({ last_run: lastRun, runs: [lastRun] }) })

    const wrapper = await mountTab(['write:settings'])

    expect(document.body.textContent).toContain('pg_dump exited with status 1')
    const statusTag = wrapper
      .findAllComponents({ name: 'Tag' })
      .find((tag) => tag.props('value') === (i18n.global.t('adminSettings.backups.status.failed') as string))
    expect(statusTag).toBeTruthy()
    expect(statusTag!.props('severity')).toBe('danger')

    wrapper.unmount()
  })

  it('shows a running last run distinctly (info severity, no finished time available)', async () => {
    const lastRun = makeBackupRun({
      status: 'running',
      trigger: 'manual',
      started_at: '2026-08-20T12:00:00Z',
      finished_at: null,
      error: null,
    })
    getMock.mockResolvedValue({ data: makeBackupList({ last_run: lastRun, runs: [lastRun] }) })

    const wrapper = await mountTab(['write:settings'])

    const statusTag = wrapper
      .findAllComponents({ name: 'Tag' })
      .find((tag) => tag.props('value') === (i18n.global.t('adminSettings.backups.status.running') as string))
    expect(statusTag).toBeTruthy()
    expect(statusTag!.props('severity')).toBe('info')
    // Falls back to started_at since finished_at is null while running.
    expect(document.body.textContent).toContain('2026-08-20')

    wrapper.unmount()
  })

  it('renders one history row per run', async () => {
    const runs = [
      makeBackupRun({ slot: '2026-08-20T12:00:00Z', status: 'success' }),
      makeBackupRun({
        slot: '2026-08-19T12:00:00Z',
        status: 'failed',
        error: 'disk full',
        finished_at: '2026-08-19T12:00:20Z',
      }),
    ]
    getMock.mockResolvedValue({ data: makeBackupList({ last_run: runs[0], runs }) })

    const wrapper = await mountTab(['write:settings'])

    const table = historyTable(wrapper)
    expect(table.props('value')).toHaveLength(2)
    expect(document.body.textContent).toContain('disk full')

    wrapper.unmount()
  })

  it('shows the history table own empty-state text when there are no runs', async () => {
    getMock.mockResolvedValue({ data: makeBackupList({ runs: [] }) })

    const wrapper = await mountTab(['write:settings'])

    const table = historyTable(wrapper)
    expect(table.props('value')).toHaveLength(0)
    expect(table.text()).toContain(i18n.global.t('adminSettings.backups.history.empty') as string)

    wrapper.unmount()
  })

  it('shows the db table own empty-state text when there are no db backups (files non-empty, so the tables render)', async () => {
    getMock.mockResolvedValue({
      data: makeBackupList({
        db: [],
        files: [{ key: 'files/2026-08-20.tar.gz', timestamp: '2026-08-20T12:00:00Z', encrypted: false }],
      }),
    })

    const wrapper = await mountTab(['write:settings'])

    const table = dbTable(wrapper)
    expect(table.props('value')).toHaveLength(0)
    expect(table.text()).toContain(i18n.global.t('adminSettings.backups.db.empty') as string)

    wrapper.unmount()
  })

  it('shows the files table own empty-state text when there are no file snapshots (db non-empty, so the tables render)', async () => {
    getMock.mockResolvedValue({
      data: makeBackupList({
        db: [{ key: 'db/2026-08-20.sql.gz', timestamp: '2026-08-20T12:00:00Z', encrypted: false }],
        files: [],
      }),
    })

    const wrapper = await mountTab(['write:settings'])

    const table = filesTable(wrapper)
    expect(table.props('value')).toHaveLength(0)
    expect(table.text()).toContain(i18n.global.t('adminSettings.backups.files.empty') as string)

    wrapper.unmount()
  })

  it('run-now 409 shows the backend detail in the error toast', async () => {
    getMock.mockResolvedValue({ data: makeBackupList() })
    postMock.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 409,
        data: { detail: 'A backup is already running.' },
      },
    })

    const wrapper = await mountTab(['write:settings'])

    const runNowButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.backups.runNow') as string))!
    await runNowButton.trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain('A backup is already running.')
    expect(document.body.textContent).not.toContain(
      i18n.global.t('adminSettings.errors.unknown') as string,
    )

    wrapper.unmount()
  })

  it('still renders the db and file lists (existing behaviour)', async () => {
    getMock.mockResolvedValue({
      data: makeBackupList({
        db: [{ key: 'db/2026-08-20.sql.gz', timestamp: '2026-08-20T12:00:00Z', encrypted: false }],
        files: [{ key: 'files/2026-08-20.tar.gz', timestamp: '2026-08-20T12:00:00Z', encrypted: false }],
      }),
    })

    const wrapper = await mountTab(['write:settings'])

    expect(document.body.textContent).toContain('db/2026-08-20.sql.gz')
    expect(document.body.textContent).toContain('files/2026-08-20.tar.gz')
    expect(document.body.textContent).not.toContain(
      i18n.global.t('adminSettings.backups.notEnabled') as string,
    )

    wrapper.unmount()
  })

  it('shows one warning per backup warning the list carries', async () => {
    getMock.mockResolvedValue({
      data: makeBackupList({ warnings: ['stored_on_host', 'encryption_key_missing'] }),
    })

    const wrapper = await mountTab(['write:settings'])

    const shown = wrapper.findAll('[data-warning]').map((w) => w.attributes('data-warning'))
    expect(shown).toEqual(['stored_on_host', 'encryption_key_missing'])
    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.backups.warnings.encryption_key_missing') as string,
    )

    wrapper.unmount()
  })

  it('marks encrypted and unencrypted database archives', async () => {
    getMock.mockResolvedValue({
      data: makeBackupList({
        db: [
          { key: 'db/2026-08-21.sql.gz.enc', timestamp: '2026-08-21T12:00:00Z', encrypted: true },
          { key: 'db/2026-08-20.sql.gz', timestamp: '2026-08-20T12:00:00Z', encrypted: false },
        ],
      }),
    })

    const wrapper = await mountTab(['write:settings'])

    const text = dbTable(wrapper).text()
    expect(text).toContain(i18n.global.t('adminSettings.backups.db.encrypted') as string)
    expect(text).toContain(i18n.global.t('adminSettings.backups.db.unencrypted') as string)

    wrapper.unmount()
  })
})
