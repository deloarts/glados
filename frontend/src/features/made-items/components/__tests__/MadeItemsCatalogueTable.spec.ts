import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'

const pushMock = vi.fn<(to: string) => void>()

// Partial mock: only useRouter's `push` needs to be observable here. The
// rest of vue-router (RouterLink et al, used by the item detail dialogs
// mounted alongside this table) must still be the real module.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
      // The PdmThumbnail column (rendered only while hostStore.pdmEnabled is
      // on) fetches this as a blob. A 404 keeps it a harmless placeholder
      // rather than handing URL.createObjectURL a plain object dressed up
      // as a Blob.
      if (url.includes('/thumbnail')) {
        return Promise.reject({ isAxiosError: true, response: { status: 404 } })
      }
      return Promise.resolve({
        data: {
          items: [
            {
              id: 1,
              part_number: 'PN-1',
              status: 'active',
              archived: false,
              created: '2026-01-01',
              changed: '2026-02-01',
              revision: 'A',
              revision_date: null,
              revision_note: null,
              article_name: 'Article',
              article_groups: [
                {
                  id: 1,
                  created: '2026-01-01',
                  changed: '2026-01-01',
                  archived: false,
                  name: 'Group',
                  label_color: '#b0e0e6',
                  description: '',
                  creator_id: 1,
                  creator: {
                    id: 1,
                    username: 'creator',
                    full_name: 'Creator',
                    email: 'creator@example.com',
                    has_avatar: false,
                  },
                },
              ],
              data_source: 'WEB',
              material: '1.0037',
              mass: 100,
              base_size: null,
              note: 'Note',
              weblink: 'http://example.com',
              successor_item_id: null,
              creator_id: 1,
              creator: {
                id: 1,
                username: 'creator',
                full_name: 'Creator',
                email: 'creator@example.com',
                has_avatar: false,
              },
              source_item_id: null,
              source_item: null,
              processes: [],
            },
          ],
          total: 1,
          limit: 25,
          skip: 0,
        },
      })
    }),
  },
}))

import api from '@/core/api'
import MadeItemsCatalogueTable from '../MadeItemsCatalogueTable.vue'
import {
  MADE_ITEMS_CATALOGUE_COLUMNS,
  useMadeItemsCatalogueColumnsStore,
} from '../../stores/madeItemsCatalogueColumnsStore'
import { useMadeItemsCatalogueEditStore } from '../../stores/madeItemsCatalogueEditStore'
import { useMadeItemsShowAllRevisionsStore } from '../../stores/madeItemsCatalogueViewStore'
import { useMadeItemsStore } from '../../stores/madeItemsStore'
import { useHostStore } from '@/core/host/stores/hostStore'

describe('MadeItemsCatalogueTable', () => {
  beforeEach(() => {
    pushMock.mockClear()
  })

  it('mounts with all columns and date-range filters without recursive update errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
  })

  it('renders every selectable column', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    // The stores are already instantiated by the mounted component, so these
    // return those instances rather than running their setups outside a
    // component.
    const columnsStore = useMadeItemsCatalogueColumnsStore()
    columnsStore.setVisibleFields(MADE_ITEMS_CATALOGUE_COLUMNS.map((column) => column.field))
    // The image column only renders when the host has file storage on.
    useHostStore().storageEnabled = true

    await flushPromises()

    const headers = wrapper.findAll('th').map((th) => th.text())
    for (const column of MADE_ITEMS_CATALOGUE_COLUMNS) {
      expect(headers).toContain(i18n.global.t(column.headerKey))
    }
  })

  it('shows the agreed default columns, in order', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    useHostStore().storageEnabled = true
    await flushPromises()

    // Only the title row: filterDisplay="row" adds a second row of <th>
    // holding the filter inputs.
    const headers = wrapper
      .find('thead tr')
      .findAll('th')
      .map((th) => th.text())
    expect(headers).toEqual([
      '#',
      'ID',
      'State',
      'Image',
      'Part Number',
      'Revision',
      'Article Name',
      'Material',
      'Mass',
      'Process Routing',
      'Files',
      'Base Size',
      'Source',
      'Groups',
      'Note',
      // The trailing spacer column that soaks up the remaining width.
      '',
    ])
  })

  it('hides the image and files columns while file storage is off', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    useMadeItemsCatalogueColumnsStore().setVisibleFields(['id', 'image', 'files'])
    useHostStore().storageEnabled = false

    await flushPromises()

    const headers = wrapper.findAll('th').map((th) => th.text())
    expect(headers).not.toContain(i18n.global.t('madeItems.catalogue.columns.image'))
    expect(headers).not.toContain(i18n.global.t('madeItems.catalogue.columns.files'))
  })

  // Export is not implemented, so its context-menu entry is disabled and
  // inert rather than a stub that would imply a working feature.
  it('offers no Export entry in the context menu, since no catalogue export exists', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    expect(contextMenu.exists()).toBe(true)

    const items = contextMenu.props('model') as Array<{ icon?: string }>
    expect(items.map((item) => item.icon)).not.toContain('mdi mdi-export')
  })

  // The context menu offers Archive for a live row and Restore for an
  // already-archived one. The fixture row above is not archived, so only
  // Archive should be offered.
  it('offers Archive (not Restore) for a live row in the context menu', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tbody tr')
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    const items = contextMenu.props('model') as Array<{ label?: string }>

    expect(items.some((item) => item.label === i18n.global.t('common.archive'))).toBe(true)
    expect(items.some((item) => item.label === i18n.global.t('common.restore'))).toBe(false)
  })

  // selectionMode="single" makes every row keyboard-reachable
  // and gives Enter the same effect as a click, via the shared
  // useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable outside edit mode', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')
  })

  it('navigates to the detail page on @row-select the same way @row-click does', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    // The real fetched row, not a hand-typed partial. MadeItemDetailDialog
    // reads several fields (article_groups, etc.) off it synchronously.
    const item = useMadeItemsStore().items[0]
    expect(item).toBeDefined()

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', {
      data: item,
      index: 0,
      originalEvent: new Event('keydown'),
    })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith(`/catalogue/made-items/${item!.id}`)
    expect(wrapper.findComponent({ name: 'MadeItemDetailDialog' }).props('visible')).toBe(false)
  })

  // Outside edit mode `selection` is deliberately left unbound: bound to
  // selectionMode="single" (via `rowSelection`), OpenVue's own tabindex
  // computation (BodyRow.vue #rowTabindex) would return -1 for every row,
  // permanently, once a row was opened, because it only special-cases the
  // nothing-selected state. Unbound, it stays null and the table stays
  // keyboard-reachable after the first open.
  // A plain row click navigates to the detail page instead of opening the
  // dialog; the tabindex coverage above sits alongside it.
  it('navigates to the detail page on row click', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/catalogue/made-items/1')
    expect(wrapper.findComponent({ name: 'MadeItemDetailDialog' }).props('visible')).toBe(false)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')
  })

  it('stays keyboard-reachable after opening a row via Enter, outside edit mode', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('keydown', { code: 'Enter' })
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/catalogue/made-items/1')
    expect(wrapper.findComponent({ name: 'MadeItemDetailDialog' }).props('visible')).toBe(false)
    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')
  })

  // The bulk-edit checkbox column (editStore.editMode) binds this same
  // DataTable's `selection`/`selectionMode` to an *array* for batch
  // actions. The new single-row-open wiring must not fight it (the
  // "do not clobber existing nested selection" guard, verified empirically).
  // The checkbox's own toggle is safe regardless (OpenVue always builds an
  // array there); the real risk is a plain row click, which is what would
  // route through selectionMode="single"'s object-shaped `update:selection`
  // if that mode were left active during edit mode, so that's what this
  // asserts survives.
  it('does not clobber the bulk-edit selection array when a row is checked, then clicked, in edit mode', async () => {
    // (The row-click open handler must not fire on top of the checkbox
    // selection either; "does not open the detail dialog..." below covers
    // that.)
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })
    await flushPromises()

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    await flushPromises()

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })

    // A plain click elsewhere on the (already checkbox-selected) row must
    // not touch the array. It also does not open the detail dialog while
    // in edit mode (row-open is gated on editStore.editMode; see "does not
    // open the detail dialog..." below); this test only covers the
    // selection side. (Not selected via the `data-p-selectable-row`
    // attribute used elsewhere in this file: in edit mode selectionMode is
    // deliberately undefined, so that attribute is absent here too.)
    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(editStore.selectedItems[0]).toMatchObject({ id: 1 })
  })

  // The bulk-select checkbox click also bubbles into onRowClick, which would
  // open the detail dialog on top of the edit panel (see the "does not
  // clobber" test above for selection). onRowClick/onRowSelect are gated on
  // editStore.editMode so neither the checkbox nor a plain row click can
  // open the dialog while bulk edit is active, and selection still works.
  it('does not open the detail dialog when the bulk-select checkbox or a plain row click fires in edit mode', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: { plugins: [ConfirmationService] },
    })
    await flushPromises()

    const editStore = useMadeItemsCatalogueEditStore()
    editStore.editMode = true
    await flushPromises()

    const dialog = () => wrapper.findComponent({ name: 'MadeItemDetailDialog' })
    expect(dialog().props('visible')).toBe(false)

    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(editStore.selectedItems).toHaveLength(1)
    expect(dialog().props('visible')).toBe(false)

    const row = wrapper.find('tbody tr')
    await row.trigger('click')
    await flushPromises()

    expect(dialog().props('visible')).toBe(false)
    expect(editStore.selectedItems).toHaveLength(1)
  })

  // The dialog stays mounted in the table purely so the context menu's
  // "Edit" entry can still open it, in edit mode. Unlike a plain row
  // click/select, this must not navigate anywhere.
  it('context-menu edit still opens the dialog in edit mode', async () => {
    const wrapper = mountWithApp(MadeItemsCatalogueTable, {
      global: {
        plugins: [ConfirmationService],
      },
    })

    await flushPromises()

    const row = wrapper.find('tbody tr')
    expect(row.exists()).toBe(true)
    await row.trigger('contextmenu')
    await flushPromises()

    const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
    expect(contextMenu.exists()).toBe(true)

    const items = contextMenu.props('model') as Array<{
      label?: string
      command?: () => void
    }>
    const editEntry = items.find(
      (item) => item.label === i18n.global.t('madeItems.catalogue.controls.edit'),
    )
    expect(editEntry).toBeDefined()

    editEntry?.command?.()
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'MadeItemDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('editOnOpen')).toBe(true)
    expect(pushMock).not.toHaveBeenCalled()
  })

  // The "Show all revisions" toggle (default off) and the inverse `latest_only`
  // request param it drives.
  describe('show all revisions', () => {
    it('sends latest_only: true by default', async () => {
      mountWithApp(MadeItemsCatalogueTable, {
        global: {
          plugins: [ConfirmationService],
        },
      })
      await flushPromises()

      expect(vi.mocked(api.get)).toHaveBeenCalledWith(
        '/made-items/',
        expect.objectContaining({ params: expect.objectContaining({ latest_only: true }) }),
      )
    })

    it('toggling the store flag refetches with latest_only: false', async () => {
      const pinia = createPinia()
      mountWithApp(MadeItemsCatalogueTable, {
        pinia,
        global: {
          plugins: [ConfirmationService],
        },
      })
      await flushPromises()

      vi.mocked(api.get).mockClear()
      useMadeItemsShowAllRevisionsStore(pinia).toggleShowAllRevisions()
      await flushPromises()

      expect(vi.mocked(api.get)).toHaveBeenCalledWith(
        '/made-items/',
        expect.objectContaining({ params: expect.objectContaining({ latest_only: false }) }),
      )
    })
  })

  // The context menu's "New revision" entry, right after Copy:
  // enable/disable matrix.
  describe('context menu: New revision', () => {
    async function openContextMenu(pinia: ReturnType<typeof createPinia>) {
      const wrapper = mountWithApp(MadeItemsCatalogueTable, {
        pinia,
        global: {
          plugins: [ConfirmationService],
        },
      })
      await flushPromises()

      const row = wrapper.find('tbody tr')
      await row.trigger('contextmenu')
      await flushPromises()

      const contextMenu = wrapper.findComponent({ name: 'ContextMenu' })
      return {
        wrapper,
        items: contextMenu.props('model') as Array<{
          label?: string
          disabled?: boolean
          title?: string
          command?: () => void
        }>,
      }
    }

    it('shows New revision right after Copy, both gated the same way by write permission for a WEB item', async () => {
      const pinia = createPinia()
      const { items } = await openContextMenu(pinia)

      const copyIndex = items.findIndex(
        (item) => item.label === i18n.global.t('madeItems.catalogue.controls.copy'),
      )
      const revisionIndex = items.findIndex(
        (item) => item.label === i18n.global.t('madeItems.catalogue.contextMenu.newRevision'),
      )
      expect(copyIndex).toBeGreaterThanOrEqual(0)
      expect(revisionIndex).toBe(copyIndex + 1)
      // No usePermissions mock in this file, so WRITE_MADE_ITEMS is false for
      // every test here (no signed-in user), so a WEB item's New revision
      // is gated identically to Copy: both disabled, and both name the
      // missing permission.
      expect(items[revisionIndex]!.disabled).toBe(items[copyIndex]!.disabled)
      expect(items[revisionIndex]!.title).toBe(items[copyIndex]!.title)
      expect(items[copyIndex]!.title).toBe('This needs the permission Write Made Items.')
    })

    it('disables New revision with a managed-by-PDM title for a CAD item', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({
        data: {
          items: [{ id: 1, part_number: 'PN-1', status: 'active', revision: 'A', article_name: 'A', data_source: 'CAD', article_groups: [], processes: [] }],
          total: 1,
          limit: 25,
          skip: 0,
        },
      })
      const pinia = createPinia()
      const { items } = await openContextMenu(pinia)

      const revisionEntry = items.find(
        (item) => item.label === i18n.global.t('madeItems.catalogue.contextMenu.newRevision'),
      )
      const copyEntry = items.find(
        (item) => item.label === i18n.global.t('madeItems.catalogue.controls.copy'),
      )
      expect(revisionEntry?.disabled).toBe(true)
      expect(revisionEntry?.title).toBe(
        i18n.global.t('madeItems.catalogue.contextMenu.newRevisionManagedByPdm'),
      )
      // CAD-ness is specific to New revision. Copy is unaffected by it and
      // stays gated purely by write permission, naming it.
      expect(copyEntry?.title).toBe('This needs the permission Write Made Items.')
    })

    it('hides both New revision and Copy once web_creation_allowed is false', async () => {
      const pinia = createPinia()
      const { items } = await openContextMenu(pinia)
      useHostStore(pinia).madeItemPartNumbers.web_creation_allowed = false
      await flushPromises()

      // Re-open to read the recomputed menu model.
      const menuAfter = (
        await openContextMenu(pinia)
      ).items

      expect(
        items.some((item) => item.label === i18n.global.t('madeItems.catalogue.controls.copy')),
      ).toBe(true)
      expect(
        menuAfter.some(
          (item) => item.label === i18n.global.t('madeItems.catalogue.controls.copy'),
        ),
      ).toBe(false)
      expect(
        menuAfter.some(
          (item) => item.label === i18n.global.t('madeItems.catalogue.contextMenu.newRevision'),
        ),
      ).toBe(false)
    })
  })

})
