import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeMadeItemResponse, makeTestRouter } from '@/test-utils/factories'

// The successor-item label resolution falls back to a live API call when the
// id isn't already cached in the made-items store (see resolveSuccessorItem
// in MadeItemDetailFields.vue). Mocked here so a test mounting an item with
// a successor_item_id never fires a real, unawaited network request that
// outlives the test (an unhandled rejection once the environment tears
// down).
const getMadeItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('../../api/getMadeItems', () => ({
  getMadeItems: (...args: unknown[]) => getMadeItemsMock(...args),
}))

import MadeItemDetailFields from '../MadeItemDetailFields.vue'

import type { MadeItemResponse } from '../../types/madeItemsResponse'

const writeTextMock = vi.fn<(value: string) => Promise<void>>()
Object.assign(navigator, { clipboard: { writeText: writeTextMock } })

function makeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return makeMadeItemResponse({
    id: 9,
    public_id: 'bbbbbbbb-0000-0000-0000-000000000009',
    part_number: 'PN-MADE-9',
    created: '2026-02-01',
    changed: '2026-02-01T00:00:00Z',
    article_name: 'Bracket Assembly',
    mass: 1.25,
    base_size: '100x50',
    creator: {
      id: 1,
      public_id: 'u1',
      username: 'jdoe',
      full_name: 'Jane Doe',
      has_avatar: false,
    },
    ...overrides,
  })
}

function mountFields(item: MadeItemResponse) {
  return mountWithApp(MadeItemDetailFields, { props: { item } })
}

function makeRouter() {
  return makeTestRouter([{ path: '/catalogue/made-items/:id', component: RouteStub }])
}

describe('MadeItemDetailFields', () => {
  beforeEach(() => {
    writeTextMock.mockReset().mockResolvedValue(undefined)
    getMadeItemsMock.mockReset().mockResolvedValue({ items: [], total: 0 })
  })

  it('renders the key fields', () => {
    const wrapper = mountFields(makeItem())

    expect(wrapper.text()).toContain('PN-MADE-9')
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('1.0037')
    expect(wrapper.text()).toContain('100x50')
  })

  it('shows the PDM sync-state tag and link fields for a synced CAD item', () => {
    const wrapper = mountFields(
      makeItem({
        data_source: 'CAD',
        vault_id: 'vault-guid',
        pdm_file_id: 42,
        pdm_file_version: 7,
        pdm_synced_at: '2026-09-01T10:00:00Z',
        pdm_sync_state: 'synced',
      }),
    )

    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).toContain('Synced')
  })

  it('shows no PDM sync-state tag or link fields for a WEB item', () => {
    const wrapper = mountFields(makeItem({ data_source: 'WEB', pdm_file_id: null }))

    expect(wrapper.text()).not.toContain('PDM')
  })

  it('shows the status tag with success severity for an active item', () => {
    const wrapper = mountFields(makeItem({ status: 'active' }))

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('severity')).toBe('success')
  })

  it('shows the status tag with warn severity for a replaced item', () => {
    const wrapper = mountFields(makeItem({ status: 'replaced' }))

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('severity')).toBe('warn')
  })

  it('shows the status tag with danger severity for an inactive item', () => {
    const wrapper = mountFields(makeItem({ status: 'inactive' }))

    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('severity')).toBe('danger')
  })

  it('shows the combined part number and revision label', () => {
    const wrapper = mountFields(makeItem({ part_number: 'PN-MADE-9', revision: 'A' }))
    expect(wrapper.text()).toContain('PN-MADE-9:A')
  })

  it('renders the successor item fallback (raw id) before resolution', () => {
    const wrapper = mountFields(makeItem({ successor_item_id: 77 }))
    expect(wrapper.text()).toContain('#77')
  })

  it('shows the source item label from the bought item when the source is bought', () => {
    const wrapper = mountFields(
      makeItem({
        bought_item: {
          edit_version: 0,
          over_delivery_tolerance_percent: null,
          under_delivery_tolerance_percent: null,
          id: 3,
          public_id: 'c3',
          part_number: null,
          status: 'active',
          created: '2026-01-01',
          changed: '2026-01-01T00:00:00Z',
          changed_by: null,
          changed_by_id: null,
          archived: false,
          order_code_1: 'OC-1',
          order_code_2: null,
          gtin: null,
          ean: null,
          tariff_number: null,
          article_name: 'Hex Bolt',
          article_groups: [],
          data_source: 'WEB',
          mass: null,
          note: null,
          weblink: null,
          successor_item_id: null,
          creator_id: 1,
          creator: null,
          manufacturer_id: 3,
          manufacturer_name: 'ACME Corp',
          pdf_files: [],
          edp_part_id: null,
          edp_synced_at: null,
          pdm_file_id: null,
          pdm_file_version: null,
          pdm_locked_fields: [],
          pdm_sync_state: null,
          pdm_synced_at: null,
          product_family: null,
          product_family_id: null,
          revision: null,
          vault_id: null,
        },
      }),
    )

    expect(wrapper.text()).toContain('Hex Bolt (OC-1)')
  })

  it('copies a field value to the clipboard when its copy button is clicked', async () => {
    const wrapper = mountFields(makeItem({ revision: 'B' }))

    const copyButtons = wrapper.findAll('.copy-btn')
    expect(copyButtons.length).toBeGreaterThan(0)
    await copyButtons[0]!.trigger('click')

    expect(writeTextMock).toHaveBeenCalledTimes(1)
  })

  it('renders article-group tags when the item has groups', () => {
    const wrapper = mountFields(
      makeItem({
        article_groups: [
          {
            id: 1,
            public_id: 'g1',
            created: '2026-01-01',
            changed: '2026-01-01T00:00:00Z',
            changed_by: null,
            changed_by_id: null,
            archived: false,
            name: { enGB: 'Assemblies' },
            label_color: '#fff',
            label_font_color: '#000',
            description: { enGB: '' },
            creator_id: 1,
            creator: null,
          },
        ],
      }),
    )

    expect(wrapper.text()).toContain('Assemblies')
  })

  it('renders the creator, created, and changed meta as plain fields in the grid', () => {
    const wrapper = mountFields(makeItem({ created: '2026-02-01', changed: '2026-02-15' }))

    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).toEqual(
      expect.arrayContaining(['Creator', 'Creation Date', 'Change Date']),
    )
    expect(wrapper.text()).toContain('Jane Doe')
    expect(wrapper.text()).toContain('2026-02-01')
    expect(wrapper.text()).toContain('2026-02-15')
    // No avatar bubble: creator/changer render as plain text, not
    // UserAvatarPreview.
    expect(wrapper.findComponent({ name: 'UserAvatarPreview' }).exists()).toBe(false)
  })

  it('hides the meta fields when showMeta is false', () => {
    const wrapper = mountWithApp(MadeItemDetailFields, {
      props: { item: makeItem({ created: '2026-02-01', changed: '2026-02-15' }), showMeta: false },
    })

    const text = wrapper.text()
    expect(text).not.toContain('2026-02-01')
    expect(text).not.toContain('2026-02-15')
    expect(text).not.toContain('Jane Doe')
    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).not.toContain('Creator')
  })

  it('shows the status tag by default and hides it when showStatus is false', () => {
    const shown = mountFields(makeItem())
    expect(shown.findComponent({ name: 'Tag' }).exists()).toBe(true)

    const hidden = mountWithApp(MadeItemDetailFields, {
      props: { item: makeItem(), showStatus: false },
    })
    expect(hidden.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })

  it('still shows article-group tags when showStatus is false', () => {
    const wrapper = mountWithApp(MadeItemDetailFields, {
      props: {
        item: makeItem({
          article_groups: [
            {
              id: 1,
              public_id: 'g1',
              created: '2026-01-01',
              changed: '2026-01-01T00:00:00Z',
              changed_by: null,
              changed_by_id: null,
              archived: false,
              name: { enGB: 'Assemblies' },
              label_color: '#fff',
              label_font_color: '#000',
              description: { enGB: '' },
              creator_id: 1,
              creator: null,
            },
          ],
        }),
        showStatus: false,
      },
    })

    expect(wrapper.text()).toContain('Assemblies')
  })

  it('renders the id, article name, revision date/note and data source fields', () => {
    const wrapper = mountFields(
      makeItem({
        id: 321,
        article_name: 'Bracket Assembly Mk II',
        revision_date: '2026-02-10',
        revision_note: 'Widened the mounting slot.',
        data_source: 'CAD',
      }),
    )
    const text = wrapper.text()

    expect(text).toContain('#321')
    expect(text).toContain('Bracket Assembly Mk II')
    expect(text).toContain('2026-02-10')
    expect(text).toContain('Widened the mounting slot.')
    // The CAD data source is labelled after the vault it comes from.
    expect(text).toContain('PDM')
  })

  it('renders changed_by as a meta field only when present', () => {
    const changer = {
      id: 2,
      public_id: 'u2',
      username: 'bsmith',
      full_name: 'Bob Smith',
      email: 'b@x.com',
      has_avatar: false,
    }

    const withChanger = mountFields(makeItem({ changed_by: changer }))
    expect(withChanger.text()).toContain('Bob Smith')

    const withoutChanger = mountFields(makeItem({ changed_by: null }))
    expect(withoutChanger.text()).not.toContain('Bob Smith')
  })

  it('renders the successor item as a RouterLink when a router is installed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(MadeItemDetailFields, {
      props: { item: makeItem({ successor_item_id: 77 }) },
      global: { plugins: [router] },
    })
    await flushPromises()

    const link = wrapper.find('a.field-link')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('#77')
    expect(link.attributes('href')).toBe('/catalogue/made-items/77')
  })

  it('renders the successor item as plain text when no router is installed', () => {
    const wrapper = mountFields(makeItem({ successor_item_id: 77 }))

    expect(wrapper.find('a.field-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('#77')
  })

  it('renders a safe weblink as a clickable href', () => {
    const wrapper = mountFields(makeItem({ weblink: 'https://example.com' }))

    const link = wrapper.find('a[href="https://example.com"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toBe('https://example.com')
  })

  it('renders no href for an unsafe weblink, but still shows it as text', () => {
    const wrapper = mountFields(makeItem({ weblink: 'javascript:alert(1)' }))

    expect(wrapper.find('a').exists()).toBe(false)
    expect(wrapper.text()).toContain('javascript:alert(1)')
  })

  // The linked-material-source sub-section is its own component, see
  // MadeItemLinkedSourceCard.spec.ts for its coverage. MadeItemDetailFields.vue
  // does not render it or know about it at all.
})
