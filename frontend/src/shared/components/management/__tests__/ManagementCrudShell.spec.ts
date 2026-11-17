import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import type { MenuItem } from 'openvue/menuitem'

import ManagementCrudShell from '../ManagementCrudShell.vue'
import type { ManagementCrudShellConfig, ManagementCrudShellStore } from '../ManagementCrudShell.vue'

const CREATE_PERMISSION = 'write:widgets'

function makeStore(overrides: Partial<ManagementCrudShellStore> = {}): ManagementCrudShellStore {
  return reactive({
    hasActiveFilters: false,
    showActions: false,
    sortBy: null,
    groupBy: null,
    triggerRefresh: vi.fn<() => void>(),
    toggleShowActions: vi.fn<() => void>(),
    clearSort: vi.fn<() => void>(),
    clearGroupBy: vi.fn<() => void>(),
    clearAll: vi.fn<() => void>(),
    toggleShowArchived: vi.fn<() => void>(),
    ...overrides,
  })
}

function makeConfig(overrides: Partial<ManagementCrudShellConfig> = {}): ManagementCrudShellConfig {
  return {
    store: makeStore(),
    idPrefix: 'widgets',
    createLabel: 'Create Widget',
    createPermission: CREATE_PERMISSION,
    sortByItems: [{ label: 'Name asc', command: vi.fn<() => void>() }] as MenuItem[],
    ...overrides,
  }
}

function mountShell(
  config: ManagementCrudShellConfig,
  permissions: string[] = [CREATE_PERMISSION],
  search = '',
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(ManagementCrudShell, {
    pinia,
    props: { config, search },
    slots: { default: '<div class="table-stub">Table</div>' },
  })
}

describe('ManagementCrudShell', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the given default slot content and the create button, but no ConfirmDialog of its own', () => {
    const config = makeConfig()
    const wrapper = mountShell(config)

    expect(wrapper.findComponent({ name: 'ConfirmDialog' }).exists()).toBe(false)
    expect(wrapper.find('.table-stub').text()).toBe('Table')
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')
    expect(button).toBeDefined()

    wrapper.unmount()
  })

  it('disables the create button without createPermission, and enables it with', () => {
    const withoutPermission = mountShell(makeConfig(), [])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')!
    expect(disabledButton.attributes('disabled')).toBeDefined()
    withoutPermission.unmount()

    const withPermission = mountShell(makeConfig(), [CREATE_PERMISSION])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')!
    expect(enabledButton.attributes('disabled')).toBeUndefined()
    withPermission.unmount()
  })

  it('names the missing create permission in a tooltip on the disabled create button', () => {
    const withoutPermission = mountShell(makeConfig({ createPermission: 'write:article_groups' }), [])
    const disabledButton = withoutPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')!
    expect(tooltipOf(disabledButton)).toBe('This needs the permission Write Article Groups.')
    withoutPermission.unmount()

    const withPermission = mountShell(makeConfig(), [CREATE_PERMISSION])
    const enabledButton = withPermission
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')!
    expect(tooltipOf(enabledButton)).toBeUndefined()
    withPermission.unmount()
  })

  it("renders the extra-controls slot next to the create button, for a feature that needs one more control-bar button", () => {
    const wrapper = mountShell(makeConfig())
    expect(wrapper.find('.extra-control-stub').exists()).toBe(false)
    wrapper.unmount()

    const withExtra = mountWithApp(ManagementCrudShell, {
      pinia: (() => {
        const pinia = createPinia()
        setActivePinia(pinia)
        useCurrentUserStore().user = userWithPermissions([CREATE_PERMISSION])
        return pinia
      })(),
      props: { config: makeConfig(), search: '' },
      slots: {
        default: '<div class="table-stub">Table</div>',
        'extra-controls': '<button class="extra-control-stub">Export</button>',
      },
    })
    expect(withExtra.find('.extra-control-stub').exists()).toBe(true)
    withExtra.unmount()
  })

  it('emits create when the create button is clicked', async () => {
    const wrapper = mountShell(makeConfig())
    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Create Widget')!

    await button.trigger('click')

    expect(wrapper.emitted('create')).toHaveLength(1)
    wrapper.unmount()
  })

  it("passes the config's idPrefix/sortByItems/groupByItems and the store's showActions/hasActiveFilters through to ViewsBar", () => {
    const store = makeStore({ showActions: true, hasActiveFilters: true, sortBy: 'name' })
    const groupByItems: MenuItem[] = [{ label: 'Country', command: vi.fn<() => void>() }]
    const config = makeConfig({ store, groupByItems })
    const wrapper = mountShell(config)

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('idPrefix')).toBe('widgets')
    expect(viewsBar.props('showActions')).toBe(true)
    expect(viewsBar.props('sortByItems')).toEqual(config.sortByItems)
    expect(viewsBar.props('sortByActive')).toBe(true)
    expect(viewsBar.props('groupByItems')).toEqual(groupByItems)
    expect(viewsBar.props('hasActiveFilters')).toBe(true)

    wrapper.unmount()
  })

  it("forwards the config's searchPlaceholder to ViewsBar, and leaves it undefined (ViewsBar's own default) when omitted", () => {
    // Some features (printers, print-labels, print-dockets) word their
    // search placeholder more specifically than the generic default. This
    // only proves the pass-through, not ViewsBar's own fallback behaviour
    // (that's ViewsBar's spec's job).
    const withPlaceholder = mountShell(makeConfig({ searchPlaceholder: 'Search printers…' }))
    expect(
      withPlaceholder.findComponent({ name: 'ViewsBar' }).props('searchPlaceholder'),
    ).toBe('Search printers…')
    withPlaceholder.unmount()

    const withoutPlaceholder = mountShell(makeConfig())
    expect(
      withoutPlaceholder.findComponent({ name: 'ViewsBar' }).props('searchPlaceholder'),
    ).toBeUndefined()
    withoutPlaceholder.unmount()
  })

  it('defaults showCreate to true (existing behaviour), and hides the create button entirely when false (print-labels/print-dockets)', () => {
    const withDefault = mountShell(makeConfig())
    expect(
      withDefault
        .findAllComponents({ name: 'Button' })
        .some((b) => b.props('label') === 'Create Widget'),
    ).toBe(true)
    withDefault.unmount()

    const withoutCreate = mountShell(makeConfig({ showCreate: false }))
    expect(
      withoutCreate
        .findAllComponents({ name: 'Button' })
        .some((b) => b.props('label') === 'Create Widget'),
    ).toBe(false)
    // The extra-controls slot still renders in Create's place, as covered by the
    // "renders the extra-controls slot" test above.
    withoutCreate.unmount()
  })

  it('does not throw clicking clear-sort-by when the store has no sortBy/clearSort (a resource with no sort-by menu)', () => {
    const noSortStore = makeStore({ sortBy: undefined, clearSort: undefined })
    const wrapper = mountShell(makeConfig({ store: noSortStore, sortByItems: undefined }))

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('sortByItems')).toEqual([])
    expect(viewsBar.props('sortByActive')).toBe(false)
    expect(() => viewsBar.vm.$emit('clear-sort-by')).not.toThrow()

    wrapper.unmount()
  })

  it('leaves groupByItems/groupByActive at their ViewsBar defaults when the config omits grouping', () => {
    const wrapper = mountShell(makeConfig({ groupByItems: undefined }))

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    // ViewsBar's own `withDefaults` turns an unset groupByItems into `[]`,
    // which is what hides its Group By button (see ViewsBar.vue).
    expect(viewsBar.props('groupByItems')).toEqual([])
    expect(viewsBar.props('groupByActive')).toBe(false)

    wrapper.unmount()
  })

  it("passes the shell's own search model through to ViewsBar, and relays ViewsBar's update:search back out - the caller wires it to its store, not this config, so a nested prop write is never assigned through here", async () => {
    const wrapper = mountShell(makeConfig(), [CREATE_PERMISSION], 'sheet metal')

    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })
    expect(viewsBar.props('search')).toBe('sheet metal')

    await viewsBar.vm.$emit('update:search', 'stainless steel')

    expect(wrapper.emitted('update:search')).toEqual([['stainless steel']])
    wrapper.unmount()
  })

  it("relays ViewsBar's sync/toggle-show-actions/clear-sort-by/clear events to the store", () => {
    const store = makeStore()
    const wrapper = mountShell(makeConfig({ store }))
    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })

    viewsBar.vm.$emit('sync')
    viewsBar.vm.$emit('toggle-show-actions')
    viewsBar.vm.$emit('clear-sort-by')
    viewsBar.vm.$emit('clear')

    expect(store.triggerRefresh).toHaveBeenCalledTimes(1)
    expect(store.toggleShowActions).toHaveBeenCalledTimes(1)
    expect(store.clearSort).toHaveBeenCalledTimes(1)
    expect(store.clearAll).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it("passes the store's showArchived through to ViewsBar, and relays toggle-show-archived back to the store", () => {
    const archivableStore = makeStore({ showArchived: true })
    const wrapper = mountShell(makeConfig({ store: archivableStore }))
    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })

    expect(viewsBar.props('showArchived')).toBe(true)

    viewsBar.vm.$emit('toggle-show-archived')
    expect(archivableStore.toggleShowArchived).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('leaves showArchived undefined for a non-archivable resource, and does not throw toggling it', () => {
    const nonArchivableStore = makeStore({ showArchived: undefined, toggleShowArchived: undefined })
    const wrapper = mountShell(makeConfig({ store: nonArchivableStore }))
    const viewsBar = wrapper.findComponent({ name: 'ViewsBar' })

    expect(viewsBar.props('showArchived')).toBeUndefined()
    expect(() => viewsBar.vm.$emit('toggle-show-archived')).not.toThrow()

    wrapper.unmount()
  })

  it("relays ViewsBar's clear-group-by to the store when it has one, and does not throw when it doesn't", () => {
    const withGroupBy = makeStore()
    const wrapper = mountShell(makeConfig({ store: withGroupBy, groupByItems: [] }))
    wrapper.findComponent({ name: 'ViewsBar' }).vm.$emit('clear-group-by')
    expect(withGroupBy.clearGroupBy).toHaveBeenCalledTimes(1)
    wrapper.unmount()

    const withoutGroupBy = makeStore({ clearGroupBy: undefined })
    const wrapper2 = mountShell(makeConfig({ store: withoutGroupBy }))
    expect(() => wrapper2.findComponent({ name: 'ViewsBar' }).vm.$emit('clear-group-by')).not.toThrow()
    wrapper2.unmount()
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
