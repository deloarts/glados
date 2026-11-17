import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import AutoComplete from 'openvue/autocomplete'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMeeting } from './meetingFixtures'

vi.mock('../api/meetingsApi', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return Object.fromEntries(Object.keys(actual).map((name) => [name, vi.fn<(...args: unknown[]) => unknown>()]))
})

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: () => true }),
}))

import * as api from '../api/meetingsApi'
import MeetingFormDialog from '../components/MeetingFormDialog.vue'
import MeetingTagInput from '../components/MeetingTagInput.vue'

let wrapper: VueWrapper | null = null

async function openDialog(props: Record<string, unknown>) {
  wrapper = mountWithApp(MeetingFormDialog, { attachTo: document.body, props: { visible: false, ...props } })
  // The form fills itself when the dialog opens.
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function save(): void {
  document.body.querySelector<HTMLButtonElement>('[data-testid="meeting-form-save"]')?.click()
}

beforeEach(() => {
  vi.mocked(api.getMeetingTagSuggestions).mockResolvedValue({
    suggestions: [
      { name: 'Milestone', count: 3 },
      { name: 'Factory acceptance', count: 1 },
    ],
  })
  vi.mocked(api.createMeeting).mockResolvedValue(makeMeeting())
  vi.mocked(api.updateMeeting).mockResolvedValue(makeMeeting())
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('MeetingFormDialog tags', () => {
  it('sends the typed tags without repeats when a meeting is created', async () => {
    const dialog = await openDialog({ ownerKind: 'project', ownerId: 142 })
    const name = document.body.querySelector<HTMLInputElement>('[data-testid="meeting-form-name"]')
    if (name) {
      name.value = 'Design Review'
      name.dispatchEvent(new Event('input'))
    }

    dialog.findComponent(MeetingTagInput).findComponent(AutoComplete).vm.$emit('update:modelValue', [
      '  Milestone ',
      'milestone',
      'Risk',
    ])
    await flushPromises()
    save()
    await flushPromises()

    expect(api.createMeeting).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Design Review', project_id: 142, tags: ['Milestone', 'Risk'] }),
    )
  })

  it('takes a tag typed but not confirmed when the meeting is saved', async () => {
    await openDialog({ ownerKind: 'project', ownerId: 142 })
    const name = document.body.querySelector<HTMLInputElement>('[data-testid="meeting-form-name"]')
    if (name) {
      name.value = 'Design Review'
      name.dispatchEvent(new Event('input'))
    }
    const tagField = document.body.querySelector<HTMLInputElement>('[data-testid="meeting-tag-input"] input')
    if (tagField) tagField.value = 'Acceptance'

    save()
    await flushPromises()

    expect(api.createMeeting).toHaveBeenCalledWith(expect.objectContaining({ tags: ['Acceptance'] }))
  })

  it('keeps the tags of an edited meeting and sends them back', async () => {
    const meeting = makeMeeting({ tags: ['Milestone', 'Risk'] })
    const dialog = await openDialog({ meeting })

    expect(dialog.findComponent(MeetingTagInput).props('modelValue')).toEqual(['Milestone', 'Risk'])
    save()
    await flushPromises()

    expect(api.updateMeeting).toHaveBeenCalledWith(
      meeting.id,
      expect.objectContaining({ tags: ['Milestone', 'Risk'], expected_edit_version: meeting.edit_version }),
    )
  })

  it('refuses to save more tags than a meeting carries', async () => {
    const dialog = await openDialog({ meeting: makeMeeting() })

    dialog
      .findComponent(MeetingTagInput)
      .findComponent(AutoComplete)
      .vm.$emit('update:modelValue', Array.from({ length: 11 }, (_, index) => `Tag ${index}`))
    await flushPromises()
    save()
    await flushPromises()

    expect(api.updateMeeting).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('A meeting carries at most 10 tags.')
  })
})

describe('MeetingTagInput', () => {
  it('offers the typed text first and then the tags in use that contain it', async () => {
    const input = mountWithApp(MeetingTagInput, { props: { modelValue: [] } })
    await flushPromises()

    input.findComponent(AutoComplete).vm.$emit('complete', { query: 'mile', originalEvent: new Event('input') })
    await flushPromises()
    expect(input.findComponent(AutoComplete).props('suggestions')).toEqual(['mile', 'Milestone'])

    input.findComponent(AutoComplete).vm.$emit('complete', { query: 'MILESTONE', originalEvent: new Event('input') })
    await flushPromises()
    expect(input.findComponent(AutoComplete).props('suggestions')).toEqual(['Milestone'])
    input.unmount()
  })

  it('takes the typed text as a tag on a comma, in the spelling already in use', async () => {
    const input = mountWithApp(MeetingTagInput, { props: { modelValue: ['Risk'] } })
    await flushPromises()
    const field = input.get('input')

    ;(field.element as HTMLInputElement).value = 'milestone'
    await field.trigger('keydown', { key: ',' })

    expect(input.emitted('update:modelValue')?.at(-1)).toEqual([['Risk', 'Milestone']])
    expect((field.element as HTMLInputElement).value).toBe('')
    input.unmount()
  })
})
