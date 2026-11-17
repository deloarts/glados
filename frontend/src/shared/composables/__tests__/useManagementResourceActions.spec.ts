import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { permissionLabel } from '@/shared/utils/permissionLabels'

import type { MenuItem } from 'openvue/menuitem'

interface Entity {
  id: number
  public_id: string
  name: string
  archived?: boolean
}

function makeEntity(overrides: Partial<Entity> = {}): Entity {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    name: 'Sheet Metal',
    ...overrides,
  }
}

// `confirm.require`/`toast.add`/`copyToClipboard` are asserted directly on
// their mocks, same approach as OrdersTable.spec.ts (confirm) and
// UserFormDialog.spec.ts (toast); real `ConfirmDialog`/`Toast` components
// aren't part of what this composable renders, so there's nothing to mount.
interface CapturedConfirmOptions {
  message: string
  header: string
  acceptProps: { label: string; severity: string }
  rejectProps: { label: string; severity: string }
  accept: () => Promise<void>
}

const confirmRequireMock = vi.fn<(options: CapturedConfirmOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

const copyToClipboardMock = vi.fn<(value: string) => Promise<void>>()
vi.mock('@/core/composables/useClipboard', () => ({
  useClipboard: () => ({ copyToClipboard: copyToClipboardMock }),
}))

import {
  useManagementResourceActions,
  type ManagementResourceActionsStore,
  type UseManagementResourceActionsOptions,
  type UseManagementResourceActionsResult,
} from '../useManagementResourceActions'

// Real keys from an existing feature (article-groups): "the drift-free
// delete-confirm+toast block" this composable generalizes already lives at
// this i18n prefix, so asserting against `i18n.global.t(...)` is exercising
// the real translation, not inventing a parallel fixture.
const I18N_PREFIX = 'settings.articleGroups'
const DELETE_PERMISSION = 'delete:widgets'

function makeStore(): ManagementResourceActionsStore & {
  remove: ReturnType<typeof vi.fn<(id: number) => Promise<void>>>
} {
  return { remove: vi.fn<(id: number) => Promise<void>>() }
}

function makeArchiveStore(): ManagementResourceActionsStore & {
  archive: ReturnType<typeof vi.fn<(id: number) => Promise<void>>>
  restore: ReturnType<typeof vi.fn<(id: number) => Promise<void>>>
} {
  return {
    archive: vi.fn<(id: number) => Promise<void>>(),
    restore: vi.fn<(id: number) => Promise<void>>(),
  }
}

function mountComposable(
  store: ManagementResourceActionsStore,
  options: UseManagementResourceActionsOptions<Entity>,
  permissions: string[] = [],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  let result!: UseManagementResourceActionsResult<Entity>
  const wrapper = mountWithApp(
    defineComponent({
      setup() {
        result = useManagementResourceActions<Entity>(store, options)
        return () => h('div')
      },
    }),
    { pinia },
  )
  return { result, wrapper }
}

function baseOptions(
  overrides: Partial<UseManagementResourceActionsOptions<Entity>> = {},
): UseManagementResourceActionsOptions<Entity> {
  return {
    i18nPrefix: I18N_PREFIX,
    entityLabel: (entity) => entity.name,
    deletePermission: DELETE_PERMISSION,
    ...overrides,
  }
}

function invoke(item: MenuItem | undefined): void {
  ;(item as { command?: () => void } | undefined)?.command?.()
}

describe('useManagementResourceActions', () => {
  beforeEach(() => {
    confirmRequireMock.mockReset()
    toastAddMock.mockReset()
    copyToClipboardMock.mockReset()
  })

  it('starts with no context-menu target, no ContextMenu bound, and the detail dialog hidden', () => {
    const { result } = mountComposable(makeStore(), baseOptions())

    expect(result.cm.value).toBeNull()
    expect(result.contextMenuTarget.value).toBeNull()
    expect(result.detailDialogVisible.value).toBe(false)
    expect(result.detailTarget.value).toBeNull()
    expect(result.contextMenuItems.value).toEqual([])
  })

  it('onRowContextMenu shows the bound ContextMenu with the original event', () => {
    const { result } = mountComposable(makeStore(), baseOptions())
    const show = vi.fn<(event: Event) => void>()
    result.cm.value = { show }
    const originalEvent = new Event('contextmenu')

    result.onRowContextMenu({ originalEvent, data: makeEntity(), index: 0 })

    expect(show).toHaveBeenCalledWith(originalEvent)
  })

  it('onRowClick opens the built-in detail dialog with the clicked row by default', () => {
    const { result } = mountComposable(makeStore(), baseOptions())
    const entity = makeEntity()

    result.onRowClick({ originalEvent: new Event('click'), data: entity, index: 0 })

    expect(result.detailDialogVisible.value).toBe(true)
    expect(result.detailTarget.value).toEqual(entity)
  })

  // onShowDetail is the one documented escape hatch: a feature whose "open
  // this row" doesn't mean "open the generic ResourceDetailDialog". Reusing
  // it here also doubles as an integration check of useRowOpenGuard. Real
  // OpenVue fires both @row-click and @row-select for one interaction (see
  // useRowOpenGuard's own spec for the guard's suppression logic in
  // isolation), and the default detail-dialog path is idempotent so can't
  // observe a double call the way a spy can.
  it('onShowDetail overrides the default dialog, and a same-tick duplicate call is still guarded', () => {
    const onShowDetail = vi.fn<(entity: Entity) => void>()
    const { result } = mountComposable(makeStore(), baseOptions({ onShowDetail }))
    const entity = makeEntity()

    result.onRowClick({ originalEvent: new Event('click'), data: entity, index: 0 })
    result.onRowClick({ originalEvent: new Event('click'), data: entity, index: 0 })

    expect(onShowDetail).toHaveBeenCalledTimes(1)
    expect(onShowDetail).toHaveBeenCalledWith(entity)
    expect(result.detailDialogVisible.value).toBe(false)
  })

  it('contextMenuItems places the feature-supplied editItem first, then Show details / Delete / Copy UUID', () => {
    const entity = makeEntity()
    const editItem: MenuItem = {
      label: 'Edit Sheet Metal',
      icon: 'mdi mdi-pencil',
      command: vi.fn<() => void>(),
    }
    const { result } = mountComposable(
      makeStore(),
      baseOptions({ editItem: () => editItem }),
      [DELETE_PERMISSION],
    )
    result.contextMenuTarget.value = entity

    const items = result.contextMenuItems.value

    expect(items).toHaveLength(7)
    expect(items[0]).toBe(editItem)
    expect(items[1]).toEqual({ separator: true })
    expect(items[2]).toMatchObject({ label: i18n.global.t('common.showDetails') })
    expect(items[3]).toEqual({ separator: true })
    expect(items[4]).toMatchObject({ label: i18n.global.t('common.delete'), disabled: false })
    expect(items[5]).toEqual({ separator: true })
    expect(items[6]).toMatchObject({ label: i18n.global.t('common.copyUuid') })
  })

  it('splices extraItems in right after Show details and before the Delete separator', () => {
    // Projects' "Show items" is one more per-row action beyond the generic
    // four. extraItems is the escape hatch for that, not a fork of the
    // shell/composable's fixed item order.
    const entity = makeEntity()
    const showItems: MenuItem = { label: 'Show items', command: vi.fn<() => void>() }
    const { result } = mountComposable(
      makeStore(),
      baseOptions({ extraItems: () => [showItems] }),
      [DELETE_PERMISSION],
    )
    result.contextMenuTarget.value = entity

    const items = result.contextMenuItems.value

    expect(items).toHaveLength(6)
    expect(items[0]).toMatchObject({ label: i18n.global.t('common.showDetails') })
    expect(items[1]).toBe(showItems)
    expect(items[2]).toEqual({ separator: true })
    expect(items[3]).toMatchObject({ label: i18n.global.t('common.delete') })
  })

  it('leaves out Show details with showDetailItem false, so extraItems open the menu', () => {
    const entity = makeEntity()
    const editItem: MenuItem = { label: 'Edit', command: vi.fn<() => void>() }
    const { result } = mountComposable(
      makeStore(),
      baseOptions({ showDetailItem: false, extraItems: () => [editItem] }),
      [DELETE_PERMISSION],
    )
    result.contextMenuTarget.value = entity

    const items = result.contextMenuItems.value

    expect(items).toHaveLength(5)
    expect(items[0]).toBe(editItem)
    expect(items[1]).toEqual({ separator: true })
    expect(items[2]).toMatchObject({ label: i18n.global.t('common.delete') })
    expect(items.some((item) => item.label === i18n.global.t('common.showDetails'))).toBe(false)
  })

  it('omits the edit entry entirely when editItem is not configured', () => {
    const { result } = mountComposable(makeStore(), baseOptions())
    result.contextMenuTarget.value = makeEntity()

    const items = result.contextMenuItems.value

    expect(items).toHaveLength(5)
    expect(items[0]).toMatchObject({ label: i18n.global.t('common.showDetails') })
  })

  it('disables the Delete menu item without deletePermission, and enables it with', () => {
    const entity = makeEntity()

    const without = mountComposable(makeStore(), baseOptions(), [])
    without.result.contextMenuTarget.value = entity
    expect(
      without.result.contextMenuItems.value.find((i) => i.label === i18n.global.t('common.delete')),
    ).toMatchObject({ disabled: true })

    const withPermission = mountComposable(makeStore(), baseOptions(), [DELETE_PERMISSION])
    withPermission.result.contextMenuTarget.value = entity
    expect(
      withPermission.result.contextMenuItems.value.find(
        (i) => i.label === i18n.global.t('common.delete'),
      ),
    ).toMatchObject({ disabled: false })
  })

  it('disables the Delete menu item for an entity deleteBlocked refuses, despite the permission', () => {
    const entity = makeEntity()
    const { result } = mountComposable(
      makeStore(),
      baseOptions({ deleteBlocked: (e) => e.id === entity.id }),
      [DELETE_PERMISSION],
    )
    result.contextMenuTarget.value = entity
    expect(
      result.contextMenuItems.value.find((i) => i.label === i18n.global.t('common.delete')),
    ).toMatchObject({ disabled: true })
  })

  it('gives a blocked Delete item the state reason, or the missing permission first, as title', () => {
    const entity = makeEntity()
    const reasonOptions = baseOptions({ deleteBlockedReason: () => 'It still has open orders.' })

    const blocked = mountComposable(makeStore(), reasonOptions, [DELETE_PERMISSION])
    blocked.result.contextMenuTarget.value = entity
    expect(
      blocked.result.contextMenuItems.value.find((i) => i.label === i18n.global.t('common.delete')),
    ).toMatchObject({ disabled: true, title: 'It still has open orders.' })

    const withoutPermission = mountComposable(makeStore(), reasonOptions, [])
    withoutPermission.result.contextMenuTarget.value = entity
    const item = withoutPermission.result.contextMenuItems.value.find(
      (i) => i.label === i18n.global.t('common.delete'),
    )
    expect(item?.disabled).toBe(true)
    expect(item?.title).toBe(
      i18n.global.t('common.permissionMissing', {
        permission: permissionLabel(i18n.global.t, DELETE_PERMISSION),
      }),
    )

    const free = mountComposable(makeStore(), baseOptions({ deleteBlockedReason: () => '' }), [
      DELETE_PERMISSION,
    ])
    free.result.contextMenuTarget.value = entity
    expect(
      free.result.contextMenuItems.value.find((i) => i.label === i18n.global.t('common.delete')),
    ).toMatchObject({ disabled: false, title: undefined })
  })

  it("the Copy UUID menu item copies the row's public_id", () => {
    const entity = makeEntity({ public_id: 'aaaa-bbbb' })
    const { result } = mountComposable(makeStore(), baseOptions())
    result.contextMenuTarget.value = entity

    invoke(result.contextMenuItems.value.find((i) => i.label === i18n.global.t('common.copyUuid')))

    expect(copyToClipboardMock).toHaveBeenCalledWith('aaaa-bbbb')
  })

  it('onDelete asks for confirmation with the resolved message, header and button props', () => {
    const entity = makeEntity({ name: 'Sheet Metal' })
    const { result } = mountComposable(makeStore(), baseOptions())

    result.onDelete(entity)

    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    const options = confirmRequireMock.mock.calls[0]![0]
    expect(options.message).toBe(
      i18n.global.t('settings.articleGroups.deleteConfirm', { name: 'Sheet Metal' }),
    )
    expect(options.header).toBe(i18n.global.t('common.delete'))
    expect(options.acceptProps).toEqual({ label: i18n.global.t('common.delete'), severity: 'danger' })
    expect(options.rejectProps).toEqual({
      label: i18n.global.t('common.cancel'),
      severity: 'secondary',
    })
  })

  it("resolves deleteConfirm with a caller-supplied interpolation object, for features whose placeholder isn't {name}", () => {
    // products/projects word their deleteConfirm string with a {number}
    // placeholder ('Delete product "{number}"?') rather than {name}; this
    // hatch lets onDelete resolve it correctly instead of leaving
    // "{number}" unresolved in the confirm dialog. Real key, real
    // placeholder mismatch, not the fixture prefix, which only has {name}.
    const entity = makeEntity({ name: 'PRD-042' })
    const { result } = mountComposable(
      makeStore(),
      baseOptions({
        i18nPrefix: 'resources.products',
        deleteConfirmParams: (e) => ({ number: e.name }),
      }),
    )

    result.onDelete(entity)

    const options = confirmRequireMock.mock.calls[0]![0]
    expect(options.message).toBe(i18n.global.t('resources.products.deleteConfirm', { number: 'PRD-042' }))
    expect(options.message).not.toContain('{number}')
  })

  it('a row with an edit version sends it with the delete', async () => {
    const store = makeStore()
    store.remove.mockResolvedValue(undefined)
    const entity = { ...makeEntity(), edit_version: 4 }
    const { result } = mountComposable(store, baseOptions())

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(store.remove).toHaveBeenCalledWith(entity.id, 4)
  })

  it('accepting the confirm removes the entity via the store and shows a success toast', async () => {
    const store = makeStore()
    store.remove.mockResolvedValue(undefined)
    const entity = makeEntity()
    const { result } = mountComposable(store, baseOptions())

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(store.remove).toHaveBeenCalledWith(entity.id)
    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'success',
      summary: entity.name,
      detail: i18n.global.t('common.delete'),
      life: 3000,
    })
  })

  it('shows the i18nPrefix-scoped unknown-error toast when the store rejects', async () => {
    const store = makeStore()
    store.remove.mockRejectedValue(new Error('boom'))
    const entity = makeEntity()
    const { result } = mountComposable(store, baseOptions())

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: i18n.global.t('settings.articleGroups.errors.unknown'),
      life: 5000,
    })
    expect(toastAddMock).toHaveBeenCalledTimes(1)
  })
})

// The archive/restore mode a master-data resource opts into via
// `options.archivable`. Wording, store calls and menu item all switch
// together, while the default (delete) path above stays untouched.
describe('useManagementResourceActions - archivable mode', () => {
  beforeEach(() => {
    confirmRequireMock.mockReset()
    toastAddMock.mockReset()
  })

  function archivableOptions(
    overrides: Partial<UseManagementResourceActionsOptions<Entity>> = {},
  ): UseManagementResourceActionsOptions<Entity> {
    return {
      ...baseOptions(),
      archivable: { isArchived: (entity) => !!entity.archived },
      ...overrides,
    }
  }

  it('contextMenuItems shows Archive for a live row and Restore for an archived one', () => {
    const { result } = mountComposable(makeArchiveStore(), archivableOptions(), [DELETE_PERMISSION])

    result.contextMenuTarget.value = makeEntity({ archived: false })
    expect(result.contextMenuItems.value.map((i) => i.label)).toContain(
      i18n.global.t('common.archive'),
    )

    result.contextMenuTarget.value = makeEntity({ archived: true })
    expect(result.contextMenuItems.value.map((i) => i.label)).toContain(
      i18n.global.t('common.restore'),
    )
  })

  it('onDelete asks for confirmation with the generic archive-confirm message and archive wording', () => {
    const { result } = mountComposable(makeArchiveStore(), archivableOptions())
    const entity = makeEntity({ name: 'Sheet Metal' })

    result.onDelete(entity)

    const options = confirmRequireMock.mock.calls[0]![0]
    expect(options.message).toBe(i18n.global.t('common.archiveConfirm', { name: 'Sheet Metal' }))
    expect(options.header).toBe(i18n.global.t('common.archive'))
    expect(options.acceptProps).toEqual({ label: i18n.global.t('common.archive'), severity: 'warn' })
  })

  it('accepting the confirm archives the entity via the store and shows a success toast', async () => {
    const store = makeArchiveStore()
    store.archive.mockResolvedValue(undefined)
    const entity = makeEntity()
    const { result } = mountComposable(store, archivableOptions())

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(store.archive).toHaveBeenCalledWith(entity.id)
    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'success',
      summary: entity.name,
      detail: i18n.global.t('common.archive'),
      life: 3000,
    })
  })

  it('onRestore restores the entity via the store with no confirm dialog, and shows a success toast', async () => {
    const store = makeArchiveStore()
    store.restore.mockResolvedValue(undefined)
    const entity = makeEntity({ archived: true })
    const { result } = mountComposable(store, archivableOptions())

    await result.onRestore(entity)

    expect(confirmRequireMock).not.toHaveBeenCalled()
    expect(store.restore).toHaveBeenCalledWith(entity.id)
    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'success',
      summary: entity.name,
      detail: i18n.global.t('common.restore'),
      life: 3000,
    })
  })

  it('onRestore surfaces a 409 conflict detail from the backend in the error toast', async () => {
    const store = makeArchiveStore()
    store.restore.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'A live supplier with this name already exists.' } },
    })
    const entity = makeEntity({ archived: true, name: 'Acme Corp' })
    const { result } = mountComposable(store, archivableOptions())

    await result.onRestore(entity)

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: 'Acme Corp',
      detail: 'A live supplier with this name already exists.',
      life: 5000,
    })
  })
})
