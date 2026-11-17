import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { hasAction } from '@/core/utils/lifecycleActions'
import type { ProjectResponse, ProjectStatus } from '../types/projectResponse'
import { liveWorkParts, statusMoveBlock } from '../utils/projectStatusMoves'

/**
 * The texts that say why a project's status move or delete is not offered:
 * the missing permission, the live work that blocks it with its counts, or
 * the project's current status.
 */
export function useProjectMoveReasons() {
  const { t } = useI18n()
  const { missing } = useMissingPermission()

  function describeLiveWork(project: ProjectResponse): string {
    return liveWorkParts(project.live_work)
      .map((part) => t(`resources.projects.liveWork.${part.kind}`, part.count))
      .join(', ')
  }

  /** Why the project cannot move to `target` now, null when it can. */
  function statusMoveReason(project: ProjectResponse, target: ProjectStatus): string | null {
    if (target === project.status) return null
    const lacking = missing(Permission.MANAGE_PROJECTS)
    if (lacking) return lacking
    const block = statusMoveBlock(project, target)
    if (block === null) return null
    if (block.kind === 'liveWork') {
      return t('resources.projects.statusMove.liveWork', { work: describeLiveWork(project) })
    }
    return t('resources.projects.statusMove.notFromStatus', {
      status: t(`resources.projects.status.${project.status}`),
    })
  }

  /** Why the project cannot be deleted on state grounds, null when it can. */
  function deleteBlockedReason(project: ProjectResponse): string | null {
    if (hasAction(project, 'remove')) return null
    return t('resources.projects.deleteBlocked', { work: describeLiveWork(project) })
  }

  /** The tooltip of the delete button: what is missing, else its label. */
  function deleteTooltip(project: ProjectResponse): string {
    return missing(Permission.MANAGE_PROJECTS) || deleteBlockedReason(project) || t('common.delete')
  }

  return { statusMoveReason, deleteBlockedReason, deleteTooltip }
}
