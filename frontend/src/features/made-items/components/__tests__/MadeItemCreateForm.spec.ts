import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

// A mutable box (vi.hoisted, since vi.mock factories are hoisted above
// normal module-scope consts) so revisionOf-mode tests can swap the
// `/made-items/{id}/revisions` GET's response per test, while every other
// `api.get` call (article groups, fabrication/inspection methods, the
// nested MaterialSourceSelect's own lookups) keeps the empty-page fallback
// every other test in this file relies on.
const { revisionsResponseBox, postMock } = vi.hoisted(() => ({
  revisionsResponseBox: {
    value: {
      items: [],
      next_revision: 'B' as string | null,
      next_revision_error: null as string | null,
      can_create: true,
      reason: null as 'cad' | 'no_write' | null,
    },
  },
  postMock: vi.fn<(url: string, payload?: unknown) => Promise<unknown>>(),
}))

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>((url: string) => {
      if (url.endsWith('/revisions')) {
        return Promise.resolve({ data: revisionsResponseBox.value })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    }),
    post: postMock,
  },
}))

import { useHostStore } from '@/core/host/stores/hostStore'
import MadeItemCreateForm from '../MadeItemCreateForm.vue'
import type { MadeItemResponse } from '../../types/madeItemsResponse'

function makeCopyFromItem(): MadeItemResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '00000000-0000-0000-0000-000000000001',
    part_number: 'PN-1',
    status: 'active',
    archived: false,
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    revision: 'A',
    revision_date: null,
    revision_note: null,
    article_name: 'Bracket',
    article_groups: [],
    data_source: 'WEB',
    material: null,
    mass: null,
    base_size: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    changed_by_id: null,
    changed_by: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    customer_id: null,
    customer_name: null,
    customer_part_number: null,
    customer_revision: null,
    source_item: null,
    source_label: '',
    source_sublabel: '',
    processes: [
      {
        id: 1,
        public_id: '00000000-0000-0000-0000-000000000011',
        created: '2026-01-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        fabrication_method_name: { enGB: 'Sawing' },
        made_item_id: 1,
        position: 0,
        group_index: 0,
      },
      {
        id: 2,
        public_id: '00000000-0000-0000-0000-000000000012',
        created: '2026-01-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        fabrication_method_name: { enGB: 'Milling' },
        made_item_id: 1,
        position: 1,
        group_index: 1,
      },
      {
        id: 3,
        public_id: '00000000-0000-0000-0000-000000000013',
        created: '2026-01-01',
        note: null,
        estimated_setup_minutes: null,
        estimated_minutes_per_piece: null,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        fabrication_method_name: { enGB: 'Deburring' },
        made_item_id: 1,
        position: 2,
        group_index: 1,
      },
    ],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_source_item_id: null,
    pdm_sync_state: null,
    pdm_synced_at: null,
    vault_id: null,
  }
}

describe('MadeItemCreateForm', () => {
  it('renders all fields without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(MadeItemCreateForm, {
      attachTo: document.body,
      props: { visible: true },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(document.querySelector('#mi-article-name')).not.toBeNull()
    expect(document.querySelector('#mi-revision')).not.toBeNull()
    expect(document.querySelector('#mi-material')).not.toBeNull()
    expect(document.querySelector('#mi-article-groups')).not.toBeNull()
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('duplicate-item copy carries the source grouping into the staged editor', async () => {
    const wrapper = mountWithApp(MadeItemCreateForm, {
      attachTo: document.body,
      props: { visible: false, copyFrom: makeCopyFromItem() },
    })

    // The copy-on-open logic runs off the visible watcher (see
    // MadeItemCreateForm.vue), which only fires on a false->true change.
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    // Dialog content is teleported to <body>, outside the wrapper's own
    // root element. The earlier "renders all fields" test hits the same
    // constraint and queries `document` directly for the same reason.
    // Sawing (group 0), Milling (group 1), Deburring (group 1): split before
    // Milling, linked between Milling and Deburring.
    const toggles = document.querySelectorAll('.boundary-toggle')
    expect(toggles).toHaveLength(2)
    expect(toggles[0]!.querySelector('i')!.classList).toContain('mdi-arrow-split-vertical')
    expect(toggles[1]!.querySelector('i')!.classList).toContain('mdi-link')

    wrapper.unmount()
  })

  // The create form in "New revision" mode.
  describe('revisionOf mode', () => {
    function makeRevisionOfItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
      return { ...makeCopyFromItem(), id: 7, part_number: 'PN-7', article_name: 'Bracket', ...overrides }
    }

    async function mountRevisionOf(item: MadeItemResponse, pinia = createPinia()) {
      const wrapper = mountWithApp(MadeItemCreateForm, {
        pinia,
        attachTo: document.body,
        props: { visible: false, revisionOf: item },
      })
      await wrapper.setProps({ visible: true })
      await flushPromises()
      await flushPromises()
      return wrapper
    }

    it('pins the revision field to next_revision (read-only) and prefills the article name without a copy suffix', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: 'C',
        next_revision_error: null,
        can_create: true,
        reason: null,
      }

      const wrapper = await mountRevisionOf(makeRevisionOfItem({ article_name: 'Bracket' }))

      const revisionInput = document.querySelector('#mi-revision') as HTMLInputElement
      const partNumberInput = document.querySelector('#mi-part-number') as HTMLInputElement
      const articleNameInput = document.querySelector('#mi-article-name') as HTMLInputElement

      expect(revisionInput.disabled).toBe(true)
      expect(revisionInput.value).toBe('C')
      expect(partNumberInput.disabled).toBe(true)
      expect(partNumberInput.value).toBe('PN-7')
      // No "(copy)" suffix: a revision is a continuation, not a duplicate.
      expect(articleNameInput.value).toBe('Bracket')

      wrapper.unmount()
    })

    it('shows the predecessor-status Select with side-effect text when the setting is "ask"', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: 'C',
        next_revision_error: null,
        can_create: true,
        reason: null,
      }
      const pinia = createPinia()
      const wrapper = await mountRevisionOf(makeRevisionOfItem(), pinia)
      useHostStore(pinia).madeItemPartNumbers.revision.predecessor_status_web = 'ask'
      await flushPromises()

      const select = document.querySelector('#mi-predecessor-status')
      expect(select).not.toBeNull()
      expect(document.body.textContent).toContain(
        i18n.global.t('madeItems.create.revision.predecessorStatus.sideEffects.replaced'),
      )

      wrapper.unmount()
    })

    it('shows a fixed note instead of a Select when the predecessor status is not "ask"', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: 'C',
        next_revision_error: null,
        can_create: true,
        reason: null,
      }
      const pinia = createPinia()
      useHostStore(pinia).madeItemPartNumbers.revision.predecessor_status_web = 'inactive'
      const wrapper = await mountRevisionOf(makeRevisionOfItem(), pinia)

      expect(document.querySelector('#mi-predecessor-status')).toBeNull()
      expect(document.body.textContent).toContain(
        i18n.global.t('madeItems.create.revision.predecessorStatus.fixedNote', {
          status: i18n.global.t('madeItems.create.revision.predecessorStatus.options.inactive'),
        }),
      )

      wrapper.unmount()
    })

    it('disables submit and shows the reason when can_create is false', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: null,
        next_revision_error: null,
        can_create: false,
        reason: 'no_write',
      }

      const wrapper = await mountRevisionOf(makeRevisionOfItem())

      const saveButton = Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent === i18n.global.t('common.save'),
      )
      expect(saveButton?.disabled).toBe(true)
      expect(document.body.textContent).toContain(
        i18n.global.t('madeItems.create.revision.reasons.no_write'),
      )

      wrapper.unmount()
    })

    it('disables submit and shows next_revision_error when the revision cannot be incremented', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: null,
        next_revision_error: 'Current revision is not a recognised numbering scheme.',
        can_create: true,
        reason: null,
      }

      const wrapper = await mountRevisionOf(makeRevisionOfItem())

      const saveButton = Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent === i18n.global.t('common.save'),
      )
      expect(saveButton?.disabled).toBe(true)
      expect(document.body.textContent).toContain(
        'Current revision is not a recognised numbering scheme.',
      )

      wrapper.unmount()
    })

    it('submits via POST …/revisions with predecessor_status and an item payload without revision/part_number/data_source', async () => {
      revisionsResponseBox.value = {
        items: [],
        next_revision: 'C',
        next_revision_error: null,
        can_create: true,
        reason: null,
      }
      postMock.mockReset().mockResolvedValue({
        data: { ...makeRevisionOfItem(), id: 8, revision: 'C' },
      })

      const pinia = createPinia()
      useHostStore(pinia).madeItemPartNumbers.revision.predecessor_status_web = 'inactive'
      const wrapper = await mountRevisionOf(makeRevisionOfItem({ article_name: 'Bracket' }), pinia)

      const saveButton = Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent === i18n.global.t('common.save'),
      )
      saveButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith(
        '/made-items/7/revisions',
        expect.objectContaining({
          predecessor_status: 'inactive',
          item: expect.objectContaining({ article_name: 'Bracket' }),
        }),
      )
      const [, payload] = postMock.mock.calls[0]!
      const itemPayload = (payload as { item: Record<string, unknown> }).item
      expect(itemPayload).not.toHaveProperty('revision')
      expect(itemPayload).not.toHaveProperty('part_number')
      expect(itemPayload).not.toHaveProperty('data_source')

      wrapper.unmount()
    })
  })
})
