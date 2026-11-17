import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { SseHttpError } from '@/core/realtime/sseClient'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  StorageMigrationProgressEvent,
  StorageMigrationResult,
  StorageMigrationStatus,
  UpdateStorageSettingsCommand,
} from '../../types/adminSettingsTypes'

const streamMock =
  vi.fn<
    (
      cmd: UpdateStorageSettingsCommand,
      onProgress: (ev: StorageMigrationProgressEvent) => void,
      signal: AbortSignal,
    ) => Promise<StorageMigrationResult>
  >()
vi.mock('../../api/streamStorageMigration', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/streamStorageMigration')>()),
  streamStorageMigration: (
    cmd: UpdateStorageSettingsCommand,
    onProgress: (ev: StorageMigrationProgressEvent) => void,
    signal: AbortSignal,
  ) => streamMock(cmd, onProgress, signal),
}))

const statusMock = vi.fn<() => Promise<StorageMigrationStatus>>()
vi.mock('../../api/getStorageMigrationStatus', () => ({
  getStorageMigrationStatus: () => statusMock(),
}))

import { StorageMigrationConnectionLostError } from '../../api/streamStorageMigration'
import { useStorageMigration } from '../useStorageMigration'

const cmd: UpdateStorageSettingsCommand = {
  provider: 'seaweedfs',
  enabled: true,
  use_ssl: false,
  backup_enabled: false,
  backup_retention_count: 7,
  disk_warning_percent: 90,
}

const committed: StorageMigrationResult = {
  migrated_count: 2,
  failed_count: 0,
  errors: [],
  committed: true,
}

function runningStatus(current: number, total: number, detail: string): StorageMigrationStatus {
  return {
    running: true,
    run: { user_name: 'Admin', started_at: '2026-10-08T10:00:00Z', current, total, detail },
  }
}

function mountComposable() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const fetchSpy = vi.spyOn(useAdminSettingsStore(), 'fetch').mockResolvedValue()
  let result!: ReturnType<typeof useStorageMigration>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useStorageMigration()
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { result, wrapper, fetchSpy }
}

describe('useStorageMigration', () => {
  beforeEach(() => {
    streamMock.mockReset()
    statusMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('follows the stream and names the file being copied', async () => {
    let report!: (ev: StorageMigrationProgressEvent) => void
    let finish!: (result: StorageMigrationResult) => void
    streamMock.mockImplementation(
      (_cmd, onProgress) =>
        new Promise((resolve) => {
          report = onProgress
          finish = resolve
        }),
    )
    const { result, fetchSpy } = mountComposable()

    const started = result.start(cmd)
    report({ current: 1, total: 2, key: 'documents/42/preview.png' })

    expect(result.phase.value).toBe('running')
    expect(result.current.value).toBe(1)
    expect(result.total.value).toBe(2)
    expect(result.percent.value).toBe(50)
    expect(result.currentKey.value).toBe('documents/42/preview.png')

    finish(committed)
    await started

    expect(result.phase.value).toBe('done')
    expect(result.result.value).toEqual(committed)
    expect(fetchSpy).toHaveBeenCalledOnce()
  })

  it('keeps following the migration through the status endpoint when the stream drops', async () => {
    vi.useFakeTimers()
    streamMock.mockRejectedValue(new StorageMigrationConnectionLostError())
    statusMock.mockResolvedValueOnce(runningStatus(30, 458, 'items/7/drawing.pdf'))
    statusMock.mockResolvedValue({ running: false, run: null })
    const { result, fetchSpy } = mountComposable()

    await result.start(cmd)
    expect(result.phase.value).toBe('observing')

    await vi.advanceTimersByTimeAsync(3000)
    expect(result.current.value).toBe(30)
    expect(result.currentKey.value).toBe('items/7/drawing.pdf')
    expect(result.startedBy.value).toBe('Admin')

    await vi.advanceTimersByTimeAsync(3000)
    expect(result.phase.value).toBe('finishedElsewhere')
    expect(fetchSpy).toHaveBeenCalledOnce()
  })

  it('observes the running migration when another one holds the lock', async () => {
    streamMock.mockRejectedValue(new SseHttpError(409))
    const { result } = mountComposable()

    await result.start(cmd)

    expect(result.phase.value).toBe('observing')
  })

  it('rethrows a failed migration and returns to idle', async () => {
    streamMock.mockRejectedValue(new Error('bucket_name is required'))
    const { result } = mountComposable()

    await expect(result.start(cmd)).rejects.toThrow('bucket_name is required')

    expect(result.phase.value).toBe('idle')
  })

  it('picks up a migration that is already running', async () => {
    statusMock.mockResolvedValue(runningStatus(12, 458, 'avatars/3.png'))
    const { result } = mountComposable()

    expect(await result.checkRunning()).toBe(true)
    await flushPromises()

    expect(result.phase.value).toBe('observing')
    expect(result.current.value).toBe(12)
    expect(result.currentKey.value).toBe('avatars/3.png')
  })

  it('reports no migration when the status endpoint says so', async () => {
    statusMock.mockResolvedValue({ running: false, run: null })
    const { result } = mountComposable()

    expect(await result.checkRunning()).toBe(false)
    expect(result.phase.value).toBe('idle')
  })
})
