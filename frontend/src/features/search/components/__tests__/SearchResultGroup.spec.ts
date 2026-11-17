import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import SearchResultGroup from '../SearchResultGroup.vue'

import type {
  GlobalSearchGroup,
  GlobalSearchHit,
  GlobalSearchHitDetails,
} from '../../types/globalSearchResponse'

function makeDetails(overrides: Partial<GlobalSearchHitDetails>): GlobalSearchHitDetails {
  return {
    status: null,
    article_name: null,
    part_number: null,
    order_code_1: null,
    revision: null,
    item_count: null,
    supplier_name: null,
    made_item_id: null,
    made_item_part_number: null,
    made_item_revision: null,
    made_item_article_name: null,
    source_label: null,
    steps: null,
    execution_kind: null,
    execution_label: null,
    ...overrides,
  }
}

function makeHit(overrides: Partial<GlobalSearchHit> = {}): GlobalSearchHit {
  return {
    resource: 'projects',
    id: 7,
    public_id: '9f3c1111-1111-1111-1111-111111111111',
    label: 'AX-2201',
    subtitle: 'Injection mold housing',
    details: null,
    match_kind: 'exact',
    via_kind: null,
    ...overrides,
  }
}

function makeGroup(overrides: Partial<GlobalSearchGroup> = {}): GlobalSearchGroup {
  const items = overrides.items ?? [makeHit()]
  return {
    resource: 'projects',
    total: items.length,
    items,
    ...overrides,
  }
}

function mountGroup(group: GlobalSearchGroup) {
  return mountWithApp(SearchResultGroup, {
    props: { group },
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        BoughtItemThumbnailCell: true,
        MadeItemThumbnailCell: true,
        SourceItemThumbnailCell: true,
      },
    },
  })
}

describe('SearchResultGroup', () => {
  it('renders a bought-item row with order code and part number, article name below, omitting the part-number segment when null', () => {
    const withPartNumber = makeHit({
      resource: 'bought-items',
      id: 1,
      label: 'ABC-123',
      subtitle: null,
      details: makeDetails({ order_code_1: 'ABC-123', part_number: 'TN-26-00004', article_name: 'Housing' }),
    })
    const withoutPartNumber = makeHit({
      resource: 'bought-items',
      id: 2,
      label: 'XYZ-1',
      subtitle: null,
      details: makeDetails({ order_code_1: 'XYZ-1', part_number: null, article_name: 'Bolt' }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'bought-items', items: [withPartNumber, withoutPartNumber] }))
    const rows = wrapper.findAll('button.hit-row')

    expect(rows[0]!.text()).toContain('ABC-123')
    expect(rows[0]!.text()).toContain('TN-26-00004')
    expect(rows[0]!.text()).toContain('Housing')

    // No part number: the primary line still shows the order code but must
    // not render an empty/dangling separator for the missing segment.
    expect(rows[1]!.text()).toContain('XYZ-1')
    expect(rows[1]!.text()).toContain('Bolt')
    expect(rows[1]!.find('.info-sep').exists()).toBe(false)
  })

  it('renders a made-item row with part number first and article name second, falling back to article name when part number is null', () => {
    const withPartNumber = makeHit({
      resource: 'made-items',
      id: 3,
      label: 'TN-2',
      subtitle: null,
      details: makeDetails({ part_number: 'TN-2', article_name: 'Bracket', revision: 'B' }),
    })
    const withoutPartNumber = makeHit({
      resource: 'made-items',
      id: 4,
      label: 'Widget',
      subtitle: null,
      details: makeDetails({ part_number: null, article_name: 'Widget', revision: null }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'made-items', items: [withPartNumber, withoutPartNumber] }))
    const rows = wrapper.findAll('button.hit-row')

    const primaryFirst = rows[0]!.find('.hit-label').text()
    expect(primaryFirst).toContain('TN-2')
    expect(rows[0]!.text()).toContain('Bracket')
    expect(rows[0]!.text()).toContain('B')

    // Falls back to the article name as the primary text, so it must not also
    // repeat as the secondary line once it has been promoted.
    const secondRow = rows[1]!
    expect(secondRow.find('.hit-label').text()).toContain('Widget')
    expect(secondRow.find('.hit-subtitle').exists()).toBe(false)
  })

  it('renders an order row with the status tag text, supplier and item count', () => {
    const hit = makeHit({
      resource: 'orders',
      id: 5,
      label: 'ORD-99',
      subtitle: null,
      details: makeDetails({ status: 'ordered', supplier_name: 'ACME', item_count: 3 }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'orders', items: [hit] }))

    expect(wrapper.text()).toContain('ORD-99')
    expect(wrapper.text()).toContain('Ordered')
    expect(wrapper.text()).toContain('ACME')
    expect(wrapper.text()).toContain('3 items')
  })

  it('renders a production-lot row with status tag, made item, source and steps, omitting the source segment when null', () => {
    const withSource = makeHit({
      resource: 'production-lots',
      id: 6,
      label: 'LOT-1',
      subtitle: null,
      details: makeDetails({
        status: 'planned',
        made_item_part_number: 'TN-9',
        made_item_article_name: 'Widget',
        source_label: 'Ø40 1.4301',
        steps: ['Sawing', 'Milling'],
      }),
    })
    const withoutSource = makeHit({
      resource: 'production-lots',
      id: 8,
      label: 'LOT-2',
      subtitle: null,
      details: makeDetails({
        status: 'planned',
        made_item_part_number: 'TN-10',
        made_item_article_name: 'Gadget',
        source_label: null,
        steps: ['Milling'],
      }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'production-lots', items: [withSource, withoutSource] }))
    const rows = wrapper.findAll('button.hit-row')

    expect(rows[0]!.text()).toContain('LOT-1')
    expect(rows[0]!.text()).toContain('Planned')
    expect(rows[0]!.text()).toContain('TN-9')
    expect(rows[0]!.text()).toContain('Ø40 1.4301')
    expect(rows[0]!.text()).toContain('Sawing › Milling')

    expect(rows[1]!.text()).not.toContain('Ø40')
    expect(rows[1]!.text()).toContain('TN-10')
    expect(rows[1]!.text()).toContain('Milling')
  })

  it('renders a production-order row with the execution label, or "Manual" when the kind is manual', () => {
    const withMachine = makeHit({
      resource: 'production-orders',
      id: 9,
      label: 'PO-1',
      subtitle: null,
      details: makeDetails({
        status: 'paused',
        made_item_part_number: 'TN-11',
        made_item_article_name: 'Sprocket',
        execution_kind: 'machine',
        execution_label: 'DMU 50',
      }),
    })
    const manual = makeHit({
      resource: 'production-orders',
      id: 10,
      label: 'PO-2',
      subtitle: null,
      details: makeDetails({
        status: 'paused',
        made_item_part_number: 'TN-12',
        made_item_article_name: 'Cog',
        execution_kind: 'manual',
        execution_label: null,
      }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'production-orders', items: [withMachine, manual] }))
    const rows = wrapper.findAll('button.hit-row')

    expect(rows[0]!.text()).toContain('PO-1')
    expect(rows[0]!.text()).toContain('Paused')
    expect(rows[0]!.text()).toContain('DMU 50')

    expect(rows[1]!.text()).toContain('PO-2')
    expect(rows[1]!.text()).toContain('Manual')
  })

  it('renders a calculation row with the document reference, the status tag and the title', () => {
    const hit = makeHit({
      resource: 'calculations',
      id: 9,
      label: 'CAL-26-0042',
      subtitle: 'Gripper torque',
      details: makeDetails({ status: 'released', revision: 'B' }),
    })

    const wrapper = mountGroup(makeGroup({ resource: 'calculations', items: [hit] }))
    const row = wrapper.find('button.hit-row')

    expect(row.find('.hit-label').text()).toContain('CAL-26-0042 rev. B')
    expect(row.text()).toContain('Released')
    expect(row.text()).toContain('Gripper torque')
  })

  it('falls back to label/subtitle rendering when a hit has no details', () => {
    const hit = makeHit({ resource: 'projects', label: 'AX-2201', subtitle: 'Injection mold housing' })

    const wrapper = mountGroup(makeGroup({ resource: 'projects', items: [hit] }))

    expect(wrapper.text()).toContain('AX-2201')
    expect(wrapper.text()).toContain('Injection mold housing')
  })

  it('emits select with the hit when a row is clicked', async () => {
    const hit = makeHit({ id: 42 })
    const wrapper = mountGroup(makeGroup({ items: [hit] }))

    await wrapper.find('button.hit-row').trigger('click')

    expect(wrapper.emitted('select')).toEqual([[hit]])
  })

  it('shows a "via <kind>" marker for a related hit', () => {
    const hit = makeHit({
      resource: 'projects',
      label: 'AX-2201',
      subtitle: 'Injection mold housing',
      match_kind: 'related',
      via_kind: 'project',
    })

    const wrapper = mountGroup(makeGroup({ resource: 'projects', items: [hit] }))

    expect(wrapper.find('.hit-marker').text()).toBe('via project')
  })

  it('shows a "≈ similar" marker for a fuzzy hit', () => {
    const hit = makeHit({
      resource: 'projects',
      label: 'AX-2201',
      subtitle: 'Injection mold housing',
      match_kind: 'fuzzy',
    })

    const wrapper = mountGroup(makeGroup({ resource: 'projects', items: [hit] }))

    expect(wrapper.find('.hit-marker').text()).toBe('≈ similar')
  })

  it('shows no marker when a hit has no match_kind', () => {
    const hit = makeHit({ resource: 'projects', label: 'AX-2201', subtitle: 'Injection mold housing' })

    const wrapper = mountGroup(makeGroup({ resource: 'projects', items: [hit] }))

    expect(wrapper.find('.hit-marker').exists()).toBe(false)
  })

  it('shows the show-all link only when total exceeds the number of items rendered', () => {
    const partial = mountGroup(makeGroup({ resource: 'projects', total: 12, items: [makeHit()] }))
    expect(partial.find('.show-all-link').exists()).toBe(true)

    const complete = mountGroup(makeGroup({ resource: 'projects', total: 1, items: [makeHit()] }))
    expect(complete.find('.show-all-link').exists()).toBe(false)
  })
})
