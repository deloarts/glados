import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useClipboard } from '@/core/composables/useClipboard'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useDialogTarget } from './useDialogTarget'
import { useMissingPermission } from './useMissingPermission'

import type {
  DataTableRowClickEvent,
  DataTableRowContextMenuEvent,
  DataTableRowSelectEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

/**
 * The shape every `*ManagementTable.vue` row needs for this composable to
 * act on it: an id to mutate/guard by, and a public_id for "copy UUID".
 */
export interface ManagedEntity {
  id: number
  public_id: string
  /** The row's edit version, which a delete sends back when the row has one. */
  edit_version?: number
}

/** The store method used for a hard-delete resource. */
export interface ManagementResourceActionsDeleteStore {
  remove: (id: number, editVersion?: number) => Promise<void>
}

/**
 * The store shape for an archivable resource, used with
 * `options.archivable`.
 */
export interface ManagementResourceActionsArchiveStore {
  archive: (id: number) => Promise<void>
  restore: (id: number) => Promise<void>
}

export type ManagementResourceActionsStore =
  | ManagementResourceActionsDeleteStore
  | ManagementResourceActionsArchiveStore

/** The part of the `<ContextMenu>` instance this composable calls. */
export interface ContextMenuHandle {
  show: (event: Event) => void
}

export interface UseManagementResourceActionsOptions<T extends ManagedEntity> {
  /**
   * i18n prefix holding `deleteConfirm` and `errors.unknown`, e.g.
   * `'settings.articleGroups'`.
   */
  i18nPrefix: string
  /**
   * Display name shown in the delete-confirm message and the delete
   * success toast's summary, e.g. `(group) => group.name`.
   */
  entityLabel: (entity: T) => string
  /**
   * Gates the built-in Delete menu item's `disabled` state. Editing's own
   * permission stays with the feature-supplied `editItem`, since it also
   * gates the table's separate inline edit button.
   */
  deletePermission: string
  /**
   * Disables the built-in Delete or Archive menu item for an entity whose
   * state does not allow it, such as work still in process on it. The
   * permission stays with `deletePermission`.
   */
  deleteBlocked?: (entity: T) => boolean
  /**
   * Why the entity's state rules out Delete or Archive, or '' when it does
   * not. A non-empty reason disables the menu item like `deleteBlocked` and
   * becomes its title, the same text the row's button shows as tooltip.
   */
  deleteBlockedReason?: (entity: T) => string
  /** Feature-owned "Edit" menu entry placed first; omit for no edit item. */
  editItem?: (entity: T) => MenuItem
  /**
   * Overrides what opening a row does; the default shows the detail
   * dialog.
   */
  onShowDetail?: (entity: T) => void
  /**
   * Set to false to leave out the built-in "Show details" entry, for a
   * table without a detail dialog or one that puts its own open entry into
   * `extraItems`.
   */
  showDetailItem?: boolean
  /** Extra items after "Show details", e.g. projects' "Show items". */
  extraItems?: (entity: T) => MenuItem[]
  /** Params for `deleteConfirm` when the placeholder is not `{name}`. */
  deleteConfirmParams?: (entity: T) => Record<string, unknown>
  /**
   * Archive and restore instead of a hard delete; `store` must then be an
   * archive store. `isArchived` shows Restore only for archived rows.
   */
  archivable?: {
    isArchived: (entity: T) => boolean
    /**
     * Interpolation params for `common.archiveConfirm`, defaults to
     * `{ name: entityLabel(entity) }`, same as `deleteConfirmParams`.
     */
    archiveConfirmParams?: (entity: T) => Record<string, unknown>
  }
}

export interface UseManagementResourceActionsResult<T extends ManagedEntity> {
  /** Bind via `ref="cm"` on the table's own `<ContextMenu>`. */
  cm: Ref<ContextMenuHandle | null>
  /** Bind via `v-model:contextMenuSelection` on the `<DataTable>`. */
  contextMenuTarget: Ref<T | null>
  /** Bind to `<ResourceDetailDialog v-model:visible>` (or an equivalent). */
  detailDialogVisible: Ref<boolean>
  /** The row currently shown in the detail dialog. */
  detailTarget: Ref<T | null>
  /** The `:model` for the table's `<ContextMenu>`. */
  contextMenuItems: ComputedRef<MenuItem[]>
  /** Bind to `@row-contextmenu`. */
  onRowContextMenu: (event: DataTableRowContextMenuEvent) => void
  /**
   * Bind to both `@row-click` and `@row-select`; the open guard keeps the
   * double event idempotent.
   */
  onRowClick: (event: DataTableRowClickEvent<T> | DataTableRowSelectEvent<T>) => void
  /**
   * The delete-confirm+toast block (archive-confirm+toast when
   * `options.archivable` is set). Bind to a row action button or call from
   * a menu item.
   */
  onDelete: (entity: T) => void
  /**
   * Restores an archived row without confirmation, since it is reversible,
   * and shows a 409 conflict's detail in the toast.
   */
  onRestore: (entity: T) => Promise<void>
}

/**
 * The row actions every management table shares: the context menu, the
 * delete confirmation with its toasts, and opening the detail dialog. The
 * table's columns, filters and edit dialog stay feature-owned.
 */
export function useManagementResourceActions<T extends ManagedEntity>(
  store: ManagementResourceActionsStore,
  options: UseManagementResourceActionsOptions<T>,
): UseManagementResourceActionsResult<T> {
  const { t } = useI18n()
  const confirm = useConfirm()
  const appToast = useAppToast()
  const { copyToClipboard } = useClipboard()
  const { hasPermission } = usePermissions()
  const { missing } = useMissingPermission()
  const { guard: guardRowOpen } = useRowOpenGuard<number>()

  const cm = ref<ContextMenuHandle | null>(null)
  const contextMenuTarget = ref<T | null>(null) as Ref<T | null>

  const { target: detailTarget, visible: detailDialogVisible, open: openDetailDialog } =
    useDialogTarget<T>()

  const canDelete = computed(() => hasPermission(options.deletePermission))

  function showDetail(entity: T): void {
    if (options.onShowDetail) {
      options.onShowDetail(entity)
      return
    }
    openDetailDialog(entity)
  }

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  function onRowClick(event: DataTableRowClickEvent<T> | DataTableRowSelectEvent<T>): void {
    const entity = event.data
    guardRowOpen(entity.id, () => showDetail(entity))
  }

  function onDelete(entity: T): void {
    const archivable = options.archivable

    async function onAccept(): Promise<void> {
      try {
        if (archivable && 'archive' in store) {
          await store.archive(entity.id)
        } else if ('remove' in store) {
          // A row with an edit version sends the one shown, so a row
          // someone changed meanwhile is refused instead of deleted.
          if (entity.edit_version === undefined) await store.remove(entity.id)
          else await store.remove(entity.id, entity.edit_version)
        }
        appToast.success(options.entityLabel(entity), t(archivable ? 'common.archive' : 'common.delete'))
      } catch (e) {
        // The server's reason, when it gives one (a project with live work
        // is not deleted, for example), like onRestore shows it.
        const reason = extractApiError(e)
        if (reason) {
          appToast.error(options.entityLabel(entity), reason)
        } else {
          appToast.error(t(`${options.i18nPrefix}.errors.unknown`))
        }
      }
    }

    confirm.require({
      message: archivable
        ? t(
            'common.archiveConfirm',
            archivable.archiveConfirmParams?.(entity) ?? { name: options.entityLabel(entity) },
          )
        : t(
            `${options.i18nPrefix}.deleteConfirm`,
            options.deleteConfirmParams?.(entity) ?? { name: options.entityLabel(entity) },
          ),
      header: t(archivable ? 'common.archive' : 'common.delete'),
      icon: archivable ? 'mdi mdi-archive-outline' : 'mdi mdi-delete-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: {
        label: t(archivable ? 'common.archive' : 'common.delete'),
        severity: archivable ? 'warn' : 'danger',
      },
      accept: () => void onAccept(),
    })
  }

  async function onRestore(entity: T): Promise<void> {
    if (!('restore' in store)) return
    try {
      await store.restore(entity.id)
      appToast.success(options.entityLabel(entity), t('common.restore'))
    } catch (e) {
      appToast.error(
        options.entityLabel(entity),
        extractApiError(e) ?? t(`${options.i18nPrefix}.errors.unknown`),
      )
    }
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const entity = contextMenuTarget.value
    if (!entity) return []

    const items: MenuItem[] = []

    const editItem = options.editItem?.(entity)
    if (editItem) {
      items.push(editItem, { separator: true })
    }

    if (options.showDetailItem !== false) {
      items.push({
        label: t('common.showDetails'),
        icon: 'mdi mdi-information-outline',
        command: () => showDetail(entity),
      })
    }

    const extraItems = options.extraItems?.(entity) ?? []
    items.push(...extraItems)

    // A disabled entry carries its reason as title, which the menu shows
    // when it binds disabledItemTooltipPt.
    const permissionReason = missing(options.deletePermission)
    const stateReason = options.deleteBlockedReason?.(entity) ?? ''
    const archivable = options.archivable
    const archiveOrDeleteItem: MenuItem =
      archivable && archivable.isArchived(entity)
        ? {
            label: t('common.restore'),
            icon: 'mdi mdi-archive-arrow-up-outline',
            disabled: !canDelete.value,
            title: permissionReason || undefined,
            command: () => void onRestore(entity),
          }
        : {
            label: t(archivable ? 'common.archive' : 'common.delete'),
            icon: archivable ? 'mdi mdi-archive-outline' : 'mdi mdi-delete-outline',
            disabled:
              !canDelete.value || (options.deleteBlocked?.(entity) ?? false) || stateReason !== '',
            title: permissionReason || stateReason || undefined,
            command: () => onDelete(entity),
          }

    items.push(
      { separator: true },
      archiveOrDeleteItem,
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(entity.public_id),
      },
    )

    return items
  })

  return {
    cm,
    contextMenuTarget,
    detailDialogVisible,
    detailTarget,
    contextMenuItems,
    onRowContextMenu,
    onRowClick,
    onDelete,
    onRestore,
  }
}
