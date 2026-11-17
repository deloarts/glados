import { describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useProductionLotsStore } from '../../../../stores/productionLotsStore'

// The nested OrderDetailDialog (rendered unconditionally, controlled by
// v-model:visible) calls useConfirm() in its own setup, mocked rather than
// registering a real ConfirmationService, same pattern OrdersTable.spec.ts
// uses, since nothing here exercises a confirm dialog.
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: vi.fn<(options: unknown) => void>() }),
}))

import LotsTable from '../LotsTable.vue'
import LotDateRangeFilter from '../LotDateRangeFilter.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import NumberRangeFilter from '@/shared/components/table-filters/NumberRangeFilter.vue'
import TextFieldsFilter from '@/shared/components/forms/TextFieldsFilter.vue'
import { makeLotSummaryResponse, makeTestRouter } from '@/test-utils/factories'
import LotStepFilterCell from '../LotStepFilterCell.vue'
import { useProductionLotsFiltersStore } from '../../../stores/productionLotsFiltersStore'
import { STEP_CELL_SPECS, type StepCellKind } from '../../../utils/lotStepColumns'
import type {
  FabricationLotStep,
  LotSummaryResponse,
  LotSummaryStepExtra,
  LotSummaryStepResponse,
} from '../../../../types/productionLotsResponse'

// LotsTable.vue Column Mode renders one row per lot position. The default
// (both filtersStore.simpleMode and .widescreenMode start false) is what
// this exercises; Simple/Widescreen Mode's own markup is covered indirectly
// through LotSourceCell's own spec since `lotOf(data)` resolves to the
// same lot object in every mode.

function makeStep(
  overrides: Partial<FabricationLotStep & LotSummaryStepExtra> = {},
): LotSummaryStepResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: null,
    estimated_minutes_per_piece: null,
    time_budget_per_piece: null,
    sequence: 1,
    creator_id: 1,
    fabrication_method_id: 1,
    role: 'fabrication',
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: false,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: 1,
    source_process_id: null,
    position_kind: 'unassigned',
    position_needs_machine: false,
    position_status: 'pending',
    position_quantity: 10,
    position_quantity_remaining: 10,
    actions: [],
    ...overrides,
  }
}

async function mountTable(
  lots: LotSummaryResponse[] = [makeLotSummaryResponse()],
  propOverrides: { showManageOrders?: boolean } = {},
  options: { widescreenMode?: boolean } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (options.widescreenMode) useProductionLotsFiltersStore().widescreenMode = true
  const lotsStore = useProductionLotsStore()
  lotsStore.items = lots
  lotsStore.total = lots.length

  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(LotsTable, {
    pinia,
    props: {
      first: 0,
      rows: 25,
      showManageOrders: false,
      showManageProduction: false,
      showManageSource: false,
      openDetailById: vi.fn<(id: number) => Promise<void>>().mockResolvedValue(undefined),
      ...propOverrides,
    },
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
    },
  })
  return { wrapper, lotsStore }
}

describe('LotsTable', () => {
  it('mounts and renders one row per lot in the default (Column Mode) layout', async () => {
    const { wrapper } = await mountTable([
      makeLotSummaryResponse({ id: 1, lot_number: 'LOT-1' }),
      makeLotSummaryResponse({ id: 2, lot_number: 'LOT-2' }),
    ])

    const rows = wrapper.findAll('tbody tr[data-p-index]')
    expect(rows.length).toBe(2)
    expect(wrapper.text()).toContain('LOT-1')
    expect(wrapper.text()).toContain('LOT-2')
  })

  it('renders the empty table with no rows when there are no lots', async () => {
    const { wrapper } = await mountTable([])

    expect(wrapper.findAll('tbody tr[data-p-index]').length).toBe(0)
  })

  it('emits open-lot on row click when no Manage panel is active', async () => {
    const { wrapper } = await mountTable([makeLotSummaryResponse({ id: 7, lot_number: 'LOT-7' })])

    await wrapper.find('tbody tr[data-p-index]').trigger('click')

    const emitted = wrapper.emitted('open-lot')
    expect(emitted).toBeTruthy()
    expect((emitted![0]![0] as LotSummaryResponse).id).toBe(7)
  })

  it('does not emit open-lot on row click while a Manage panel is active', async () => {
    const { wrapper } = await mountTable([makeLotSummaryResponse({ id: 7 })], {
      showManageOrders: true,
    })

    await wrapper.find('tbody tr[data-p-index]').trigger('click')

    expect(wrapper.emitted('open-lot')).toBeFalsy()
  })

  it('renders a row-number cell for each row', async () => {
    const { wrapper } = await mountTable([makeLotSummaryResponse({ id: 1 })])

    // The row-number column renders `first + index + 1`.
    const firstDataCell = wrapper.find('tbody tr td')
    expect(firstDataCell.exists()).toBe(true)
    expect(firstDataCell.text()).toBe('1')
  })

  describe('row filters', () => {
    const searchPlaceholder = i18n.global.t('production.lots.filters.searchBy')
    // Structural so it accepts whatever findAllComponents infers for a
    // script-setup component.
    const kindsOf = (cells: { props(): { kind: StepCellKind } }[]) =>
      cells.map((c) => c.props().kind)

    it('renders a filter input for every column in Column Mode', async () => {
      const { wrapper } = await mountTable([makeLotSummaryResponse()])
      const head = wrapper.find('thead')

      // Text filters: lot number, project, step note. Counted by
      // placeholder, since DatePicker and InputNumber render an InputText of
      // their own underneath. Item and source item search their two lines
      // in one filter card each.
      expect(head.findAll(`input[placeholder="${searchPlaceholder}"]`).length).toBe(3)
      expect(head.findAllComponents(TextFieldsFilter).length).toBe(2)
      // Date ranges: required delivery, source delivery, plus the three step
      // date columns. Created filters by creator and date in one field.
      expect(head.findAllComponents(LotDateRangeFilter).length).toBe(5)
      expect(head.findAllComponents(UserDateFilter).length).toBe(2)
      // Numeric ranges: quantity, setup, per piece.
      expect(head.findAllComponents(NumberRangeFilter).length).toBe(3)
      // One step filter cell per step column.
      const stepCells = head.findAllComponents(LotStepFilterCell)
      expect(kindsOf(stepCells)).toEqual(STEP_CELL_SPECS.map((s) => s.kind))
    })

    it('writes a typed lot number into the filters store', async () => {
      const { wrapper } = await mountTable([makeLotSummaryResponse()])
      const filtersStore = useProductionLotsFiltersStore()

      // The lot number column is the first text filter in the header.
      const lotNumberInput = wrapper
        .find('thead')
        .findAll(`input[placeholder="${searchPlaceholder}"]`)[0]!
      await lotNumberInput.setValue('LOT-42')

      expect(filtersStore.lotNumber).toBe('LOT-42')
    })

    it('renders the step filters only once in Widescreen Mode, in the first step group', async () => {
      const lot = makeLotSummaryResponse({
        steps: [
          makeStep({ id: 1, position_id: 1, sequence: 1 }),
          makeStep({ id: 2, position_id: 2, sequence: 2 }),
        ],
      })
      const { wrapper } = await mountTable([lot], {}, { widescreenMode: true })
      const head = wrapper.find('thead')

      // Two positions, so two step groups of eight body columns each, but
      // the filter cells appear for the first group only.
      expect(head.findAll('th').length).toBeGreaterThan(0)
      const stepCells = head.findAllComponents(LotStepFilterCell)
      expect(stepCells.length).toBe(STEP_CELL_SPECS.length)
      expect(kindsOf(stepCells)).toEqual(STEP_CELL_SPECS.map((s) => s.kind))
    })
  })
})
