import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { Pinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useBucketsStore } from '../../stores/bucketsStore'
import BucketFilterSelect from '../BucketFilterSelect.vue'

import type { BucketResponse } from '../../types/bucketResponse'

function makeBucket(id: number, name: string): BucketResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-00000000000${id}`,
    created: '2026-01-01',
    name,
    color: '#ef4444',
    creator_id: 1,
  }
}

const BUCKETS = [makeBucket(1, 'Urgent'), makeBucket(2, 'Later')]

describe('BucketFilterSelect', () => {
  let pinia: Pinia
  let store: ReturnType<typeof useBucketsStore>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    store = useBucketsStore()
    store.items.bought_item_demand = [...BUCKETS]
    vi.spyOn(store, 'fetch').mockResolvedValue()
  })

  function mountSelect(props: { bucketIds?: number[]; includeUnbucketed?: boolean } = {}) {
    return mountWithApp(BucketFilterSelect, {
      pinia,
      attachTo: document.body,
      props: {
        resourceType: 'bought_item_demand',
        bucketIds: props.bucketIds ?? [],
        includeUnbucketed: props.includeUnbucketed ?? false,
      },
    })
  }

  it('lists the "Unbucketed" pseudo-option first, then the resource type buckets', () => {
    const wrapper = mountSelect()
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    expect(multiSelect.props('options')).toEqual([
      { value: null, label: 'Unbucketed', color: null },
      { value: 1, label: 'Urgent', color: '#ef4444' },
      { value: 2, label: 'Later', color: '#ef4444' },
    ])
    expect(store.fetch).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('fetches the buckets on mount when the store has none yet', () => {
    store.items.bought_item_demand = []
    const wrapper = mountSelect()

    expect(store.fetch).toHaveBeenCalledWith('bought_item_demand')
    wrapper.unmount()
  })

  it('derives the model from both props', () => {
    const wrapper = mountSelect({ bucketIds: [2], includeUnbucketed: true })
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    expect(multiSelect.props('modelValue')).toEqual([null, 2])
    wrapper.unmount()
  })

  it('picking the pseudo-option toggles includeUnbucketed and leaves bucketIds alone', async () => {
    const wrapper = mountSelect({ bucketIds: [1] })
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    multiSelect.vm.$emit('update:modelValue', [1, null])
    await flushPromises()

    expect(wrapper.emitted('update:includeUnbucketed')).toEqual([[true]])
    expect(wrapper.emitted('update:bucketIds')).toBeUndefined()
    wrapper.unmount()
  })

  it('picking buckets emits the real ids only', async () => {
    const wrapper = mountSelect({ includeUnbucketed: true })
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    multiSelect.vm.$emit('update:modelValue', [null, 1, 2])
    await flushPromises()

    expect(wrapper.emitted('update:bucketIds')).toEqual([[[1, 2]]])
    expect(wrapper.emitted('update:includeUnbucketed')).toBeUndefined()
    wrapper.unmount()
  })

  it('clearing resets both fields', async () => {
    const wrapper = mountSelect({ bucketIds: [1], includeUnbucketed: true })
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })

    multiSelect.vm.$emit('update:modelValue', [])
    await flushPromises()

    expect(wrapper.emitted('update:includeUnbucketed')).toEqual([[false]])
    expect(wrapper.emitted('update:bucketIds')).toEqual([[[]]])
    wrapper.unmount()
  })

  // Exercises OpenVue's own option handling with a `null` option value: the
  // pseudo-option must render as selected and toggle off through a real click.
  it('OpenVue marks the null-valued pseudo-option selected and toggles it on click', async () => {
    const wrapper = mountSelect({ includeUnbucketed: true })
    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    await multiSelect.vm.show()
    await flushPromises()

    const rows = document.body.querySelectorAll<HTMLElement>('li[role="option"]')
    expect(rows).toHaveLength(3)
    expect(rows[0]!.getAttribute('aria-selected')).toBe('true')
    expect(rows[0]!.textContent).toContain('Unbucketed')
    expect(rows[1]!.getAttribute('aria-selected')).toBe('false')

    rows[0]!.click()
    await flushPromises()

    expect(wrapper.emitted('update:includeUnbucketed')).toEqual([[false]])
    expect(wrapper.emitted('update:bucketIds')).toBeUndefined()
    wrapper.unmount()
  })
})
