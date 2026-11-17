import { describe, it, expect } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'


import LotRejectSourceDialog from '../LotRejectSourceDialog.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

// OpenVue's Dialog mounts its content (the mask + transition-stub) a tick
// after the component itself mounts; findComponent on the Textarea/Button
// inside it comes back empty without this flush.
async function mountDialog(props: { visible: boolean; lotNumber?: string; loading?: boolean }) {
  const wrapper = mountWithApp(LotRejectSourceDialog, {
    attachTo: document.body,
    props: { lotNumber: 'LOT-0001', ...props },
  })
  await flushPromises()
  return wrapper
}

function rejectButton(wrapper: VueWrapper) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === 'Reject')
}

function cancelButton(wrapper: VueWrapper) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === 'Cancel')
}

async function typeReason(wrapper: VueWrapper, value: string): Promise<void> {
  await wrapper.findComponent({ name: 'Textarea' }).setValue(value)
}

describe('LotRejectSourceDialog', () => {
  it('disables Reject while the reason is empty', async () => {
    const wrapper = await mountDialog({ visible: true })

    expect(rejectButton(wrapper)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  // trim() is what canSubmit checks: a reason of only spaces must not read
  // as "something was typed".
  it('disables Reject while the reason is whitespace-only', async () => {
    const wrapper = await mountDialog({ visible: true })

    await typeReason(wrapper, '   ')

    expect(rejectButton(wrapper)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables Reject once real text is entered', async () => {
    const wrapper = await mountDialog({ visible: true })

    await typeReason(wrapper, 'Wrong material dimension')

    expect(rejectButton(wrapper)!.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('emits confirm with the trimmed reason', async () => {
    const wrapper = await mountDialog({ visible: true })

    await typeReason(wrapper, '  Wrong material dimension  ')
    await rejectButton(wrapper)!.trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([['Wrong material dimension']])

    wrapper.unmount()
  })

  // The dialog is reused across rows/lots rather than remounted, so a
  // leftover reason from a previous rejection must not leak into the next
  // one. The reset hangs off the visible false -> true transition, the
  // same convention SourceItemDemandCreateDialog's own form reset uses.
  it('resets the textarea when visible flips from false to true', async () => {
    const wrapper = await mountDialog({ visible: false })

    await wrapper.setProps({ visible: true })
    await flushPromises()
    await typeReason(wrapper, 'Wrong material dimension')
    expect(wrapper.findComponent({ name: 'Textarea' }).props('modelValue')).toBe(
      'Wrong material dimension',
    )

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Textarea' }).props('modelValue')).toBe('')

    wrapper.unmount()
  })

  it('cancel emits update:visible false without emitting confirm', async () => {
    const wrapper = await mountDialog({ visible: true })

    await cancelButton(wrapper)!.trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(wrapper.emitted('confirm')).toBeUndefined()

    wrapper.unmount()
  })

  it('disables Reject while loading, even with a valid reason', async () => {
    const wrapper = await mountDialog({ visible: true, loading: true })

    await typeReason(wrapper, 'Wrong material dimension')

    expect(rejectButton(wrapper)!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })
})
