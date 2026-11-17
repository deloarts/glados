import { streamSse } from '@/core/realtime/sseClient'

import type {
  StorageMigrationProgressEvent,
  StorageMigrationResult,
  UpdateStorageSettingsCommand,
} from '../types/adminSettingsTypes'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const MIGRATE_STREAM_URL = `${API_ROOT}/api/v1/web/admin/settings/storage/migrate/stream`

/**
 * The stream closed before a result or error frame. The migration's outcome
 * is unknown here, but it keeps going on the server.
 */
export class StorageMigrationConnectionLostError extends Error {
  constructor() {
    super('Storage migration stream ended without a result or error frame')
    this.name = 'StorageMigrationConnectionLostError'
  }
}

// Runs one migration over the SSE endpoint and resolves with the same shape
// as POST /storage/migrate. Unknown event names are ignored.
export async function streamStorageMigration(
  cmd: UpdateStorageSettingsCommand,
  onProgress: (ev: StorageMigrationProgressEvent) => void,
  signal: AbortSignal,
): Promise<StorageMigrationResult> {
  let result: StorageMigrationResult | null = null
  let errorDetail: string | null = null

  await streamSse(
    {
      url: MIGRATE_STREAM_URL,
      method: 'POST',
      body: JSON.stringify(cmd),
      // This stream bypasses axios, so it adds the CSRF header itself.
      headers: () => ({
        'Content-Type': 'application/json',
        'X-Requested-With': 'glados',
      }),
      onOpen: () => {},
      onFrame: (frame) => {
        if (frame.event === 'progress') {
          try {
            onProgress(JSON.parse(frame.data) as StorageMigrationProgressEvent)
          } catch {
            // Malformed frame: ignore it, the next one carries the same fields.
          }
        } else if (frame.event === 'result') {
          result = JSON.parse(frame.data) as StorageMigrationResult
        } else if (frame.event === 'error') {
          errorDetail = (JSON.parse(frame.data) as { detail: string }).detail
        }
      },
    },
    signal,
  )

  if (errorDetail !== null) throw new Error(errorDetail)
  if (result !== null) return result
  throw new StorageMigrationConnectionLostError()
}
