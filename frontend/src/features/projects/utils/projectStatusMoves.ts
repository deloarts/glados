import { hasAction, type LifecycleAction } from '@/core/utils/lifecycleActions'
import type {
  ProjectLiveWork,
  ProjectResponse,
  ProjectStatus,
} from '@/features/projects/types/projectResponse'

// A project's status moves through the intents of its backend intent table
// (lifecycle/project.py): hold, resume, complete, archive and reopen. The
// response offers the moves the reading user may take now in `actions`, and
// `live_work` counts what blocks completing, archiving and deleting.

/**
 * The intent that moves a project from `current` to `target`, null when the
 * status stays. Mirrors project_status_move in the backend.
 */
export function projectStatusMove(
  current: ProjectStatus,
  target: ProjectStatus,
): LifecycleAction | null {
  if (current === target) return null
  switch (target) {
    case 'on_hold':
      return 'hold'
    case 'completed':
      return 'complete'
    case 'archived':
      return 'archive'
    case 'active':
      return current === 'on_hold' ? 'resume' : 'reopen'
  }
}

export type LiveWorkKind = keyof ProjectLiveWork

/** The kinds of live work the project still has, in display order, with their counts. */
export function liveWorkParts(
  work: ProjectLiveWork | null | undefined,
): { kind: LiveWorkKind; count: number }[] {
  if (!work) return []
  return (Object.keys(work) as LiveWorkKind[])
    .map((kind) => ({ kind, count: work[kind] }))
    .filter((part) => part.count > 0)
}

/**
 * Why the project cannot move to `target` now, null when it can or the
 * status stays. A move the live work blocks names it; any other refusal is
 * the project's current status. The permission is the caller's own check.
 */
export function statusMoveBlock(
  project: ProjectResponse,
  target: ProjectStatus,
): { kind: 'liveWork' } | { kind: 'status' } | null {
  const move = projectStatusMove(project.status, target)
  if (move === null || hasAction(project, move)) return null
  const byWork = move === 'complete' || move === 'archive'
  return byWork && liveWorkParts(project.live_work).length > 0
    ? { kind: 'liveWork' }
    : { kind: 'status' }
}
