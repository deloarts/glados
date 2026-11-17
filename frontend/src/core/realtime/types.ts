/**
 * Mirrors `LiveAction`/`LiveSignal` on the backend
 * (src/modules/platform/ports/outbound/live_signal.py). A signal carries row identity only,
 * never row data, so the client always refetches through the resource's
 * normal authenticated list endpoint.
 */
export type LiveAction = 'created' | 'updated' | 'deleted' | 'bulk'

export interface LiveSignal {
  resource: string
  id: number
  action: LiveAction
  actor_id: number | null
}
