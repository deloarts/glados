import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { MeetingScopeParams } from '../types/meetingRequest'
import type { MeetingScopeSuggestionsResponse } from '../types/meetingResponse'

const getMeetingScopeSuggestions = vi.fn<(params: MeetingScopeParams) => Promise<MeetingScopeSuggestionsResponse>>()
vi.mock('../api/meetingsApi', () => ({
  getMeetingScopeSuggestions: (params: MeetingScopeParams) => getMeetingScopeSuggestions(params),
}))

import MeetingScopePopover from '../components/MeetingScopePopover.vue'

let wrapper: VueWrapper | null = null

function find(testId: string): HTMLElement | null {
  return document.body.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
}

async function openPopover(props: Partial<InstanceType<typeof MeetingScopePopover>['$props']> = {}) {
  wrapper = mountWithApp(MeetingScopePopover, {
    attachTo: document.body,
    props: { scope: 'Gripper', icon: null, owner: { project_id: 142 }, ...props },
  })
  // The popover anchors to the button that opened it, as the card's scope button does.
  const target = document.createElement('button')
  document.body.appendChild(target)
  const vm = wrapper.vm as unknown as { open: (event: Event) => void }
  target.addEventListener('click', (event) => vm.open(event))
  target.click()
  await flushPromises()
  return wrapper
}

async function typeScope(text: string): Promise<void> {
  const input = find('meeting-scope-input') as HTMLInputElement
  input.value = text
  input.dispatchEvent(new Event('input'))
  await vi.advanceTimersByTimeAsync(400)
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  getMeetingScopeSuggestions.mockResolvedValue({
    suggestions: [
      { scope: 'Vacuum gripper', icon: 'mechanics', count: 5 },
      { scope: 'Fence', icon: null, count: 2 },
    ],
    near_duplicate: null,
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.useRealTimers()
})

describe('MeetingScopePopover', () => {
  it('offers the scopes the owner uses, most used first', async () => {
    await openPopover()

    expect(getMeetingScopeSuggestions).toHaveBeenCalledWith({ project_id: 142, q: 'Gripper', limit: 8 })
    const suggestions = [...document.body.querySelectorAll('[data-testid="meeting-scope-suggestion"]')]
    expect(suggestions.map((element) => element.textContent?.trim())).toEqual(['Vacuum gripper5', 'Fence2'])
  })

  it('takes a suggestion with its icon and applies scope and icon', async () => {
    const view = await openPopover()

    ;(document.body.querySelector('[data-testid="meeting-scope-suggestion"]') as HTMLElement).click()
    await flushPromises()
    expect(find('meeting-scope-icon-mechanics')?.getAttribute('aria-pressed')).toBe('true')
    find('meeting-scope-apply')?.click()
    await flushPromises()

    expect(view.emitted('apply')).toEqual([[{ scope: 'Vacuum gripper', icon: 'mechanics' }]])
  })

  it('offers the existing scope a typed one nearly repeats', async () => {
    getMeetingScopeSuggestions.mockResolvedValue({ suggestions: [], near_duplicate: 'Vacuum gripper' })
    const view = await openPopover({ scope: null })

    await typeScope('vacum gripper')
    const hint = find('meeting-scope-near-duplicate') as HTMLElement
    expect(hint.textContent).toContain('There already is the scope "Vacuum gripper".')
    ;(hint.querySelector('button') as HTMLElement).click()
    await flushPromises()
    find('meeting-scope-apply')?.click()

    expect(view.emitted('apply')).toEqual([[{ scope: 'Vacuum gripper', icon: null }]])
  })

  it('picks one of the twelve icons and clears it with No Icon', async () => {
    const view = await openPopover({ icon: 'risk' })

    expect(document.body.querySelectorAll('[data-testid^="meeting-scope-icon-"]')).toHaveLength(12)
    expect(find('meeting-scope-icon-risk')?.getAttribute('aria-pressed')).toBe('true')
    find('meeting-scope-icon-safety')?.click()
    await flushPromises()
    expect(find('meeting-scope-icon-safety')?.getAttribute('aria-pressed')).toBe('true')
    expect(find('meeting-scope-icon-risk')?.getAttribute('aria-pressed')).toBe('false')
    find('meeting-scope-no-icon')?.click()
    await flushPromises()
    find('meeting-scope-apply')?.click()

    expect(view.emitted('apply')).toEqual([[{ scope: 'Gripper', icon: null }]])
  })

  it('applies an empty scope as none', async () => {
    const view = await openPopover()

    await typeScope('   ')
    find('meeting-scope-apply')?.click()

    expect(view.emitted('apply')).toEqual([[{ scope: null, icon: null }]])
  })
})
