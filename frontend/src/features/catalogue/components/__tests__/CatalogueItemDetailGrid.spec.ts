import { describe, it, expect } from 'vitest'
import Panel from 'openvue/panel'

import { mountWithApp } from '@/test-utils/mountWithApp'
import CatalogueItemDetailGrid from '../CatalogueItemDetailGrid.vue'

describe('CatalogueItemDetailGrid', () => {
  it('renders only the areas whose slot was given content', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      slots: {
        item: '<div class="item-content">Item</div>',
        demands: '<div class="demands-content">Demands</div>',
      },
    })

    expect(wrapper.find('.area-item').exists()).toBe(true)
    expect(wrapper.find('.area-demands').exists()).toBe(true)
    expect(wrapper.find('.area-files').exists()).toBe(false)
    expect(wrapper.find('.area-processes').exists()).toBe(false)
    expect(wrapper.find('.area-orders').exists()).toBe(false)
    expect(wrapper.find('.area-lots').exists()).toBe(false)
    expect(wrapper.find('.area-usedin').exists()).toBe(false)
    expect(wrapper.find('.area-changelog').exists()).toBe(false)
  })

  it('renders the processes and lots areas when given, made-only slots that no longer share a catch-all', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      slots: {
        processes: '<div class="processes-content">Processes</div>',
        lots: '<div class="lots-content">Lots</div>',
      },
    })

    expect(wrapper.find('.area-processes').exists()).toBe(true)
    expect(wrapper.find('.area-lots').exists()).toBe(true)
  })

  it('wraps every rendered slot in a record-card wrapper; only item and processes stay out of the scroll idiom', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      slots: {
        item: '<div>Item</div>',
        files: '<div>Files</div>',
        processes: '<div>Processes</div>',
        source: '<div>Source</div>',
        lots: '<div>Lots</div>',
      },
    })

    // `files`/`source`/`lots` (and every `.lower-grid` card) keep the
    // scroll idiom. Their Panel content is taken out of flow so a long
    // card never grows its row/cell.
    for (const area of ['.area-files', '.area-source', '.area-lots']) {
      const el = wrapper.find(area)
      expect(el.classes()).toContain('record-card')
      expect(el.classes()).toContain('record-card--scroll')
    }
    // `item`'s content must stay in flow so `.head-row` measures its real
    // height, so it is not `record-card--scroll`, unlike every other card.
    const item = wrapper.find('.area-item')
    expect(item.classes()).toContain('record-card')
    expect(item.classes()).not.toContain('record-card--scroll')
    // The processes card sizes to its own content in the `.head-middle` flex
    // column, so its Panel must stay in flow too, no
    // scroll idiom on that wrapper either.
    const processes = wrapper.find('.area-processes')
    expect(processes.classes()).toContain('record-card')
    expect(processes.classes()).not.toContain('record-card--scroll')
  })

  it('groups item/files/processes/source under .head-row, and orders/demands/lots/usedIn/changelog under .lower-grid', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      slots: {
        item: '<div>Item</div>',
        files: '<div>Files</div>',
        processes: '<div>Processes</div>',
        source: '<div>Source</div>',
        orders: '<div>Orders</div>',
        demands: '<div>Demands</div>',
        lots: '<div>Lots</div>',
        usedIn: '<div>Used in</div>',
        changelog: '<div>Changelog</div>',
      },
    })

    const headRow = wrapper.find('.head-row')
    expect(headRow.exists()).toBe(true)
    for (const area of ['.area-item', '.area-files', '.area-processes', '.area-source']) {
      expect(headRow.find(area).exists()).toBe(true)
    }

    // `files`/`processes` stack inside their own `.head-middle` column,
    // beside `item` and `source`.
    const headMiddle = headRow.find('.head-middle')
    expect(headMiddle.exists()).toBe(true)
    expect(headMiddle.find('.area-files').exists()).toBe(true)
    expect(headMiddle.find('.area-processes').exists()).toBe(true)

    const lowerGrid = wrapper.find('.lower-grid')
    expect(lowerGrid.exists()).toBe(true)
    for (const area of ['.area-orders', '.area-demands', '.area-lots', '.area-usedin', '.area-changelog']) {
      expect(lowerGrid.find(area).exists()).toBe(true)
    }
    // Neither container leaks the other's cards.
    expect(headRow.find('.area-orders').exists()).toBe(false)
    expect(lowerGrid.find('.area-item').exists()).toBe(false)
  })

  it('omits .head-row/.head-middle/.lower-grid entirely when none of their cards are given', () => {
    const onlyLower = mountWithApp(CatalogueItemDetailGrid, {
      slots: { demands: '<div>Demands</div>' },
    })
    expect(onlyLower.find('.head-row').exists()).toBe(false)
    expect(onlyLower.find('.lower-grid').exists()).toBe(true)

    const onlyHead = mountWithApp(CatalogueItemDetailGrid, {
      slots: { item: '<div>Item</div>' },
    })
    expect(onlyHead.find('.head-row').exists()).toBe(true)
    expect(onlyHead.find('.lower-grid').exists()).toBe(false)
    // No `files`/`processes` given, so there is nothing for `.head-middle`
    // to stack. It must not render an empty column.
    expect(onlyHead.find('.head-middle').exists()).toBe(false)
  })

  it('renders the slot content inside its wrapper', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      slots: { changelog: '<div class="my-changelog">Changelog body</div>' },
    })

    expect(wrapper.find('.area-changelog .my-changelog').text()).toBe('Changelog body')
  })

  it('adds record-grid--no-files whenever the files slot is absent, and removes it once given', () => {
    const withoutFiles = mountWithApp(CatalogueItemDetailGrid, {
      slots: { item: '<div>Item</div>' },
    })
    const withFiles = mountWithApp(CatalogueItemDetailGrid, {
      slots: { item: '<div>Item</div>', files: '<div>Files</div>' },
    })

    expect(withoutFiles.find('.record-grid').classes()).toContain('record-grid--no-files')
    expect(withFiles.find('.record-grid').classes()).not.toContain('record-grid--no-files')
  })

  it('adds record-grid--processes/--lots only when those slots are given', () => {
    const bare = mountWithApp(CatalogueItemDetailGrid, { slots: { item: '<div>Item</div>' } })
    const withBoth = mountWithApp(CatalogueItemDetailGrid, {
      slots: { item: '<div>Item</div>', processes: '<div>P</div>', lots: '<div>L</div>' },
    })

    expect(bare.find('.record-grid').classes()).not.toContain('record-grid--processes')
    expect(bare.find('.record-grid').classes()).not.toContain('record-grid--lots')
    expect(withBoth.find('.record-grid').classes()).toContain('record-grid--processes')
    expect(withBoth.find('.record-grid').classes()).toContain('record-grid--lots')
  })

  it('puts a slotted Panel root directly under .record-card, not one level deeper', () => {
    // The `.record-card`/`.record-card--scroll` CSS threads flex height down
    // via `.record-card > :deep(.p-panel)` (CatalogueItemDetailGrid.vue). It
    // depends on the Panel this component wraps being an immediate child of
    // the wrapper div, not nested inside some other element. A real Panel
    // (not a stub) pins the DOM shape that selector assumes.
    const wrapper = mountWithApp(CatalogueItemDetailGrid, {
      global: { components: { Panel } },
      slots: {
        item: '<Panel header="Item" data-testid="slot-panel"><div>Body</div></Panel>',
      },
    })

    expect(wrapper.find('.record-card > [data-testid="slot-panel"]').exists()).toBe(true)
  })

  it('renders nothing but the empty grid when no slots are given', () => {
    const wrapper = mountWithApp(CatalogueItemDetailGrid)

    expect(wrapper.find('.record-grid').exists()).toBe(true)
    expect(wrapper.find('.record-grid').classes()).toContain('record-grid--no-files')
    expect(wrapper.findAll('[class*="area-"]')).toHaveLength(0)
  })

  describe('source slot (linked-source card)', () => {
    it('renders the area, wrapped in record-card record-card--scroll, only when given', () => {
      const without = mountWithApp(CatalogueItemDetailGrid, { slots: { item: '<div>Item</div>' } })
      expect(without.find('.area-source').exists()).toBe(false)
      expect(without.find('.record-grid').classes()).not.toContain('record-grid--source')

      const withSource = mountWithApp(CatalogueItemDetailGrid, {
        slots: { item: '<div>Item</div>', source: '<div class="my-source">Source</div>' },
      })
      const area = withSource.find('.area-source')
      expect(area.exists()).toBe(true)
      expect(area.classes()).toContain('record-card')
      expect(area.classes()).toContain('record-card--scroll')
      expect(withSource.find('.record-grid').classes()).toContain('record-grid--source')
      expect(area.find('.my-source').text()).toBe('Source')
    })

    it('coexists with the files/processes areas (the made-item page combination)', () => {
      const wrapper = mountWithApp(CatalogueItemDetailGrid, {
        slots: {
          item: '<div>Item</div>',
          files: '<div>Files</div>',
          processes: '<div>Processes</div>',
          source: '<div>Source</div>',
        },
      })

      expect(wrapper.find('.area-item').exists()).toBe(true)
      expect(wrapper.find('.area-files').exists()).toBe(true)
      expect(wrapper.find('.area-processes').exists()).toBe(true)
      expect(wrapper.find('.area-source').exists()).toBe(true)
      const classes = wrapper.find('.record-grid').classes()
      expect(classes).toContain('record-grid--source')
      expect(classes).toContain('record-grid--processes')
      expect(classes).not.toContain('record-grid--no-files')
    })

    it('still renders sanely (source area present) when combined with every other modifier', () => {
      const wrapper = mountWithApp(CatalogueItemDetailGrid, {
        slots: {
          processes: '<div>Processes</div>',
          lots: '<div>Lots</div>',
          source: '<div>Source</div>',
        },
      })

      // No `item`/`files` given here (files absent => --no-files), so this
      // covers the --source.--no-files.--processes.--lots combination.
      const classes = wrapper.find('.record-grid').classes()
      expect(classes).toContain('record-grid--source')
      expect(classes).toContain('record-grid--processes')
      expect(classes).toContain('record-grid--lots')
      expect(classes).toContain('record-grid--no-files')
      expect(wrapper.find('.area-source').exists()).toBe(true)
      expect(wrapper.find('.area-processes').exists()).toBe(true)
      expect(wrapper.find('.area-lots').exists()).toBe(true)
    })
  })
})
