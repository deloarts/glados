import { describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { RouteStub, makeTestRouter } from '@/test-utils/factories'
import { useUsersStore } from '@/core/stores/usersStore'
import SourceItemDetailFields from '../SourceItemDetailFields.vue'

import type { SourceItemResponse } from '../../types/sourceItemsResponse'
import type { UserResponse } from '@/core/types/userResponse'

function item(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 12,
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'active',
    created: '2026-03-01',
    changed: '2026-03-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    type_id: 3,
    type_name: { enGB: 'Rod' },
    dimension: 'D20x100',
    material: 'Steel S235',
    mass: 1.5,
    note: null,
    order_code_1: 'OC-1',
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: { id: 1, full_name: 'Jane Doe', username: 'jane' } as SourceItemResponse['creator'],
    approver_id: null,
    manufacturer_id: 4,
    manufacturer_name: 'Acme Steel',
    ...overrides,
  }
}

function mountFields(overrides: Partial<SourceItemResponse> = {}) {
  return mountWithApp(SourceItemDetailFields, {
    props: { item: item(overrides) },
  })
}

function makeRouter() {
  return makeTestRouter([{ path: '/catalogue/source-items/:id', component: RouteStub }])
}

describe('SourceItemDetailFields', () => {
  it('renders the dimension, type, material, mass and manufacturer fields', () => {
    const wrapper = mountFields()
    const text = wrapper.text()
    expect(text).toContain('D20x100')
    expect(text).toContain('Rod')
    expect(text).toContain('Steel S235')
    expect(text).toContain('1.5')
    expect(text).toContain('Acme Steel')
    expect(text).toContain('OC-1')
  })

  it('renders the successor item id when present', () => {
    const wrapper = mountFields({ successor_item_id: 99 })
    expect(wrapper.text()).toContain('#99')
  })

  it('omits the successor field when there is none', () => {
    const wrapper = mountFields({ successor_item_id: null })
    expect(wrapper.text()).not.toContain('#99')
  })

  it('renders the note field only when present', () => {
    const withNote = mountFields({ note: 'Handle with care' })
    expect(withNote.text()).toContain('Handle with care')

    const withoutNote = mountFields({ note: null })
    expect(withoutNote.find('.field-wide').exists()).toBe(false)
  })

  it('renders the creator, created and changed meta as plain fields in the grid', () => {
    const wrapper = mountFields({ created: '2026-03-01', changed: '2026-03-05' })
    const text = wrapper.text()
    expect(text).toContain('2026-03-01')
    expect(text).toContain('2026-03-05')
    expect(text).toContain('Jane Doe')

    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).toEqual(expect.arrayContaining(['Creator', 'Created', 'Changed']))
    // Exactly one avatar bubble (the approver field); creator renders as
    // plain text, not a second UserAvatarPreview.
    expect(wrapper.findAllComponents({ name: 'UserAvatarPreview' })).toHaveLength(1)
  })

  // `changed` is a NOT NULL datetime initialised to `created`, so it is
  // never null and the field always renders, covered by the "renders the
  // creator, created and changed meta" test above.

  it.each([
    ['active', 'success'],
    ['replaced', 'warn'],
    ['inactive', 'danger'],
  ] as const)('gives the %s status tag severity %s', (status, severity) => {
    const wrapper = mountFields({ status })
    const tag = wrapper.findComponent({ name: 'Tag' })
    expect(tag.props('severity')).toBe(severity)
  })

  it('copies a field value to the clipboard when its copy button is clicked', async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    const wrapper = mountFields({ material: 'Steel S235' })
    const buttons = wrapper.findAll('.copy-btn')
    expect(buttons.length).toBeGreaterThan(0)

    await buttons[0]!.trigger('click')

    expect(writeText).toHaveBeenCalled()
  })

  it('hides the meta fields when showMeta is false', () => {
    const wrapper = mountWithApp(SourceItemDetailFields, {
      props: { item: item({ created: '2026-02-01', changed: '2026-02-15' }), showMeta: false },
    })

    const text = wrapper.text()
    expect(text).not.toContain('2026-02-01')
    expect(text).not.toContain('2026-02-15')
    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).not.toContain('Creator')
  })

  it('shows the status tag by default and hides it when showStatus is false', () => {
    const shown = mountFields()
    expect(shown.findComponent({ name: 'Tag' }).exists()).toBe(true)

    const hidden = mountWithApp(SourceItemDetailFields, {
      props: { item: item(), showStatus: false },
    })
    expect(hidden.findComponent({ name: 'Tag' }).exists()).toBe(false)
  })

  it('renders the id field', () => {
    const wrapper = mountFields({ id: 456 })
    expect(wrapper.text()).toContain('#456')
  })

  it('resolves the approver to a user via the users store', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const usersStore = useUsersStore()
    usersStore.users = [
      {
        id: 5,
        username: 'asmith',
        full_name: 'Alice Smith',
        email: 'a@x.com',
        has_avatar: false,
      } as UserResponse,
    ]

    const wrapper = mountWithApp(SourceItemDetailFields, {
      pinia,
      props: { item: item({ approver_id: 5 }) },
    })

    expect(wrapper.text()).toContain('Alice Smith')
  })

  it('renders the successor item as a RouterLink when a router is installed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(SourceItemDetailFields, {
      props: { item: item({ successor_item_id: 99 }) },
      global: { plugins: [router] },
    })

    const link = wrapper.find('a.field-link')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('#99')
    expect(link.attributes('href')).toBe('/catalogue/source-items/99')
  })

  it('renders the successor item as plain text when no router is installed', () => {
    const wrapper = mountFields({ successor_item_id: 99 })

    expect(wrapper.find('a.field-link').exists()).toBe(false)
    expect(wrapper.text()).toContain('#99')
  })
})
