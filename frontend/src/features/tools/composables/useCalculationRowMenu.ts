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
import type { DocumentPageAction, DocumentRowPermissions } from '@/shared/documents'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { toolByKey } from '../registry'
import type { CalculationSummaryResponse } from '../types/calculation'

/**
 * The context menu of a calculations table row, and what a row may do. The
 * steps of the document itself open the calculation, which carries them
 * out with its own checks; the menu only leaves out what the row already
 * rules out.
 */
export function useCalculationRowMenu(actions: {
  print: (row: CalculationSummaryResponse) => void
  remove: (row: CalculationSummaryResponse) => void
}) {
  const { t } = useI18n()
  const router = useRouter()
  const links = useDocumentRowLinks()
  const { missing } = useMissingPermission()
  const currentUserStore = useCurrentUserStore()

  const cm = ref<{ show: (event: Event) => void } | null>(null)
  const contextMenuItem = ref<CalculationSummaryResponse | null>(null)

  function location(row: CalculationSummaryResponse, action?: DocumentPageAction): RouteLocationRaw | null {
    const tool = toolByKey(row.tool)
    if (!tool) return null
    return { name: 'Tools', params: { tab: tool.tab, calc: row.public_id }, query: action ? { action } : {} }
  }

  function go(row: CalculationSummaryResponse, action?: DocumentPageAction): void {
    const to = location(row, action)
    if (to) void router.push(to)
  }

  // Each step first asks whether the row's state allows it, then which
  // permission or lock still blocks it; that blocker is the entry's title.
  function steps(row: CalculationSummaryResponse) {
    const write = missing(Permission.WRITE_CALCULATIONS)
    const manage = missing(Permission.MANAGE_CALCULATIONS)
    const userId = currentUserStore.user?.id ?? null
    const ownOrManage = row.creator_id === userId ? '' : manage
    const released = row.released_at != null
    const draft = row.is_latest && !released
    const editor = editingBy(row)
    const locked = editor !== null && row.locked_by_id !== userId ? t('documents.table.editing', { name: editor }) : ''
    return documentRowSteps({
      edit: documentRowStep(draft && !row.read_only, [write, ownOrManage, locked]),
      revise: documentRowStep(released && row.is_latest, [write]),
      release: documentRowStep(draft, [missing(Permission.RELEASE_CALCULATIONS)]),
      invalidate: documentRowStep(released && row.invalid_at == null, [manage]),
      delete: documentRowStep(draft, [write, ownOrManage]),
      copy: documentRowStep(true, [write]),
    })
  }

  function permissions(row: CalculationSummaryResponse): DocumentRowPermissions & { copy: boolean } {
    return steps(row).can
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const row = contextMenuItem.value
    if (!row) return []
    const { can, reasons } = steps(row)
    return documentRowMenu(
      {
        open: () => go(row),
        openInNewTab: () => {
          const to = location(row)
          if (to) links.openInNewTab(to)
        },
        copyLink: () => {
          const to = location(row)
          if (to) void links.copyLink(to)
        },
        print: () => actions.print(row),
        remove: () => actions.remove(row),
        pageAction: (action) => go(row, action),
        can,
        reasons,
        extra: [
          {
            label: t('tools.calculations.actions.saveAsNew'),
            icon: 'mdi mdi-content-save-plus-outline',
            disabled: !can.copy,
            title: reasons.copy || undefined,
            command: () => go(row, 'copy'),
          },
        ],
      },
      t,
    )
  })

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  return { cm, contextMenuItem, contextMenuItems, onRowContextMenu, permissions, open: go }
}
