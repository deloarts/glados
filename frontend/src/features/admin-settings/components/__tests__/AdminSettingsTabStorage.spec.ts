import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  AdminStorageSettings,
  AllAdminSettings,
  StorageMigrationProgressEvent,
  StorageMigrationResult,
  StorageMigrationStatus,
} from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabGeneral.locales.spec.ts / AdminSettingsTabMaintenance.spec.ts's
// mount/userWithPermissions/store-seeding pattern. No full-tab spec existed for Storage
// yet, so this one is scoped to the disk_warning_percent field and the
// SeaweedFS defaults rather than covering the whole tab (migrate dialog, etc.).

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

const streamMigrationMock =
  vi.fn<
    (
      cmd: unknown,
      onProgress: (ev: StorageMigrationProgressEvent) => void,
    ) => Promise<StorageMigrationResult>
  >()
vi.mock('../../api/streamStorageMigration', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/streamStorageMigration')>()),
  streamStorageMigration: (cmd: unknown, onProgress: (ev: StorageMigrationProgressEvent) => void) =>
    streamMigrationMock(cmd, onProgress),
}))

// The tab asks for the migration status on mount, so every test needs an
// answer; no migration is running unless a test says otherwise.
const migrationStatusMock = vi.fn<() => Promise<StorageMigrationStatus>>(() =>
  Promise.resolve({ running: false, run: null }),
)
vi.mock('../../api/getStorageMigrationStatus', () => ({
  getStorageMigrationStatus: () => migrationStatusMock(),
}))

import AdminSettingsTabStorage from '../AdminSettingsTabStorage.vue'

function makeStorageSettings(overrides: Partial<AdminStorageSettings> = {}): AdminStorageSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    provider: 'local',
    enabled: true,
    endpoint_url: null,
    public_endpoint_url: null,
    bucket_name: null,
    access_key: null,
    secret_key_configured: false,
    region: null,
    use_ssl: true,
    backup_enabled: false,
    backup_path: null,
    backup_cron: null,
    backup_retention_count: 7,
    disk_warning_percent: 90,
    ...overrides,
  }
}

async function mountTab(permissions: string[], storage: AdminStorageSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  // Seeded directly rather than driven through fetch(): only `storage` is
  // under test, so the rest of AllAdminSettings would be dead weight.
  useAdminSettingsStore().settings = { storage } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabStorage, {
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function fieldRowByLabel(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.field-row').find((r) => r.text().includes(label))!
}

function diskWarningInput(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.storage.diskWarningPercent') as string
  return fieldRowByLabel(wrapper, label).findComponent({ name: 'InputNumber' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabStorage disk_warning_percent', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('reflects settings.storage.disk_warning_percent in the field', async () => {
    const wrapper = await mountTab(['write:settings'], makeStorageSettings({ disk_warning_percent: 75 }))

    expect(diskWarningInput(wrapper).props('modelValue')).toBe(75)

    wrapper.unmount()
  })

  it('shows the hint explaining 0 disables and warnings go to the Mail tab', async () => {
    const wrapper = await mountTab(['write:settings'], makeStorageSettings())

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.storage.diskWarningPercentHint'),
    )

    wrapper.unmount()
  })

  it('disables the field without write:settings', async () => {
    const wrapper = await mountTab([], makeStorageSettings())

    expect(diskWarningInput(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })

  it('PUTs disk_warning_percent with the rest of the form on Save', async () => {
    putMock.mockResolvedValue({ data: makeStorageSettings({ disk_warning_percent: 50 }) })
    const wrapper = await mountTab(['write:settings'], makeStorageSettings())

    await diskWarningInput(wrapper).vm.$emit('update:modelValue', 50)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/storage',
      expect.objectContaining({ disk_warning_percent: 50 }),
    )

    wrapper.unmount()
  })
})

describe('AdminSettingsTabStorage SeaweedFS defaults', () => {
  function providerSelect(wrapper: ReturnType<typeof mount>) {
    const label = i18n.global.t('adminSettings.storage.provider') as string
    return fieldRowByLabel(wrapper, label).findComponent({ name: 'Select' })
  }

  function textInput(wrapper: ReturnType<typeof mount>, labelKey: string) {
    const label = i18n.global.t(labelKey) as string
    return fieldRowByLabel(wrapper, label).findComponent({ name: 'InputText' })
  }

  it('replaces the previous endpoint and bucket when SeaweedFS is picked', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeStorageSettings({
        provider: 's3',
        endpoint_url: 'http://objects.example.com:9000',
        bucket_name: 'media',
      }),
    )

    await providerSelect(wrapper).vm.$emit('update:modelValue', 'seaweedfs')

    expect(textInput(wrapper, 'adminSettings.storage.labels.endpointUrl.seaweedfs').props('modelValue')).toBe(
      'http://seaweedfs:8333',
    )
    expect(textInput(wrapper, 'adminSettings.storage.labels.bucketName.seaweedfs').props('modelValue')).toBe(
      'objects',
    )

    wrapper.unmount()
  })

  it('keeps saved SeaweedFS values when SeaweedFS is picked again', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeStorageSettings({
        provider: 'seaweedfs',
        endpoint_url: 'http://localhost:8333',
        bucket_name: 'objects',
      }),
    )

    await providerSelect(wrapper).vm.$emit('update:modelValue', 'seaweedfs')

    expect(textInput(wrapper, 'adminSettings.storage.labels.endpointUrl.seaweedfs').props('modelValue')).toBe(
      'http://localhost:8333',
    )

    wrapper.unmount()
  })
})

describe('AdminSettingsTabStorage migration progress', () => {
  function buttonByLabel(wrapper: ReturnType<typeof mount>, labelKey: string) {
    const label = i18n.global.t(labelKey) as string
    return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)!
  }

  beforeEach(() => {
    streamMigrationMock.mockReset()
    migrationStatusMock.mockReset()
    migrationStatusMock.mockResolvedValue({ running: false, run: null })
  })

  it('shows the count and the file being copied while the migration runs', async () => {
    streamMigrationMock.mockImplementation((_cmd, onProgress) => {
      onProgress({ current: 1, total: 2, key: 'documents/42/preview.png' })
      return new Promise(() => {})
    })
    const wrapper = await mountTab(
      ['read:settings', 'write:settings'],
      makeStorageSettings({ provider: 's3' }),
    )

    await buttonByLabel(wrapper, 'adminSettings.storage.migrate').trigger('click')
    await flushPromises()
    await buttonByLabel(wrapper, 'adminSettings.storage.migrateDialog.startMigration').trigger(
      'click',
    )
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.storage.migrateDialog.progress', { current: 1, total: 2 }),
    )
    expect(document.body.querySelector('[data-testid="migration-current-key"]')?.textContent).toContain(
      'documents/42/preview.png',
    )

    wrapper.unmount()
  })

  it('opens the progress for a migration that is already running', async () => {
    migrationStatusMock.mockResolvedValue({
      running: true,
      run: {
        user_name: 'Admin',
        started_at: '2026-10-08T10:00:00Z',
        current: 12,
        total: 458,
        detail: 'avatars/3.png',
      },
    })

    const wrapper = await mountTab(['read:settings', 'write:settings'], makeStorageSettings())

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.storage.migrateDialog.progress', { current: 12, total: 458 }),
    )
    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.storage.migrateDialog.startedBy', { name: 'Admin' }),
    )
    expect(streamMigrationMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})
