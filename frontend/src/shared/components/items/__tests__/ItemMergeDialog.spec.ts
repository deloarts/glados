import { describe, it, expect, vi, afterEach } from 'vitest'
import { DOMWrapper, flushPromises, type VueWrapper } from '@vue/test-utils'
import { h } from 'vue'
import type { ToastMessageOptions } from 'openvue/toast'

import { mountWithApp } from '@/test-utils/mountWithApp'

import ItemMergeDialog from '../ItemMergeDialog.vue'
import type { ItemMergeOperations, ItemMergeTarget, MergeableItem } from '../ItemMergeDialog.vue'

// Same technique as UserFormDialog.spec.ts: replace the composable entirely
// so success/error toasts can be asserted without driving the real
// ToastService's DOM/timing.
const toastAddMock = vi.fn<(options: ToastMessageOptions) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

interface TestItem extends MergeableItem {
  id: number
  article_name: string
  code: string
}

function makeItem(overrides: Partial<TestItem> = {}): TestItem {
  return {
    id: 1,
    article_name: 'Hex Bolt',
    code: 'OC-1',
    ...overrides,
  }
}

function makeOperations(
  overrides: Partial<ItemMergeOperations<TestItem>> = {},
): ItemMergeOperations<TestItem> {
  return {
    merge: vi
      .fn<(sourceId: number, targetId: number) => Promise<TestItem>>()
      .mockResolvedValue(makeItem()),
    ...overrides,
  }
}

interface TargetSelectScope {
  targetItem: TestItem | null
  setTargetItem: (item: TestItem | null) => void
  excludeId?: number
  fetchOptions: (query: string) => Promise<TestItem[]>
  disabledReason: (item: TestItem) => string | null
}

// What the stand-in select last saw: its options and their disabled reasons.
let seenReasons: (string | null)[] = []

/**
 * A stand-in for a feature's own `<XItemSelect>` component: a single button
 * that loads the options through the slot's `fetchOptions`, as the real
 * select does, then hands the dialog the first one through `setTargetItem`,
 * on click rather than during render (mutating a prop function's backing
 * ref while rendering would fight Vue's reactivity).
 */
function pickTargetSlot() {
  return (scope: TargetSelectScope) =>
    h('button', {
      'data-testid': 'pick-target',
      onClick: async () => {
        const options = await scope.fetchOptions('')
        seenReasons = options.map((option) => scope.disabledReason(option))
        scope.setTargetItem(options[0] ?? null)
      },
    })
}

function allowed(item: TestItem, reactivates = false): ItemMergeTarget<TestItem> {
  return { item, refusal: null, reactivates }
}

const mounted: VueWrapper[] = []

const fetchTargetsMock =
  vi.fn<(sourceId: number, query: string) => Promise<ItemMergeTarget<TestItem>[]>>()

async function mountDialog(props: {
  item: TestItem | null
  operations: ItemMergeOperations<TestItem>
  target?: ItemMergeTarget<TestItem>
}) {
  fetchTargetsMock.mockResolvedValue([
    props.target ?? allowed(makeItem({ id: 2, article_name: 'Target Item' })),
  ])
  const wrapper = mountWithApp(ItemMergeDialog<TestItem>, {
    attachTo: document.body,
    props: {
      visible: true,
      item: props.item,
      operations: props.operations,
      i18nPrefix: 'boughtItems.catalogue.merge',
      itemLabel: (item: TestItem) => item.code,
      fetchTargets: fetchTargetsMock,
    },
    slots: {
      'target-select': pickTargetSlot(),
    },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

function confirmButton(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === 'Merge & Archive')!
}

function cancelButton(wrapper: VueWrapper) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === 'Cancel')!
}

// The Dialog teleports its content to document.body, outside the wrapper's
// own DOM subtree, so a plain `wrapper.find` (which searches from the
// wrapper's root element) cannot see it. Look it up from the document
// instead, the same way document.body.textContent is asserted elsewhere in
// this file.
async function pickTarget(): Promise<void> {
  const button = document.querySelector('[data-testid="pick-target"]')
  if (!button) throw new Error('pick-target button not found')
  await new DOMWrapper(button).trigger('click')
  await flushPromises()
}

describe('ItemMergeDialog', () => {
  afterEach(() => {
    toastAddMock.mockClear()
    fetchTargetsMock.mockReset()
    seenReasons = []
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the item name in the header and the source info panel', async () => {
    await mountDialog({
      item: makeItem({ article_name: 'Hex Bolt' }),
      operations: makeOperations(),
    })

    expect(document.body.textContent).toContain('Merge Item, Hex Bolt')
    expect(document.body.textContent).toContain('#1')
    expect(document.body.textContent).toContain('Hex Bolt')
  })

  it('shows just the title when no item is set', async () => {
    await mountDialog({ item: null, operations: makeOperations() })

    expect(document.body.textContent).toContain('Merge Item')
    expect(document.body.textContent).not.toContain('Merge Item,')
  })

  it('renders the item label formatter output under the source info', async () => {
    await mountDialog({ item: makeItem({ code: 'OC-99' }), operations: makeOperations() })

    expect(document.body.textContent).toContain('OC-99')
  })

  it('disables the merge button until a target item is picked', async () => {
    const wrapper = await mountDialog({ item: makeItem(), operations: makeOperations() })

    // Button has no declared `disabled` prop, it derives disabled-ness from
    // $attrs.disabled at render time, so this asserts the rendered DOM
    // attribute rather than a component prop.
    expect(confirmButton(wrapper).attributes('disabled')).toBeDefined()
  })

  it('enables the merge button once the target-select slot picks a target item', async () => {
    const wrapper = await mountDialog({ item: makeItem(), operations: makeOperations() })

    await pickTarget()

    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('asks the server for the targets of its item', async () => {
    await mountDialog({ item: makeItem({ id: 5 }), operations: makeOperations() })

    await pickTarget()

    expect(fetchTargetsMock).toHaveBeenCalledWith(5, '')
    expect(seenReasons).toEqual([null])
  })

  it('refuses a target the server calls not active, with the reason, and keeps the merge button disabled', async () => {
    const wrapper = await mountDialog({
      item: makeItem(),
      operations: makeOperations(),
      target: { item: makeItem({ id: 2 }), refusal: 'not_active', reactivates: false },
    })

    await pickTarget()

    expect(seenReasons).toEqual([expect.stringContaining('not active')])
    expect(confirmButton(wrapper).attributes('disabled')).toBeDefined()
    expect(document.querySelector('[data-testid="merge-target-refusal"]')?.textContent).toContain(
      'not active',
    )
  })

  it('refuses a target the server calls archived', async () => {
    const wrapper = await mountDialog({
      item: makeItem(),
      operations: makeOperations(),
      target: { item: makeItem({ id: 2 }), refusal: 'archived', reactivates: false },
    })

    await pickTarget()

    expect(confirmButton(wrapper).attributes('disabled')).toBeDefined()
    expect(document.querySelector('[data-testid="merge-target-refusal"]')?.textContent).toContain(
      'archived',
    )
  })

  it('accepts a target the server says the merge reactivates, and says so', async () => {
    const wrapper = await mountDialog({
      item: makeItem({ id: 1 }),
      operations: makeOperations(),
      target: allowed(makeItem({ id: 2 }), true),
    })

    await pickTarget()

    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined()
    expect(document.querySelector('[data-testid="merge-target-reactivated"]')).not.toBeNull()
  })

  it('merges, shows a success toast, and closes on confirm', async () => {
    const mergeMock = vi
      .fn<(sourceId: number, targetId: number) => Promise<TestItem>>()
      .mockResolvedValue(makeItem({ id: 2 }))
    const wrapper = await mountDialog({
      item: makeItem({ id: 1, article_name: 'Hex Bolt' }),
      operations: makeOperations({ merge: mergeMock }),
      target: allowed(makeItem({ id: 2, article_name: 'Target Item' })),
    })

    await pickTarget()
    await confirmButton(wrapper).trigger('click')
    await flushPromises()

    expect(mergeMock).toHaveBeenCalledWith(1, 2)
    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', summary: 'Hex Bolt' }),
    )
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
  })

  it('shows an error toast and stays open when the merge fails', async () => {
    const wrapper = await mountDialog({
      item: makeItem(),
      operations: makeOperations({
        merge: vi
          .fn<(sourceId: number, targetId: number) => Promise<TestItem>>()
          .mockRejectedValue(new Error('boom')),
      }),
    })

    await pickTarget()
    await confirmButton(wrapper).trigger('click')
    await flushPromises()

    expect(toastAddMock).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  it('closes without merging on cancel', async () => {
    const operations = makeOperations()
    const wrapper = await mountDialog({ item: makeItem(), operations })

    await cancelButton(wrapper).trigger('click')

    expect(operations.merge).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])
  })

  it('resets the picked target item when the dialog is closed', async () => {
    const wrapper = await mountDialog({ item: makeItem(), operations: makeOperations() })

    await pickTarget()
    expect(confirmButton(wrapper).attributes('disabled')).toBeUndefined()

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(confirmButton(wrapper).attributes('disabled')).toBeDefined()
  })
})
