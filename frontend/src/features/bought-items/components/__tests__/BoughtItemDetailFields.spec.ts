import { describe, it, expect, vi, beforeEach } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'
import BoughtItemDetailFields from '../BoughtItemDetailFields.vue'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

const writeTextMock = vi.fn<(value: string) => Promise<void>>()
Object.assign(navigator, { clipboard: { writeText: writeTextMock } })

function makeItem(overrides: Partial<BoughtItemResponse> = {}): BoughtItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 7,
    public_id: 'aaaaaaaa-0000-0000-0000-000000000007',
    part_number: 'PN-007',
    revision: null,
    status: 'active',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
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
    creator: { id: 1, public_id: 'u1', username: 'jdoe', full_name: 'Jane Doe', has_avatar: false },
    manufacturer_id: 3,
    manufacturer_name: 'ACME Corp',
    edp_part_id: null,
    edp_synced_at: null,
    pdf_files: [],
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_locked_fields: [],
    pdm_sync_state: null,
    pdm_synced_at: null,
    product_family: null,
    product_family_id: null,
    vault_id: null,
    ...overrides,
  }
}

function mountFields(item: BoughtItemResponse) {
  return mountWithApp(BoughtItemDetailFields, { props: { item } })
}

function makeRouter() {
  return makeTestRouter([{ path: '/catalogue/bought-items/:id', component: RouteStub }])
}

describe('BoughtItemDetailFields', () => {
  beforeEach(() => {
    writeTextMock.mockReset().mockResolvedValue(undefined)
  })

  it('renders the key fields', () => {
    const wrapper = mountFields(makeItem())

    expect(wrapper.text()).toContain('OC-1')
    expect(wrapper.text()).toContain('PN-007')
    expect(wrapper.text()).toContain('ACME Corp')
  })

  it('shows the PDM sync-state tag and link fields for a conflicted CAD item', () => {
    const wrapper = mountFields(
      makeItem({
        data_source: 'CAD',
        vault_id: 'vault-guid',
        pdm_file_id: 42,
        pdm_file_version: 3,
        pdm_synced_at: '2026-09-01T10:00:00Z',
        pdm_sync_state: 'conflict',
      }),
    )

    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('Conflict')
  })

  it('shows no PDM link fields for a WEB item', () => {
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

  it('renders the revision field with the empty placeholder when null', () => {
    const wrapper = mountFields(makeItem({ revision: null }))
    expect(wrapper.text()).toContain('-')
  })

  it('renders the revision value when present', () => {
    const wrapper = mountFields(makeItem({ revision: 'A' }))
    expect(wrapper.text()).toContain('A')
  })

  it('renders the successor item link when present', () => {
    const wrapper = mountFields(makeItem({ successor_item_id: 42 }))
    expect(wrapper.text()).toContain('#42')
  })

  it('copies a field value to the clipboard when its copy button is clicked', async () => {
    const wrapper = mountFields(makeItem({ order_code_1: 'OC-COPY-ME' }))

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
            name: { enGB: 'Fasteners' },
            label_color: '#fff',
            label_font_color: '#000',
            description: { enGB: '' },
            creator_id: 1,
            creator: null,
          },
        ],
      }),
    )

    expect(wrapper.text()).toContain('Fasteners')
  })

  it('renders the creator, created, and changed footer meta', () => {
    const wrapper = mountFields(makeItem({ created: '2026-02-01', changed: '2026-02-15' }))

    expect(wrapper.text()).toContain('2026-02-01')
    expect(wrapper.text()).toContain('2026-02-15')
  })

  it('hides the footer meta when showMeta is false', () => {
    const wrapper = mountWithApp(BoughtItemDetailFields, {
      props: { item: makeItem({ created: '2026-02-01', changed: '2026-02-15' }), showMeta: false },
    })

    expect(wrapper.find('.detail-footer-meta').exists()).toBe(false)
  })

  it('shows the status tag by default and hides it when showStatus is false', () => {
    const shown = mountFields(makeItem())
    expect(shown.findComponent({ name: 'Tag' }).exists()).toBe(true)

    const hidden = mountWithApp(BoughtItemDetailFields, {
      props: { item: makeItem(), showStatus: false },
    })
    expect(hidden.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })

  it('still shows article-group tags when showStatus is false', () => {
    const wrapper = mountWithApp(BoughtItemDetailFields, {
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
              name: { enGB: 'Fasteners' },
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

    expect(wrapper.text()).toContain('Fasteners')
  })

  it('renders the id, article name and data source fields', () => {
    const wrapper = mountFields(makeItem({ id: 123, article_name: 'Hex Bolt M6', data_source: 'CAD' }))

    expect(wrapper.text()).toContain('#123')
    expect(wrapper.text()).toContain('Hex Bolt M6')
    // The CAD data source is labelled after the vault it comes from.
    expect(wrapper.text()).toContain('PDM')
  })

  it('renders the successor item as a RouterLink when a router is installed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(BoughtItemDetailFields, {
      props: { item: makeItem({ successor_item_id: 42 }) },
      global: { plugins: [router] },
    })

    const link = wrapper.find('a.field-link')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('#42')
    expect(link.attributes('href')).toBe('/catalogue/bought-items/42')
  })

  it('renders the successor item as plain text when no router is installed', () => {
    const wrapper = mountFields(makeItem({ successor_item_id: 42 }))

    expect(wrapper.find('a.field-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('#42')
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
})
