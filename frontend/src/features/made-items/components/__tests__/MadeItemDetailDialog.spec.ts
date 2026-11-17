import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { answerCadClaim, cadClaimOpen, cadClaimText } from '@/test-utils/cadClaim'
import { i18n } from '@/core/i18n'
import { useHostStore } from '@/core/host/stores/hostStore'

// Generic fallback for everything this dialog's descendants touch besides
// the made-items-specific calls mocked below (MaterialSourceSelect's nested
// selects, article/fabrication/inspection-method stores, the files store);
// mirrors MadeItemCreateForm.spec.ts's own generic mock.
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
      // PdmThumbnail (rendered only while hostStore.pdmEnabled is on)
      // fetches this as a blob. A 404 keeps it a harmless placeholder
      // rather than handing URL.createObjectURL a plain object dressed up
      // as a Blob.
      if (url.includes('/thumbnail')) {
        return Promise.reject({ isAxiosError: true, response: { status: 404 } })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: vi.fn<() => Promise<unknown>>(),
  },
}))

const getMadeItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../api/getMadeItems', () => ({
  getMadeItems: (...args: unknown[]) => getMadeItemsMock(...args),
}))

const getMadeItemRevisionsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../api/getMadeItemRevisions', () => ({
  getMadeItemRevisions: (...args: unknown[]) => getMadeItemRevisionsMock(...args),
}))

const createMadeItemRevisionMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../api/createMadeItemRevision', () => ({
  createMadeItemRevision: (...args: unknown[]) => createMadeItemRevisionMock(...args),
}))

import api from '@/core/api'
import { makeMadeItemResponse } from '@/test-utils/factories'
import MadeItemDetailDialog from '../MadeItemDetailDialog.vue'
import type { MadeItemResponse } from '../../types/madeItemsResponse'

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({ revision: 'B', material: 'Steel', ...overrides })
}

function makeRevisionsResponse(overrides: Record<string, unknown> = {}) {
  return {
    items: [
      {
        id: 1,
        public_id: '00000000-0000-0000-0000-000000000001',
        revision: 'B',
        revision_date: null,
        status: 'active',
        successor_item_id: null,
        created: '2026-02-01',
        is_newest: true,
      },
    ],
    next_revision: 'C',
    next_revision_error: null,
    can_create: true,
    reason: null,
    ...overrides,
  }
}

const mounted: VueWrapper[] = []

// Reused (not a fresh `createPinia()` per mount) so `beforeEach`'s hostStore
// mutation below actually reaches the mounted component. A fresh instance
// passed only to `global.plugins` would leave `useHostStore()` calls made
// beforehand (in the outer test scope, against whatever `setActivePinia`
// last set) pointed at a different Pinia than the one the component itself
// resolves via injection.
let pinia: ReturnType<typeof createPinia>

async function mountDialog(item: MadeItemResponse, editOnOpen = false, answerClaim = true) {
  const wrapper = mountWithApp(MadeItemDetailDialog, {
    pinia,
    attachTo: document.body,
    // Starts closed then opens, same as MadeItemCreateForm.spec.ts's own
    // mount helper. The dialog's revisions fetch (and editOnOpen) run off
    // the `visible` watcher, which (deliberately, see MadeItemDetailDialog's
    // `watch(visible, ...)`) only fires on a false->true transition, not on
    // an initial `true` prop value.
    props: { visible: false, item, editOnOpen },
  })
  mounted.push(wrapper)
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  // A PDM-claimed item asks before its form opens; these tests are about the form.
  if (answerClaim) await answerCadClaim()
  return wrapper
}

describe('MadeItemDetailDialog', () => {
  afterEach(() => {
    // attachTo: document.body leaves real DOM nodes in <body> once mounted:
    // without unmounting, a later test's `document.querySelector` (needed
    // because Dialog content teleports outside the wrapper's own root, see
    // MadeItemCreateForm.spec.ts's identical comment) can match a stale
    // element from a previous test's still-attached dialog instead of the
    // current one.
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  beforeEach(() => {
    getMadeItemsMock.mockReset().mockResolvedValue({ items: [], total: 0 })
    getMadeItemRevisionsMock.mockReset().mockResolvedValue(makeRevisionsResponse())
    createMadeItemRevisionMock.mockReset()
    pinia = createPinia()
    setActivePinia(pinia)
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.field_policy = [
      { field: 'article_name', web_requires_revision: true },
      { field: 'material', web_requires_revision: true },
      { field: 'mass', web_requires_revision: true },
      { field: 'note', web_requires_revision: false },
    ]
    hostStore.madeItemPartNumbers.revision.only_newest_editable = true
  })

  it('hides the revision Select when there is only one revision', async () => {
    const wrapper = await mountDialog(makeItem())

    expect(wrapper.findComponent({ name: 'Select' }).exists()).toBe(false)
  })

  it('shows the revision Select, newest first, current preselected, when siblings exist', async () => {
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisionsResponse({
        items: [
          {
            id: 1,
            public_id: 'a',
            revision: 'B',
            revision_date: null,
            status: 'active',
            successor_item_id: null,
            created: '2026-02-01',
            is_newest: true,
          },
          {
            id: 2,
            public_id: 'b',
            revision: 'A',
            revision_date: null,
            status: 'replaced',
            successor_item_id: 1,
            created: '2026-01-01',
            is_newest: false,
          },
        ],
      }),
    )

    const wrapper = await mountDialog(makeItem())

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.exists()).toBe(true)
    expect(select.props('modelValue')).toBe(1)
    expect(select.props('options')).toHaveLength(2)
  })

  it('swaps the displayed item when a different revision is picked', async () => {
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisionsResponse({
        items: [
          {
            id: 1,
            public_id: 'a',
            revision: 'B',
            revision_date: null,
            status: 'active',
            successor_item_id: null,
            created: '2026-02-01',
            is_newest: true,
          },
          {
            id: 2,
            public_id: 'b',
            revision: 'A',
            revision_date: null,
            status: 'replaced',
            successor_item_id: 1,
            created: '2026-01-01',
            is_newest: false,
          },
        ],
      }),
    )
    getMadeItemsMock.mockResolvedValue({
      items: [makeItem({ id: 2, revision: 'A', article_name: 'Old Bracket' })],
      total: 1,
    })

    const wrapper = await mountDialog(makeItem())

    const select = wrapper.findComponent({ name: 'Select' })
    await select.vm.$emit('update:modelValue', 2)
    await flushPromises()

    // Dialog content is teleported to <body>, outside the wrapper's own
    // root element. See MadeItemCreateForm.spec.ts's identical comment for
    // why `document` is queried directly instead of `wrapper.find`/`.text()`.
    expect(document.body.textContent).toContain('Old Bracket')
  })

  it('disables policy-flagged fields on a WEB item and shows the shared hint with a New revision button', async () => {
    const wrapper = await mountDialog(makeItem(), true)

    expect((document.querySelector('#mid-material') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-note') as HTMLTextAreaElement).disabled).toBe(false)
    expect(document.body.textContent).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))

    const revisionButton = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent === i18n.global.t('madeItems.catalogue.contextMenu.newRevision'),
    )
    expect(revisionButton).toBeTruthy()

    revisionButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    const revisionForm = wrapper.findComponent({ name: 'MadeItemCreateForm' })
    expect(revisionForm.props('revisionOf')).toMatchObject({ id: 1 })
  })

  // ── Granular material-source policy (bought_item_id/source_item_id
  // split: flagging only one half must not freeze both) ───────────────────

  it('leaves the unflagged half of a split material-source policy fully usable', async () => {
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: false },
      { field: 'source_item_id', web_requires_revision: true },
    ]

    const wrapper = await mountDialog(makeItem({ bought_item_id: 5, source_item_id: null }), true)

    // bought_item_id is the currently-set, unflagged field. Its own Select
    // and its wrapper stay fully interactive: flagging just source_item_id
    // locks only that field, not the whole material source.
    expect(document.querySelector('.field-locked')).toBeFalsy()
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).props('disabled')).toBe(false)
    expect(document.body.textContent).not.toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('locks the whole material-source control only once both fields are flagged', async () => {
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: true },
      { field: 'source_item_id', web_requires_revision: true },
    ]

    await mountDialog(makeItem(), true)

    expect(document.querySelector('.field-locked')).toBeTruthy()
    expect(document.body.textContent).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('blocks save client-side when a staged material-source change would violate a flagged field, even if it slipped past the UI', async () => {
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.field_policy = [
      { field: 'bought_item_id', web_requires_revision: false },
      { field: 'source_item_id', web_requires_revision: true },
    ]
    vi.mocked(api.put).mockClear()

    const wrapper = await mountDialog(
      makeItem({ bought_item_id: null, source_item_id: 99 }),
      true,
    )

    // Force a staged value that changes the flagged source_item_id. The
    // save-diff backstop must catch this even though MaterialSourceSelect's
    // own UI would never let a real user reach it.
    const materialSourceSelect = wrapper.findComponent({ name: 'MaterialSourceSelect' })
    await materialSourceSelect.vm.$emit('update:modelValue', {
      bought_item_id: null,
      source_item_id: 123,
      made_item_id: null,
    })
    await flushPromises()

    const saveButton = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent === i18n.global.t('common.save'),
    )
    saveButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    expect(api.put).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('madeItems.edit.fieldPolicy.hint'))
  })

  it('does not lock fields for a CAD item and shows the managed-by-PDM hint instead', async () => {
    await mountDialog(makeItem({ data_source: 'CAD' }), true)

    expect((document.querySelector('#mid-material') as HTMLInputElement).disabled).toBe(false)
    expect(document.body.textContent).toContain(
      i18n.global.t('madeItems.catalogue.contextMenu.newRevisionManagedByPdm'),
    )
  })

  it('disables Edit with a hint when only-newest-editable is on and this item is not the newest', async () => {
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisionsResponse({
        items: [
          {
            id: 1,
            public_id: 'a',
            revision: 'B',
            revision_date: null,
            status: 'active',
            successor_item_id: null,
            created: '2026-02-01',
            is_newest: false,
          },
        ],
      }),
    )

    await mountDialog(makeItem())
    // Wait for the revisions GET (fired without editOnOpen this time) to
    // resolve so canEdit reflects the real is_newest: false.
    await flushPromises()

    const editButton = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent === i18n.global.t('madeItems.catalogue.controls.edit'),
    )
    expect(editButton).toBeTruthy()
    expect(editButton!.disabled).toBe(true)
  })

  // ── Read-only up front: a row that would fail on save never looks
  // editable ────────────────────────────────────────────────────────────

  it('keeps Edit disabled while the revisions lookup is pending, then reflects the resolved answer', async () => {
    let resolveRevisions!: (value: unknown) => void
    getMadeItemRevisionsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRevisions = resolve
      }),
    )

    const wrapper = mountWithApp(MadeItemDetailDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: false, item: makeItem(), editOnOpen: false },
    })
    mounted.push(wrapper)
    await wrapper.setProps({ visible: true })
    await flushPromises()

    function findEditButton(): HTMLButtonElement | undefined {
      return Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent === i18n.global.t('madeItems.catalogue.controls.edit'),
      )
    }

    // Still in flight: disabled rather than permissive, so the button never
    // looks editable before the lookup has actually said so.
    expect(findEditButton()!.disabled).toBe(true)

    resolveRevisions(makeRevisionsResponse())
    await flushPromises()
    await flushPromises()

    // Resolved as the newest, so now enabled, and entering edit mode then
    // exposes an enabled Save button (belt-and-braces: the same `canEdit`
    // gates both).
    expect(findEditButton()!.disabled).toBe(false)
    findEditButton()!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    const saveButton = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent === i18n.global.t('common.save'),
    )
    expect(saveButton).toBeTruthy()
    expect(saveButton!.disabled).toBe(false)
  })

  it('defers editOnOpen until the lookup resolves and stays in view mode (with the notice) when not the newest', async () => {
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisionsResponse({
        items: [
          {
            id: 1,
            public_id: 'a',
            revision: 'B',
            revision_date: null,
            status: 'active',
            successor_item_id: 2,
            created: '2026-01-01',
            is_newest: false,
          },
          {
            id: 2,
            public_id: 'b',
            revision: 'C',
            revision_date: null,
            status: 'active',
            successor_item_id: null,
            created: '2026-02-01',
            is_newest: true,
          },
        ],
      }),
    )

    const wrapper = await mountDialog(makeItem(), true)

    // Never entered edit mode: none of the edit-form fields exist.
    expect(document.querySelector('#mid-article-name')).toBeFalsy()

    const notice = wrapper.findComponent({ name: 'Message' })
    expect(document.body.textContent).toContain(
      i18n.global.t('madeItems.edit.notNewestNotice', { revision: 'C' }),
    )
    expect(notice.exists()).toBe(true)
  })

  it('falls back to permissive and enters edit when the revisions lookup fails, never locking the user out', async () => {
    getMadeItemRevisionsMock.mockRejectedValue(new Error('network error'))

    await mountDialog(makeItem(), true)

    expect((document.querySelector('#mid-article-name') as HTMLInputElement | null)).toBeTruthy()
    const saveButton = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent === i18n.global.t('common.save'),
    )
    expect(saveButton).toBeTruthy()
    expect(saveButton!.disabled).toBe(false)
  })

  it('does not show the not-newest notice when only-newest-editable is off', async () => {
    const hostStore = useHostStore()
    hostStore.madeItemPartNumbers.revision.only_newest_editable = false
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisionsResponse({
        items: [
          {
            id: 1,
            public_id: 'a',
            revision: 'B',
            revision_date: null,
            status: 'active',
            successor_item_id: null,
            created: '2026-01-01',
            is_newest: false,
          },
        ],
      }),
    )

    const wrapper = await mountDialog(makeItem())

    // View mode's only possible Message is the not-newest notice itself
    // (the other Message instances in this dialog only ever render inside
    // the edit form). Not finding one here means the notice was
    // suppressed, as it should be with the policy off.
    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(false)
  })

  // ── PDM ownership read-only gating (docs/FIELD_OWNERSHIP.md principle 3),
  // independent of the WEB-only revision field policy above. The lock
  // list itself is server-provided (item.pdm_locked_fields) rather
  // than a client-side mirror of the ownership table, so these tests drive
  // it straight off the item fixture instead of the host PDM policy. ─────

  it('locks the fields named in item.pdm_locked_fields', async () => {
    const wrapper = await mountDialog(
      makeItem({
        data_source: 'CAD',
        pdm_locked_fields: [
          'article_name',
          'part_number',
          'material',
          'base_size',
          'weblink',
          'note',
          'mass',
        ],
      }),
      true,
    )

    expect((document.querySelector('#mid-article-name') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-part-number') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-material') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-base-size') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-weblink') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-note') as HTMLTextAreaElement).disabled).toBe(true)
    // mass uses the same isPdmLockedField('mass') call as the fields above,
    // through InputNumber, so it's covered via the component prop instead of
    // the native input, since InputNumber puts its native `id` (`inputId`, not
    // `id`) on the inner <input> rather than the id this dialog passes.
    const massInput = wrapper.findComponent({ name: 'InputNumber' })
    expect(massInput.props('disabled')).toBe(true)
  })

  it('does not lock any field when pdm_locked_fields is empty', async () => {
    await mountDialog(makeItem({ data_source: 'CAD', pdm_locked_fields: [] }), true)

    expect((document.querySelector('#mid-article-name') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#mid-part-number') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#mid-material') as HTMLInputElement).disabled).toBe(false)
  })

  it('locks only the fields the server listed, leaving the rest editable', async () => {
    await mountDialog(
      makeItem({ data_source: 'CAD', pdm_locked_fields: ['article_name'] }),
      true,
    )

    expect((document.querySelector('#mid-article-name') as HTMLInputElement).disabled).toBe(true)
    expect((document.querySelector('#mid-part-number') as HTMLInputElement).disabled).toBe(false)
    expect((document.querySelector('#mid-material') as HTMLInputElement).disabled).toBe(false)
  })

  // ── Lifecycle status feature (docs/PDM_INTEGRATION.md's "lifecycle
  // mapping" section): status is itself a server-lockable field, and
  // the successor picker on a locked row gives way to an explanatory hint
  // until the row's status is already replaced. ───────────────────────────

  it('locks the status Select when pdm_locked_fields includes status', async () => {
    const wrapper = await mountDialog(
      makeItem({ data_source: 'CAD', status: 'active', pdm_locked_fields: ['status'] }),
      true,
    )

    // The status Select is always the first Select rendered in the edit
    // grid, regardless of which other fields are locked.
    const statusSelect = wrapper.findAllComponents({ name: 'Select' })[0]
    expect(statusSelect!.props('disabled')).toBe(true)
  })

  it('still shows the successor picker on a locked row whose status is already replaced', async () => {
    await mountDialog(
      makeItem({ data_source: 'CAD', status: 'replaced', pdm_locked_fields: ['status'] }),
      true,
    )

    expect(document.querySelector('#mid-successor-item')).not.toBeNull()
    expect(document.body.textContent).not.toContain(
      i18n.global.t('madeItems.edit.pdmManagedStatusHint'),
    )
  })

  it('shows the PDM-managed-status hint instead of the successor picker on a locked row not yet replaced', async () => {
    await mountDialog(
      makeItem({ data_source: 'CAD', status: 'active', pdm_locked_fields: ['status'] }),
      true,
    )

    expect(document.querySelector('#mid-successor-item')).toBeNull()
    expect(document.body.textContent).toContain(
      i18n.global.t('madeItems.edit.pdmManagedStatusHint'),
    )
  })

  describe('CAD claim warning', () => {
    function formOpen(): boolean {
      return document.querySelector('#mid-article-name') !== null
    }

    async function clickSave(): Promise<void> {
      Array.from(document.querySelectorAll<HTMLButtonElement>('button'))
        .find((button) => button.textContent?.trim() === i18n.global.t('common.save'))
        ?.click()
      await flushPromises()
      await flushPromises()
    }

    it('asks before the form opens on a CAD item and opens nothing on Cancel', async () => {
      await mountDialog(makeItem({ data_source: 'CAD' }), true, false)

      expect(cadClaimOpen()).toBe(true)
      expect(formOpen()).toBe(false)

      await answerCadClaim(false)

      expect(formOpen()).toBe(false)
    })

    it('asks at save when the fresh read shows the item claimed meanwhile and saves nothing on Cancel', async () => {
      await mountDialog(makeItem({ data_source: 'WEB' }), true, false)
      expect(formOpen()).toBe(true)
      getMadeItemsMock.mockResolvedValue({ items: [makeItem({ data_source: 'CAD' })], total: 1 })
      vi.mocked(api.put).mockClear()

      await clickSave()

      expect(cadClaimOpen()).toBe(true)
      expect(cadClaimText()).toContain(i18n.global.t('catalogue.cadClaim.claimedMeanwhile'))

      await answerCadClaim(false)

      expect(api.put).not.toHaveBeenCalled()
      expect(formOpen()).toBe(true)
    })
  })
})
