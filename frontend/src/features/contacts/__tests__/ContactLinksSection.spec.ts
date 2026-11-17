import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerConfirmations } from '@/test-utils/confirmations'
import { makeSummary } from './contactFixtures'
import type { ContactLinksApi } from '../components/ContactLinksSection.vue'
import type { LinkedContactRow } from '../components/LinkedContactsTable.vue'
import type { ContactSummaryResponse } from '../types/contactResponse'

const granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))
vi.mock('../api/contactsApi', () => ({
  getContacts: async () => ({ items: [], total: 0, limit: 20, skip: 0 }),
}))

import ContactLinksSection from '../components/ContactLinksSection.vue'

interface Entry {
  contact: ContactSummaryResponse
  receives_meeting_notes: boolean
  inherited: boolean
}

function entry(receives: boolean, inherited = false): Entry {
  return { contact: makeSummary(), receives_meeting_notes: receives, inherited }
}

function makeApi(entries: Entry[]) {
  return {
    list: vi.fn<() => Promise<Entry[]>>().mockResolvedValue(entries),
    link: vi.fn<(id: number, receives: boolean) => Promise<Entry[]>>().mockResolvedValue(entries),
    setMeetingNotes: vi
      .fn<(id: number, receives: boolean) => Promise<Entry[]>>()
      .mockResolvedValue([entry(false, true)]),
    unlink: vi.fn<(id: number) => Promise<Entry[]>>().mockResolvedValue([]),
  } satisfies ContactLinksApi<Entry>
}

function toRow(value: Entry): LinkedContactRow {
  return {
    contact: value.contact,
    receivesMeetingNotes: value.receives_meeting_notes,
    sourceLabel: value.inherited ? 'From P-031' : null,
    canUnlink: !value.inherited,
  }
}

function mountSection(api: ContactLinksApi<Entry>, canWrite = true) {
  return mountWithApp(ContactLinksSection, {
    props: {
      ownerKey: 'project-1',
      hint: 'hint',
      api,
      // A generic component mounted directly takes its entries as unknown.
      toRow: toRow as (value: unknown) => LinkedContactRow,
      customerId: 2,
      customerName: 'Muster Anlagenbau',
      showSource: true,
      liveResources: [],
      canWrite,
      writeBlocked: canWrite ? '' : 'Only the designated user or a project manager edits this project.',
    },
    global: { directives: { tooltip: Tooltip } },
  })
}

beforeEach(() => {
  granted.clear()
  granted.add('read:contacts')
})

describe('ContactLinksSection', () => {
  it('shows an inherited contact with its source and no Unlink, and mutes it', async () => {
    const api = makeApi([entry(true, true)])
    const wrapper = mountSection(api)
    await flushPromises()

    expect(wrapper.text()).toContain('Thomas Muster')
    expect(wrapper.text()).toContain('From P-031')
    expect(wrapper.find('[data-testid="linked-contact-unlink"]').exists()).toBe(false)

    await wrapper.get('[data-testid="linked-contact-meeting-notes"] input').setValue(false)
    await flushPromises()

    expect(api.setMeetingNotes).toHaveBeenCalledWith(7, false)
  })

  it('unlinks an own contact after the confirmation', async () => {
    const confirmations = answerConfirmations('accept')
    const api = makeApi([entry(true)])
    const wrapper = mountSection(api)
    await flushPromises()

    await wrapper.get('[data-testid="linked-contact-unlink"]').trigger('click')
    await flushPromises()

    expect(api.unlink).toHaveBeenCalledWith(7)
    confirmations.stop()
  })

  it('keeps Link Contact and the switch visible but disabled without the record edit rights', async () => {
    const wrapper = mountSection(makeApi([entry(true)]), false)
    await flushPromises()

    expect(wrapper.get('[data-testid="contact-links-link"]').attributes('disabled')).toBeDefined()
    expect(
      wrapper.get('[data-testid="linked-contact-meeting-notes"] input').attributes('disabled'),
    ).toBeDefined()
  })

  it('loads nothing and says why without read:contacts', async () => {
    granted.clear()
    const api = makeApi([entry(true)])
    const wrapper = mountSection(api)
    await flushPromises()

    expect(api.list).not.toHaveBeenCalled()
    expect(wrapper.find('[data-testid="contact-links-no-access"]').exists()).toBe(true)
  })
})
