import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'
import type { RouteLocationRaw } from 'vue-router'
import { useRouter } from 'vue-router'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import {
  documentRowMenu,
  documentRowStep,
  documentRowSteps,
  editingBy,
  useDocumentRowLinks,
} from '@/shared/documents'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import type { DocumentPageAction, DocumentRowPermissions } from '@/shared/documents'
import type { ChecklistSummaryResponse } from '../types/checklist'

/**
 * The context menu of a checklists table row, and what a row may do. The
 * steps of the document itself open the checklist, which carries them out
 * with its own checks, such as the reasons a checklist cannot be released
 * yet; the menu only leaves out what the row already rules out.
 */
export function useChecklistRowMenu(actions: {
  print: (row: ChecklistSummaryResponse) => void
  remove: (row: ChecklistSummaryResponse) => void
}) {
  const { t } = useI18n()
  const router = useRouter()
  const links = useDocumentRowLinks()
  const { missing } = useMissingPermission()
  const currentUserStore = useCurrentUserStore()

  const cm = ref<{ show: (event: Event) => void } | null>(null)
  const contextMenuItem = ref<ChecklistSummaryResponse | null>(null)

  function location(row: ChecklistSummaryResponse, action?: DocumentPageAction): RouteLocationRaw {
    return { name: 'ChecklistDetail', params: { id: row.id }, query: action ? { action } : {} }
  }

  function go(row: ChecklistSummaryResponse, action?: DocumentPageAction): void {
    void router.push(location(row, action))
  }

  // Each step first asks whether the row's state allows it, then which
  // permission or lock still blocks it; that blocker is the entry's title.
  function steps(row: ChecklistSummaryResponse) {
    const write = missing(Permission.WRITE_CHECKLISTS)
    const manage = missing(Permission.MANAGE_CHECKLISTS)
    const userId = currentUserStore.user?.id ?? null
    const ownOrManage = row.creator_id === userId ? '' : manage
    const released = row.released_at != null
    const draft = row.is_latest && !released
    const editor = editingBy(row)
    const locked = editor !== null && row.locked_by_id !== userId ? t('documents.table.editing', { name: editor }) : ''
    return documentRowSteps({
      edit: documentRowStep(draft && !row.read_only, [write, ownOrManage, locked]),
      revise: documentRowStep(row.is_latest && row.finished, [write]),
      release: documentRowStep(draft && row.release_required, [missing(Permission.RELEASE_CHECKLISTS)]),
      invalidate: documentRowStep(released && row.invalid_at == null, [manage]),
      delete: documentRowStep(draft, [write, ownOrManage]),
    })
  }

  function permissions(row: ChecklistSummaryResponse): DocumentRowPermissions {
    return steps(row).can
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const row = contextMenuItem.value
    if (!row) return []
    return documentRowMenu(
      {
        open: () => go(row),
        openInNewTab: () => links.openInNewTab(location(row)),
        copyLink: () => void links.copyLink(location(row)),
        print: () => actions.print(row),
        remove: () => actions.remove(row),
        pageAction: (action) => go(row, action),
        ...steps(row),
      },
      t,
    )
  })

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  return { cm, contextMenuItem, contextMenuItems, onRowContextMenu, permissions, open: go }
}
