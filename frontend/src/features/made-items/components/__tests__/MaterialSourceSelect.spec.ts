import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

// Generic fallback for every nested lookup this component's children make on
// mount (SourceItemSelect/BoughtItemSelect/MadeItemSelect's own searches),
// same pattern as MadeItemCreateForm.spec.ts's own mock of the nested
// MaterialSourceSelect.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>(),
  },
}))

import MaterialSourceSelect from '../MaterialSourceSelect.vue'

import type { MaterialSource, MaterialSourceFieldLocks } from '../../types/materialSource'

function makeModel(overrides: Partial<MaterialSource> = {}): MaterialSource {
  return { bought_item_id: null, source_item_id: null, made_item_id: null, ...overrides }
}

async function mountSelect(modelValue: MaterialSource, lockedFields?: MaterialSourceFieldLocks) {
  const wrapper = mountWithApp(MaterialSourceSelect, {
    props: { modelValue, ...(lockedFields ? { lockedFields } : {}) },
    global: { directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return wrapper
}

// `optionDisabled` is passed to the real SelectButton as a function prop.
// Calling it directly with a candidate option is far more robust than
// simulating a real click on a genuinely-disabled native <button> (whose
// mouse events browsers suppress in the first place, which is why this
// component's own #option slot shows its reason through a plain `title`).
function optionDisabled(wrapper: Awaited<ReturnType<typeof mountSelect>>, value: string): boolean {
  const fn = wrapper.findComponent({ name: 'SelectButton' }).props('optionDisabled') as (opt: {
    value: string
  }) => boolean
  return fn({ value })
}

describe('MaterialSourceSelect', () => {
  it('leaves every kind option enabled when nothing is locked (default props)', async () => {
    const wrapper = await mountSelect(makeModel())

    expect(optionDisabled(wrapper, 'source')).toBe(false)
    expect(optionDisabled(wrapper, 'bought')).toBe(false)
  })

  it('disables a flagged field\'s own item Select even while it is still unset, without touching the toggle', async () => {
    const wrapper = await mountSelect(makeModel(), { bought: false, source: true })

    // 'source' is the default active tab, so its Select is the one on
    // screen. Flagged means "any change requires a revision", including
    // setting it from null, so it's disabled unconditionally.
    const sourceSelect = wrapper.findComponent({ name: 'SourceItemSelect' })
    expect(sourceSelect.props('disabled')).toBe(true)
    expect(sourceSelect.attributes('data-pd-tooltip')).toBe('true')

    // Nothing is actually set yet, so no kind option is blocked; a fresh
    // pick in either kind is exactly what the policy still allows.
    expect(optionDisabled(wrapper, 'source')).toBe(false)
    expect(optionDisabled(wrapper, 'bought')).toBe(false)
  })

  it('blocks switching away from a set, flagged source item, but leaves that kind itself reachable', async () => {
    const wrapper = await mountSelect(makeModel({ source_item_id: 42 }), {
      bought: false,
      source: true,
    })

    // Switching to 'bought' would clear the flagged, currently-set
    // source_item_id, which is blocked. Re-selecting 'source' itself would
    // not clear anything, so it stays selectable.
    expect(optionDisabled(wrapper, 'bought')).toBe(true)
    expect(optionDisabled(wrapper, 'source')).toBe(false)

    // Its own item Select is still disabled by rule 1 regardless.
    expect(wrapper.findComponent({ name: 'SourceItemSelect' }).props('disabled')).toBe(true)

    // The blocked option's rendered label carries a native `title` (a real
    // disabled <button> never fires the mouseenter v-tooltip needs), the
    // reachable one doesn't.
    const labels = wrapper.findAll('[data-testid="material-source-option-label"]')
    const boughtLabel = labels.find((l) => l.text() === i18n.global.t('sourceItems.select.kind.bought'))
    const sourceLabel = labels.find((l) => l.text() === i18n.global.t('sourceItems.select.kind.source'))
    expect(boughtLabel?.attributes('title')).toBe(i18n.global.t('sourceItems.select.fieldLock.source'))
    expect(sourceLabel?.attributes('title')).toBeUndefined()
  })

  it('blocks switching away from a set, flagged bought item, but leaves that kind itself reachable', async () => {
    const wrapper = await mountSelect(makeModel({ bought_item_id: 7 }), {
      bought: true,
      source: false,
    })

    expect(optionDisabled(wrapper, 'source')).toBe(true)
    expect(optionDisabled(wrapper, 'bought')).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).props('disabled')).toBe(true)
  })

  it('leaves the toggle fully open when the currently-set field is not the flagged one', async () => {
    // bought_item_id is set but unflagged; source_item_id is flagged but
    // currently null, so nothing would actually be cleared by switching,
    // and both options stay reachable. The still-unflagged, currently-active
    // Select also stays fully usable (the XOR case).
    const wrapper = await mountSelect(makeModel({ bought_item_id: 7 }), {
      bought: false,
      source: true,
    })

    expect(optionDisabled(wrapper, 'bought')).toBe(false)
    expect(optionDisabled(wrapper, 'source')).toBe(false)
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).props('disabled')).toBe(false)
  })

  it('disables the newly active Select immediately after switching to a flagged, still-empty kind', async () => {
    const wrapper = await mountSelect(makeModel(), { bought: true, source: false })

    // Nothing set yet, so switching is allowed...
    expect(optionDisabled(wrapper, 'bought')).toBe(false)
    await wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'bought')
    await flushPromises()

    // ...but rule 1 still locks the item Select the instant that kind is
    // active, since setting a flagged field from null is itself a change.
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).props('disabled')).toBe(true)
  })
})
