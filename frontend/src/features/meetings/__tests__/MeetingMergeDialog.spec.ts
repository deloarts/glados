import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import MeetingMergeDialog from '../components/MeetingMergeDialog.vue'

let wrapper: VueWrapper | null = null

function find(testId: string): HTMLElement | null {
  return document.body.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
}

async function mountDialog(theirs: string, mine: string) {
  wrapper = mountWithApp(MeetingMergeDialog, {
    attachTo: document.body,
    props: { visible: true, theirs, mine },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('MeetingMergeDialog', () => {
  it('shows their text, the user text and the lines between them', async () => {
    await mountDialog('Line one\nTheir line', 'Line one\nMy line')

    expect(find('meeting-merge-theirs')?.textContent).toBe('Line one\nTheir line')
    expect(find('meeting-merge-mine')?.textContent).toBe('Line one\nMy line')
    const lines = [...document.body.querySelectorAll<HTMLElement>('[data-kind]')].map((line) => [
      line.dataset.kind,
      line.querySelector('.diff-text')?.textContent,
    ])
    expect(lines).toEqual([
      ['same', 'Line one'],
      ['removed', 'Their line'],
      ['added', 'My line'],
    ])
  })

  it('starts the merged text as the user text and saves what was merged', async () => {
    const view = await mountDialog('Their text', 'My text')
    const field = find('meeting-merge-text') as HTMLTextAreaElement

    expect(field.value).toBe('My text')
    field.value = 'Their text\nMy text'
    field.dispatchEvent(new Event('input'))
    await flushPromises()
    find('meeting-merge-save')?.click()

    expect(view.emitted('save')).toEqual([['Their text\nMy text']])
  })

  it('shows a save error in the footer', async () => {
    const view = await mountDialog('a', 'b')
    await view.setProps({ error: 'The card was deleted.' })

    expect(document.body.textContent).toContain('The card was deleted.')
  })
})
