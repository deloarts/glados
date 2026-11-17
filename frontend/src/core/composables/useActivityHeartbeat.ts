import { onScopeDispose } from 'vue'

import { getCurrentUser } from '@/core/api/users/getCurrentUser'
import { hasUnreportedActivity } from '@/core/session/userActivity'

/** How often the heartbeat looks for activity no request has reported. */
export const ACTIVITY_HEARTBEAT_MS = 60 * 1000

/**
 * Tells the backend about activity that causes no request of its own, such
 * as typing a long remark, so the session stays alive while the user works.
 * Without new activity it sends nothing, and the session runs out after the
 * idle timeout the administrators set. Runs while the signed-in layout is
 * mounted.
 */
export function useActivityHeartbeat(): void {
  const timer = setInterval(() => {
    if (hasUnreportedActivity()) getCurrentUser().catch(() => {})
  }, ACTIVITY_HEARTBEAT_MS)
  onScopeDispose(() => clearInterval(timer))
}
