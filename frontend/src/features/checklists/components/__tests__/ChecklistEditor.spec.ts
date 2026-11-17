import { describe, it, expect } from 'vitest'
import { reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { noOwnerData } from '../../composables/useOwnerData'
import type { OwnerData } from '../../composables/useOwnerData'
import type { ChecklistOwner } from '../../types/checklist'
import { CHECKLISTS } from '../../utils/definitions'
import { emptyState } from '../../utils/state'
import type { HeaderTextField } from '../../utils/state'
import type { Answer, ChecklistDefinition, ChecklistState } from '../../utils/types'
import ChecklistEditor from '../ChecklistEditor.vue'
import ChecklistHeaderForm from '../ChecklistHeaderForm.vue'

const hydraulics = CHECKLISTS.hydraulics
const TODAY = new Date(2026, 9, 9)

const OWNER_FIELDS: OwnerData = {
  ownerNumber: 'PR-7',
  ownerCustomer: 'ACME',
  ownerProduct: '',
  ownerManager: 'Jane Doe',
  designation: 'Press 12',
  machineType: 'HP-400',
  placingOnMarket: '2026-11-01',
  installationSite: 'Linz',
  installationLocation: 'Hall 3',
  legalBasis: 'directive',
}

interface MountOptions {
  definition?: ChecklistDefinition
  state?: ChecklistState
  owner?: ChecklistOwner
  ownerFields?: OwnerData
  readOnly?: boolean
  changedIds?: ReadonlySet<string> | null
}

// Mounts the editor on a reactive state and applies its events the way the
// detail page does, so the editor re-renders on its own edits.
async function mountEditor(options: MountOptions = {}) {
  const state = reactive(options.state ?? emptyState(TODAY))
  const wrapper = mountWithApp(ChecklistEditor, {
    props: {
      definition: options.definition ?? hydraulics,
      state,
      owner: options.owner ?? { kind: 'product', id: 7, label: 'PR-7' },
      ownerFields: options.ownerFields ?? OWNER_FIELDS,
      readOnly: options.readOnly ?? false,
      releaseRequired: true,
      releasedBy: null,
      changedIds: options.changedIds ?? null,
      onAnswer: (id: string, value: Answer | null) => {
        if (value === null) delete state.answers[id]
        else state.answers[id] = value
      },
      onRemark: (id: string, value: string) => {
        state.remarks[id] = value
      },
      onHeader: (field: HeaderTextField, value: string) => {
        state.header[field] = value
      },
    },
  })
  await flushPromises()
  return { wrapper, state }
}

type Wrapper = Awaited<ReturnType<typeof mountEditor>>['wrapper']

function text(wrapper: Wrapper, testid: string): string {
  return wrapper.get(`[data-testid="${testid}"]`).text()
}

async function click(wrapper: Wrapper, testid: string) {
  await wrapper.get(`[data-testid="${testid}"]`).trigger('click')
  await flushPromises()
}

async function chooseFilter(wrapper: Wrapper, value: string) {
  const filter = wrapper.findAllComponents({ name: 'SelectButton' }).find((c) => c.attributes('data-testid') === 'cl-filter')
  if (!filter) throw new Error('no filter')
  filter.vm.$emit('update:modelValue', value)
  await flushPromises()
}

describe('ChecklistEditor', () => {
  it('shows an empty hydraulics checklist with the data of its owner', async () => {
    const { wrapper } = await mountEditor()
    const total = hydraulics.items.length

    expect(text(wrapper, 'cl-verdict')).toBe('Open')
    expect(text(wrapper, 'cl-count-open')).toBe(String(total))
    expect(text(wrapper, 'cl-completion')).toBe('0 % answered')
    expect(text(wrapper, 'cl-section-progress-assessment')).toBe('0 of 5 answered')
    expect(text(wrapper, 'cl-header-owner-number')).toBe('PR-7')
    expect(text(wrapper, 'cl-header-owner-manager')).toBe('Jane Doe')
    expect(text(wrapper, 'cl-header-machine-designation')).toBe('Press 12')
    expect(text(wrapper, 'cl-header-machine-installationLocation')).toBe('Hall 3')
    expect(text(wrapper, 'cl-header-machine-legalBasis')).toBe('Directive 2006/42/EC')
    expect(text(wrapper, 'cl-header-checked-by')).toBe('Not released yet')
    expect(wrapper.find('[data-testid="cl-methods-legend"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('says when a checklist belongs to nobody', async () => {
    const { wrapper } = await mountEditor({ owner: { kind: 'personal' }, ownerFields: noOwnerData() })
    expect(wrapper.find('[data-testid="cl-header-owner"]').exists()).toBe(false)
    expect(text(wrapper, 'cl-header')).toContain('A personal checklist')
    wrapper.unmount()
  })

  it('answers items and fails as soon as there is a finding', async () => {
    const { wrapper, state } = await mountEditor()

    await click(wrapper, 'cl-section-toggle-assessment')
    expect(wrapper.get('[data-testid="cl-section-toggle-assessment"]').attributes('aria-expanded')).toBe('true')

    await click(wrapper, 'cl-answer-assessment.documents-yes')
    expect(text(wrapper, 'cl-verdict')).toBe('Open')
    await click(wrapper, 'cl-answer-assessment.circuitFunctions-defect')

    expect(state.answers).toEqual({ 'assessment.documents': 'yes', 'assessment.circuitFunctions': 'defect' })
    expect(text(wrapper, 'cl-count-yes')).toBe('1')
    expect(text(wrapper, 'cl-count-defect')).toBe('1')
    expect(text(wrapper, 'cl-section-progress-assessment')).toBe('2 of 5 answered')
    expect(text(wrapper, 'cl-verdict')).toBe('Failed')
    expect(text(wrapper, 'cl-problems')).toContain('1.1/1.1')
    expect(wrapper.find('[data-testid="cl-remark-assessment.circuitFunctions"]').exists()).toBe(true)

    await click(wrapper, 'cl-answer-assessment.documents-yes')
    expect(state.answers['assessment.documents']).toBeUndefined()
    expect(text(wrapper, 'cl-section-progress-assessment')).toBe('1 of 5 answered')

    wrapper.unmount()
  })

  it('takes the machine data from the product and cites the annex of its legal basis', async () => {
    const item = (wrapper: Wrapper) => wrapper.get('[data-testid="cl-item-marking.interchangeableLines"]').text()
    const directive = await mountEditor()
    expect(item(directive.wrapper)).toContain('Annex I 1.5.4')
    expect(directive.wrapper.find('[data-testid="cl-header-designation"]').exists()).toBe(false)
    expect(directive.wrapper.find('[data-testid="cl-legal-basis-warning"]').exists()).toBe(false)
    directive.wrapper.unmount()

    const regulation = await mountEditor({ ownerFields: { ...OWNER_FIELDS, legalBasis: 'regulation' } })
    expect(item(regulation.wrapper)).toContain('Annex III 1.5.4')
    regulation.wrapper.unmount()
  })

  it('warns when the product keeps the Directive past the switch to the Regulation', async () => {
    const { wrapper } = await mountEditor({ ownerFields: { ...OWNER_FIELDS, placingOnMarket: '2027-03-01' } })
    expect(wrapper.find('[data-testid="cl-legal-basis-warning"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('passes edits of its own header fields on', async () => {
    const { wrapper, state } = await mountEditor()
    wrapper.getComponent(ChecklistHeaderForm).vm.$emit('update', 'assessedBy', 'J. Doe')
    await flushPromises()
    expect(state.header.assessedBy).toBe('J. Doe')
    wrapper.unmount()
  })

  it('shows a read-only checklist without inputs', async () => {
    const saved = emptyState(TODAY)
    saved.answers['assessment.documents'] = 'no'
    saved.remarks['assessment.documents'] = 'Parts list missing'
    const { wrapper, state } = await mountEditor({ state: saved, readOnly: true })

    await click(wrapper, 'cl-section-toggle-assessment')
    const answer = wrapper.get('[data-testid="cl-answer-assessment.documents-yes"]')
    expect(answer.attributes('disabled')).toBeDefined()
    await answer.trigger('click')
    expect(state.answers['assessment.documents']).toBe('no')
    expect(wrapper.find('[data-testid="cl-header-designation"]').exists()).toBe(false)
    expect(text(wrapper, 'cl-header')).toContain('Press 12')
    expect(wrapper.find('[data-testid="cl-remark-assessment.documents"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="cl-remark-toggle-assessment.documents"]').exists()).toBe(false)
    expect(text(wrapper, 'cl-item-assessment.documents')).toContain('Parts list missing')

    wrapper.unmount()
  })

  it('filters the list down to findings', async () => {
    const { wrapper } = await mountEditor()
    await click(wrapper, 'cl-section-toggle-assessment')
    await click(wrapper, 'cl-answer-assessment.documents-no')

    await chooseFilter(wrapper, 'problems')

    expect(wrapper.get('[data-testid="cl-item-assessment.documents"]').isVisible()).toBe(true)
    expect(wrapper.get('[data-testid="cl-item-assessment.circuitFunctions"]').isVisible()).toBe(false)
    expect(wrapper.get('[data-testid="cl-section-circuit"]').isVisible()).toBe(false)

    await click(wrapper, 'cl-answer-assessment.documents-no')
    expect(wrapper.find('[data-testid="cl-no-matches"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('marks the items changed since the revision before and filters on them', async () => {
    const changed = new Set(['assessment.circuitFunctions'])
    const { wrapper } = await mountEditor({ changedIds: changed })

    expect(text(wrapper, 'cl-section-toggle-assessment')).toContain('Changed: 1')
    await chooseFilter(wrapper, 'changes')

    expect(wrapper.get('[data-testid="cl-changed-assessment.circuitFunctions"]').text()).toBe('Changed')
    expect(wrapper.get('[data-testid="cl-item-assessment.circuitFunctions"]').isVisible()).toBe(true)
    expect(wrapper.get('[data-testid="cl-item-assessment.documents"]').isVisible()).toBe(false)
    expect(wrapper.get('[data-testid="cl-section-circuit"]').isVisible()).toBe(false)

    wrapper.unmount()
  })

  it('offers the changes filter only when something changed', async () => {
    const { wrapper } = await mountEditor()
    const filter = wrapper.findAllComponents({ name: 'SelectButton' }).find((c) => c.attributes('data-testid') === 'cl-filter')
    if (!filter) throw new Error('no filter')
    const values = (filter.props('options') as { value: string }[]).map((option) => option.value)
    expect(values).toEqual(['all', 'unanswered', 'problems'])
    wrapper.unmount()
  })

  it('shows the verification methods of the robotics list', async () => {
    const { wrapper } = await mountEditor({ definition: CHECKLISTS.robotics })
    expect(wrapper.find('[data-testid="cl-methods-legend"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('puts result, data and methods beside the checklist card, without the title card', async () => {
    const { wrapper } = await mountEditor({ definition: CHECKLISTS.robotics })
    const side = wrapper.get('[data-testid="cl-side"]')
    expect(side.find('[data-testid="cl-summary"]').exists()).toBe(true)
    expect(side.find('[data-testid="cl-methods-legend"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="cl-list"]').find('[data-testid="cl-filter"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cl-title"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
