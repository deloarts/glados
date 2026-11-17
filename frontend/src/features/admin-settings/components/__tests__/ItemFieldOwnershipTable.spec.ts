import { describe, it, expect } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import ItemFieldOwnershipTable from '../ItemFieldOwnershipTable.vue'
import type { ItemFieldOwnership } from '../../types/adminSettingsTypes'

// The backend serves item_fields in docs/reference/field-ownership.md sections 2 and 3 order,
// which interleaves owners (identity/PDM fields, then CAD-authored, then
// Web-owned, then system-managed) rather than grouping by owner. This
// fixture keeps that same interleaving deliberately so a passing test
// proves the component re-sorts for display rather than merely happening
// to already be in the right order. Every field named here has real
// `adminSettings.itemFields.fields.*`/`notes.made.*` i18n entries (see
// AdminSettingsTabSolidworksPdm.spec.ts's own fixture, which reuses the
// same subset).
const SCRAMBLED_FIELDS: ItemFieldOwnership[] = [
  { field: 'id', owner: 'server', mappable: false, policy_applicable: false, label_of: null },
  { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
  { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
  {
    field: 'source_item_id',
    owner: 'addin_web',
    mappable: true,
    policy_applicable: true,
    label_of: null,
  },
  { field: 'status', owner: 'web', mappable: false, policy_applicable: false, label_of: null },
  { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
  { field: 'mass', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
]

function indexOfField(html: string, field: string): number {
  const label = i18n.global.t(`adminSettings.itemFields.fields.${field}`) as string
  const index = html.indexOf(label)
  expect(index).toBeGreaterThanOrEqual(0)
  return index
}

function mountTable(
  fields: ItemFieldOwnership[],
  options: {
    kind?: 'made' | 'bought'
    variableMap?: Record<string, string>
    lockedRequired?: string[]
    required?: Record<string, boolean>
    canWrite?: boolean
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)

  return mountWithApp(ItemFieldOwnershipTable, {
    pinia,
    props: {
      kind: options.kind ?? 'made',
      fields,
      canWrite: options.canWrite ?? true,
      showPdmColumn: true,
      variableMap: options.variableMap ?? { part_number: 'PDM.PartNumber', revision: 'PDM.Revision' },
      updateInPlace: {},
      lockedRequired: options.lockedRequired ?? [],
      required: options.required ?? {},
    },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
}

describe('ItemFieldOwnershipTable', () => {
  it('renders rows grouped by owner (pdm, addin, addin_web, web, server) rather than backend order', () => {
    const wrapper = mountTable(SCRAMBLED_FIELDS)
    const html = wrapper.html()

    // pdm, addin, addin_web, web, server, with each group's own fields kept
    // in the fixture's original relative order (part_number before
    // revision, article_name before mass), the point of the stable-sort
    // requirement.
    const partNumber = indexOfField(html, 'part_number')
    const revision = indexOfField(html, 'revision')
    const articleName = indexOfField(html, 'article_name')
    const mass = indexOfField(html, 'mass')
    const sourceItemId = indexOfField(html, 'source_item_id')
    const status = indexOfField(html, 'status')
    const id = indexOfField(html, 'id')

    expect(revision).toBeGreaterThan(partNumber)
    expect(articleName).toBeGreaterThan(revision)
    expect(mass).toBeGreaterThan(articleName)
    expect(sourceItemId).toBeGreaterThan(mass)
    expect(status).toBeGreaterThan(sourceItemId)
    expect(id).toBeGreaterThan(status)
  })

  it('does not mutate the fields prop', () => {
    const original = [...SCRAMBLED_FIELDS]
    mountTable(SCRAMBLED_FIELDS)

    expect(SCRAMBLED_FIELDS).toEqual(original)
  })

  it('shows one group subheader per distinct owner present', () => {
    const wrapper = mountTable(SCRAMBLED_FIELDS)

    const headers = wrapper.findAll('.group-header-label').map((el) => el.text())
    // 5 distinct owners in the fixture (pdm, addin, addin_web, web, server),
    // labelled and ordered the same way as OWNER_GROUP_ORDER.
    expect(headers).toEqual([
      i18n.global.t('adminSettings.itemFields.owners.pdm'),
      i18n.global.t('adminSettings.itemFields.owners.addin'),
      i18n.global.t('adminSettings.itemFields.owners.addin_web'),
      i18n.global.t('adminSettings.itemFields.owners.web'),
      i18n.global.t('adminSettings.itemFields.owners.server'),
    ])
  })
})

function fieldLabel(field: string): string {
  return i18n.global.t(`adminSettings.itemFields.fields.${field}`) as string
}

function rowFor(wrapper: ReturnType<typeof mountTable>, field: string) {
  return wrapper.findAll('tr').find((row) => row.text().includes(fieldLabel(field)))!
}

// A label field (article_group_names, manufacturer_name, process_names,
// source_item_name) is a normal mappable, "addin"-owned row like any
// other. `label_of` only adds a muted note under it, naming its source
// field, and never disables the Custom Property input the way a
// non-mappable field's does.
const LABEL_FIELDS: ItemFieldOwnership[] = [
  { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
  {
    field: 'manufacturer_id',
    owner: 'addin',
    mappable: true,
    policy_applicable: true,
    label_of: null,
  },
  {
    field: 'manufacturer_name',
    owner: 'addin',
    mappable: true,
    policy_applicable: false,
    label_of: 'manufacturer_id',
  },
  {
    field: 'article_group_ids',
    owner: 'addin',
    mappable: true,
    policy_applicable: true,
    label_of: null,
  },
  {
    field: 'article_group_names',
    owner: 'addin',
    mappable: true,
    policy_applicable: false,
    label_of: 'article_group_ids',
  },
  { field: 'id', owner: 'server', mappable: false, policy_applicable: false, label_of: null },
]

describe('ItemFieldOwnershipTable label rows', () => {
  it('renders a label row grouped under the same "addin" owner as its source, not a separate group', () => {
    const wrapper = mountTable(LABEL_FIELDS, { kind: 'bought' })

    const headers = wrapper.findAll('.group-header-label').map((el) => el.text())
    expect(headers).toEqual([
      i18n.global.t('adminSettings.itemFields.owners.pdm'),
      i18n.global.t('adminSettings.itemFields.owners.addin'),
      i18n.global.t('adminSettings.itemFields.owners.server'),
    ])
  })

  it('shows the same "Add-in" owner badge on a label row as its source, and an editable Custom Property input on both', () => {
    const wrapper = mountTable(LABEL_FIELDS, { kind: 'bought' })

    const labelRow = rowFor(wrapper, 'manufacturer_name')
    expect(labelRow.findComponent({ name: 'Tag' }).props('value')).toBe(
      i18n.global.t('adminSettings.itemFields.owners.addin'),
    )
    const input = labelRow.findComponent({ name: 'InputText' })
    expect(input.exists()).toBe(true)
    expect(input.props('disabled')).toBe(false)

    const sourceRow = rowFor(wrapper, 'manufacturer_id')
    expect(sourceRow.findComponent({ name: 'InputText' }).exists()).toBe(true)
  })

  it('lets a label row\'s Custom Property be edited independently of its source', async () => {
    const variableMap: Record<string, string> = {
      manufacturer_id: 'Glados.ManufacturerId',
      manufacturer_name: '',
    }
    const wrapper = mountTable(LABEL_FIELDS, { kind: 'bought', variableMap })

    await rowFor(wrapper, 'manufacturer_name')
      .findComponent({ name: 'InputText' })
      .setValue('Vault.Manufacturer')

    expect(variableMap.manufacturer_name).toBe('Vault.Manufacturer')
    expect(variableMap.manufacturer_id).toBe('Glados.ManufacturerId')
  })

  it('shows a muted "label of <source>" note on a label row, naming its source field', () => {
    const wrapper = mountTable(LABEL_FIELDS, { kind: 'bought' })

    const note = rowFor(wrapper, 'article_group_names').find('.notes-cell').text()
    expect(note).toBe(
      i18n.global.t('adminSettings.itemFields.notes.labelOf', {
        source: fieldLabel('article_group_ids'),
      }),
    )
  })
})

// Required-field validation column (docs/PDM_INTEGRATION.md's "required
// fields" section): part_number stands in for a locked field, mass for a
// configurable one, id for a non-mappable field that gets no checkbox in
// this column either, exactly like the Custom Property input.
const REQUIRED_COLUMN_FIELDS: ItemFieldOwnership[] = [
  { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
  { field: 'mass', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
  { field: 'id', owner: 'server', mappable: false, policy_applicable: false, label_of: null },
]

describe('ItemFieldOwnershipTable required-field validation column', () => {
  it('renders the Validation column header', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS)

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.columns.required'))

    wrapper.unmount()
  })

  it('renders a locked row checked and disabled, with the locked hint tooltip', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      variableMap: { part_number: 'PDM.PartNumber', mass: 'Glados.Mass' },
    })

    const checkbox = rowFor(wrapper, 'part_number').findComponent({ name: 'Checkbox' })
    expect(checkbox.props('modelValue')).toBe(true)
    expect(checkbox.props('disabled')).toBe(true)
    // OpenVue's Tooltip directive (auto-imported per-SFC) only stamps this
    // marker attribute when its bound value is truthy.
    expect(checkbox.attributes('data-pd-tooltip')).toBe('true')

    wrapper.unmount()
  })

  it('renders a configurable row unchecked and enabled, and toggling it updates the passed required map', async () => {
    const requiredMap: Record<string, boolean> = {}
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      required: requiredMap,
      variableMap: { part_number: 'PDM.PartNumber', mass: 'Glados.Mass' },
    })

    const checkbox = rowFor(wrapper, 'mass').findComponent({ name: 'Checkbox' })
    expect(checkbox.props('modelValue')).toBeFalsy()
    expect(checkbox.props('disabled')).toBe(false)

    await checkbox.setValue(true)

    // The same map instance passed in as a prop is mutated in place, the
    // same convention the updateInPlace column relies on
    // (see AdminSettingsTabSolidworksPdm.vue's one-way `:required=` bind).
    expect(requiredMap.mass).toBe(true)

    wrapper.unmount()
  })

  it('disables a configurable row checkbox when canWrite is false', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      canWrite: false,
      variableMap: { part_number: 'PDM.PartNumber', mass: 'Glados.Mass' },
    })

    expect(rowFor(wrapper, 'mass').findComponent({ name: 'Checkbox' }).props('disabled')).toBe(true)

    wrapper.unmount()
  })

  it('renders no checkbox at all for a non-mappable row', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, { lockedRequired: ['part_number'] })

    expect(rowFor(wrapper, 'id').findComponent({ name: 'Checkbox' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows the warning icon on a checked (locked) row whose mapping is empty, and hides it once mapped', async () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      variableMap: { part_number: '', mass: '' },
    })

    expect(rowFor(wrapper, 'part_number').find('.warning-icon').exists()).toBe(true)

    await wrapper.setProps({ variableMap: { part_number: 'PDM.PartNumber', mass: '' } })

    expect(rowFor(wrapper, 'part_number').find('.warning-icon').exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows no warning icon on an unchecked configurable row even while its mapping is empty', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      required: { mass: false },
      variableMap: { part_number: 'PDM.PartNumber', mass: '' },
    })

    expect(rowFor(wrapper, 'mass').find('.warning-icon').exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows the warning icon once a configurable row is checked while its mapping is still empty', () => {
    const wrapper = mountTable(REQUIRED_COLUMN_FIELDS, {
      lockedRequired: ['part_number'],
      required: { mass: true },
      variableMap: { part_number: 'PDM.PartNumber', mass: '' },
    })

    expect(rowFor(wrapper, 'mass').find('.warning-icon').exists()).toBe(true)

    wrapper.unmount()
  })
})
