import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'

import PermissionChecklist from '../PermissionChecklist.vue'

async function mountChecklist(
  props: { permissions?: string[]; inherited?: Map<string, string[]>; disabled?: boolean } = {},
) {
  const wrapper = mountWithApp(PermissionChecklist, {
    attachTo: document.body,
    props: { idPrefix: 'perm', labelledby: 'caption', permissions: [], ...props },
  })
  await flushPromises()
  return wrapper
}

function checkbox(perm: string): HTMLInputElement | null {
  return document.querySelector(`input[id="perm-${perm}"]`)
}

describe('PermissionChecklist', () => {
  it('offers every assignable permission exactly once, under an area heading', async () => {
    const wrapper = await mountChecklist()

    const offered = Array.from(document.querySelectorAll<HTMLInputElement>('input[id^="perm-"]'))
      .map((input) => input.id.replace('perm-', ''))
      .sort()
    const assignable = Permission.ALL.filter((p) => p !== Permission.CONNECT_TERMINALS).sort()
    expect(offered).toEqual(assignable)
    expect(checkbox(Permission.CONNECT_TERMINALS)).toBeNull()
    expect(wrapper.findAll('h3').map((h) => h.text())).toContain('Printing')

    wrapper.unmount()
  })

  it('describes each permission to screen readers with what it allows', async () => {
    const wrapper = await mountChecklist()

    const input = checkbox(Permission.WRITE_ARTICLE_GROUPS)!
    const description = document.getElementById(input.getAttribute('aria-describedby')!)
    expect(description?.textContent).toBe(
      'Create, update, archive and restore article groups and product families.',
    )

    wrapper.unmount()
  })

  it('names the granting groups after the description of an inherited permission', async () => {
    const wrapper = await mountChecklist({
      inherited: new Map([[Permission.WRITE_ORDERS, ['Purchasing']]]),
    })

    const input = checkbox(Permission.WRITE_ORDERS)!
    expect(input.disabled).toBe(true)
    expect(input.checked).toBe(true)
    const description = document.getElementById(input.getAttribute('aria-describedby')!)
    expect(description?.textContent).toContain('Create orders and update draft or requested orders.')
    expect(description?.textContent).toContain('Purchasing')

    wrapper.unmount()
  })

  it('toggles a direct grant and disables every box when locked', async () => {
    const wrapper = await mountChecklist()

    checkbox(Permission.USE_PDM_ADDIN)!.click()
    await flushPromises()
    expect(wrapper.emitted('update:permissions')?.at(-1)).toEqual([[Permission.USE_PDM_ADDIN]])

    await wrapper.setProps({ disabled: true })
    expect(checkbox(Permission.USE_PDM_ADDIN)!.disabled).toBe(true)

    wrapper.unmount()
  })
})
