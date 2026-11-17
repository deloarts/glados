const API_ROOT = import.meta.env.VITE_API_URL ?? ''

export const LIVE_STREAM_URL = `${API_ROOT}/api/v1/web/live/`

// Coalescing window for row-patch signals: several "updated" signals for
// the same table within this window collapse into one ids-refetch.
export const LIVE_COALESCE_MS = 250

// Reconnect backoff ladder, seconds -> ms. After a deploy every client of
// every gunicorn worker reconnects at once, so this also gets +-20% jitter
// (see liveStore.ts) to avoid a synchronized retry storm.
export const LIVE_RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000]
export const LIVE_RECONNECT_JITTER_RATIO = 0.2
