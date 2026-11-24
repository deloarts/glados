import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { HANDBOOK_SECTIONS } from '../../utils/handbookSections'

import HandbookIndexView from '../HandbookIndexView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

const stub = { template: '<div />' }

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/handbook', name: 'Handbook', component: stub },
    { path: '/handbook/:section', name: 'HandbookSection', component: stub },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: stub },
  ],
})

let wrapper: ReturnType<typeof mount> | null = null

async function mountIndex() {
  await router.push('/handbook')
  await router.isReady()

  wrapper = mountWithApp(HandbookIndexView, {
    global: { plugins: [router] },
  })
  await flushPromises()
  // The first mount loads every handbook page lazily, which takes well over
  // the default second on a busy CI runner.
  await vi.waitFor(
    () => {
      expect(wrapper?.find('.handbook-index-tile-link').exists()).toBe(true)
    },
    { timeout: 10_000 },
  )
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('HandbookIndexView', () => {
  it('maps every section, including the ones nobody has written yet', async () => {
    await mountIndex()

    const tiles = wrapper!.findAll('.handbook-index-tile')
    expect(tiles).toHaveLength(HANDBOOK_SECTIONS.length)

    // Workspace, catalogue, production, procurement, resources and account
    // have docs today, so the rest must still be on the page, marked empty
    // rather than dropped.
    const empty = wrapper!.findAll('.handbook-index-tile-empty')
    expect(empty).toHaveLength(HANDBOOK_SECTIONS.length - 6)
    expect(empty[0]!.text()).toContain('Nothing has been written')
  })

  it('lists the pages of a documented section with a count', async () => {
    await mountIndex()

    const production = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Production'))!

    expect(production.classes()).not.toContain('handbook-index-tile-empty')
    expect(production.find('.handbook-index-tile-count').text()).toBe('26')
    expect(production.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Capacity',
      'How Auto-Plan places orders',
      'How Auto-Plan works',
      'Inspection Report',
      'KPIs',
      'Lot Lifecycle',
      'Lot Position Kind',
      'Lot Position Status',
      'Lot Position Transitions',
      'Lot Transitions',
      'Lots',
      'Machine Page',
      'Manage Orders',
      'Manage Production',
      'Manage Quotes',
      'Material Source',
      'Planning',
      'Planning Exceptions',
      'Production Order Lifecycle',
      'Production Order Transitions',
      'QA Inspections',
      'Queue Board',
      'Recording Completions',
      'Status Cascades',
      'When an order can start',
      'Work in Progress',
    ])
  })

  it('lists the pages of the procurement section, from demands to quotes', async () => {
    await mountIndex()

    const procurement = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Procurement'))!

    expect(procurement.classes()).not.toContain('handbook-index-tile-empty')
    expect(procurement.find('.handbook-index-tile-count').text()).toBe('22')
    expect(procurement.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Allocating Demands',
      'Auto-Assigning Lots',
      'Bought Item Demand Lifecycle',
      'Bought Item Demand Transitions',
      'Correcting a Delivery',
      'Creating Demands from a Sheet',
      'Delivery Tolerances',
      'Exporting Demands and Orders',
      'External Work',
      'Made Item Demand Lifecycle',
      'Made Item Demand Transitions',
      'Marking an Order Line as Delivered',
      'Order Lifecycle',
      'Order Line Actions',
      'Order Line Transitions',
      'Order Mails, Dockets and Files',
      'Order Transitions',
      'Orders',
      'Quote Request Transitions',
      'Quote Requests',
      'Source Item Demand Lifecycle',
      'Source Item Demand Transitions',
    ])
  })

  it('lists the pages of the resources section', async () => {
    await mountIndex()

    const resources = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Resources'))!

    expect(resources.classes()).not.toContain('handbook-index-tile-empty')
    expect(resources.find('.handbook-index-tile-count').text()).toBe('22')
    expect(resources.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Article Groups',
      'Contacts',
      'Customers',
      'Device Lists',
      'Display Times',
      'Exporting and Printing Reports',
      'Fabrication Methods',
      'Holidays',
      'Infoscreen Pages and Widgets',
      'Infoscreens',
      'Inspection Methods',
      'Machine Pools',
      'Messages to Terminals',
      'Print Dockets',
      'Print Labels',
      'Printed Copies and Distribution',
      'Printers',
      'Product Families',
      'Production Machines',
      'Source Item Types',
      'Suppliers',
      'Terminals',
    ])
  })

  it('lists the pages of the workspace section', async () => {
    await mountIndex()

    const workspace = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Workspace'))!

    expect(workspace.classes()).not.toContain('handbook-index-tile-empty')
    expect(workspace.find('.handbook-index-tile-count').text()).toBe('16')
    expect(workspace.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Device Completeness',
      'Device Overview',
      'Editing Documents',
      'Flow Sequences',
      'Meeting Cards',
      'Meeting Notes',
      'Meeting Page',
      'Meeting Todos',
      'PLC Tags',
      'Printing and Sending Meeting Notes',
      'Product Devices',
      'Products',
      'Project Lifecycle',
      'Projects',
      'Releasing Flow Sequences',
      'Revisions and Release',
    ])
  })

  it('lists the pages of the catalogue section', async () => {
    await mountIndex()

    const catalogue = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Catalogue'))!

    expect(catalogue.classes()).not.toContain('handbook-index-tile-empty')
    expect(catalogue.find('.handbook-index-tile-count').text()).toBe('7')
    expect(catalogue.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Bought Items',
      'Catalogue Item Lifecycle',
      'EPLAN Data Portal',
      'Exporting the Catalogue',
      'Importing Bought Items from a File',
      'Made Items',
      'Source Items',
    ])
  })

  it('lists the pages of the account section', async () => {
    await mountIndex()

    const account = wrapper!
      .findAll('.handbook-index-tile')
      .find((tile) => tile.text().includes('Account'))!

    expect(account.classes()).not.toContain('handbook-index-tile-empty')
    expect(account.find('.handbook-index-tile-count').text()).toBe('8')
    expect(account.findAll('.handbook-index-tile-link').map((l) => l.text())).toEqual([
      'Access Tokens',
      'AI Agents',
      'My Account',
      'Notifications and Permissions',
      'Passkeys',
      'Sessions',
      'Time Tracking',
      'Two-Factor Authentication',
    ])
  })

  it('states how much of the app is covered', async () => {
    await mountIndex()

    expect(wrapper!.find('.handbook-index-coverage').text()).toBe(
      `6 of ${HANDBOOK_SECTIONS.length} sections documented so far.`,
    )
  })
})
