import { describe, it, expect } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import LotDetailHeader from '../LotDetailHeader.vue'
import { lotActions } from '../../../__tests__/fixtures'
import type { LotStatus } from '../../../../types/productionLotsResponse'

// The actions default to what the backend offers a manager of lots on a lot
// in that status that produced something.
function mountHeader(props: {
  status: LotStatus
  actions?: string[]
  blockedActions?: Record<string, string>
  canWrite?: boolean
  canManage?: boolean
  manageMode?: boolean
  canPrint?: boolean
  hasScrap?: boolean
}) {
  return mountWithApp(LotDetailHeader, {
    props: {
      stateSignals: [],
      canWrite: true,
      canManage: true,
      manageMode: false,
      actions: lotActions(props.status, 1),
      ...props,
    },
  })
}

function findButton(wrapper: VueWrapper, matcher: RegExp) {
  return wrapper.findAll('button').find((b) => matcher.test(b.text()))
}

describe('LotDetailHeader', () => {
  it('shows Hold only for a plannable/in-progress lot', () => {
    const planned = mountHeader({ status: 'planned' })
    expect(findButton(planned, /hold/i)).toBeTruthy()

    const completed = mountHeader({ status: 'completed' })
    expect(findButton(completed, /hold/i)).toBeUndefined()
  })

  it('shows Resume only when the lot is on hold', () => {
    const onHold = mountHeader({ status: 'on_hold' })
    expect(findButton(onHold, /resume/i)).toBeTruthy()

    const inProgress = mountHeader({ status: 'in_progress' })
    expect(findButton(inProgress, /resume/i)).toBeUndefined()
  })

  it('hides Complete/Cancel once the lot is already completed or canceled', () => {
    const completed = mountHeader({ status: 'completed' })
    expect(findButton(completed, /complete/i)).toBeUndefined()
    expect(findButton(completed, /cancel/i)).toBeUndefined()

    const inProgress = mountHeader({ status: 'in_progress' })
    expect(findButton(inProgress, /complete/i)).toBeTruthy()
    expect(findButton(inProgress, /cancel/i)).toBeTruthy()
  })

  it('offers no Complete or Cancel the lot does not offer, as to a non-manager', () => {
    const wrapper = mountHeader({ status: 'in_progress', actions: ['hold', 'scrap'] })

    expect(findButton(wrapper, /complete/i)).toBeUndefined()
    expect(findButton(wrapper, /cancel/i)).toBeUndefined()
    expect(findButton(wrapper, /hold/i)).toBeTruthy()
  })

  it('shows the Complete and Cancel a lot blocks disabled, naming manage:lots', () => {
    // A non-manager of lots gets the force actions the state allows as
    // blocked, so they stay visible and say what is missing.
    const wrapper = mountHeader({
      status: 'in_progress',
      actions: ['hold', 'scrap'],
      blockedActions: { force_complete: 'manage:lots' },
      canManage: false,
    })

    const complete = findButton(wrapper, /complete/i)
    expect(complete?.attributes('disabled')).toBeDefined()
    const span = complete?.element.parentElement as
      | (HTMLElement & { $_ptooltipValue?: string })
      | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Manage Production Lots.')
    // The state refuses the cancel, so it is neither allowed nor blocked.
    expect(findButton(wrapper, /cancel/i)).toBeUndefined()
  })

  it('shows the Manage toggle disabled with the missing permission for a user without write access', () => {
    const wrapper = mountHeader({ status: 'in_progress', canWrite: false })

    const manage = wrapper.get('[data-testid="lot-header-manage-toggle"]')
    expect(manage.attributes('disabled')).toBeDefined()
    const span = manage.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Production Lots.')
  })

  it('emits toggle-manage when the Manage button is clicked', async () => {
    const wrapper = mountHeader({ status: 'in_progress' })

    await findButton(wrapper, /manage/i)!.trigger('click')

    expect(wrapper.emitted('toggle-manage')).toHaveLength(1)
  })

  it('emits open-hold, resume, and open-force-status with the right action', async () => {
    const holdable = mountHeader({ status: 'planned' })
    await findButton(holdable, /hold/i)!.trigger('click')
    expect(holdable.emitted('open-hold')).toHaveLength(1)

    const onHold = mountHeader({ status: 'on_hold' })
    await findButton(onHold, /resume/i)!.trigger('click')
    expect(onHold.emitted('resume')).toHaveLength(1)

    const wrapper = mountHeader({ status: 'in_progress' })
    await findButton(wrapper, /complete/i)!.trigger('click')
    await findButton(wrapper, /cancel/i)!.trigger('click')
    expect(wrapper.emitted('open-force-status')).toEqual([['complete'], ['cancel']])
  })

  it('prints the docket from the split button itself and only for a user who may print', async () => {
    const withoutPrint = mountHeader({ status: 'in_progress' })
    expect(findButton(withoutPrint, /print docket/i)).toBeUndefined()

    const wrapper = mountHeader({ status: 'in_progress', canPrint: true })
    const printButton = findButton(wrapper, /print docket/i)
    expect(printButton).toBeTruthy()

    await printButton!.trigger('click')

    expect(wrapper.emitted('print')).toEqual([['lot_docket']])
  })

  it('offers the label and the scrap tag in the dropdown, scrap tag only once something was scrapped', async () => {
    const wrapper = mountHeader({ status: 'in_progress', canPrint: true, hasScrap: false })

    const dropdown = wrapper
      .findAll('button')
      .find((b) => b.attributes('aria-haspopup') === 'true' || /menu/i.test(b.attributes('aria-label') ?? ''))
    expect(dropdown).toBeTruthy()
    await dropdown!.trigger('click')
    await flushPromises()

    const items = document.body.querySelectorAll('[role="menuitem"]')
    const labels = [...items].map((el) => el.textContent?.trim())
    expect(labels).toEqual([
      i18n.global.t('production.lots.detail.print.label'),
      i18n.global.t('production.lots.detail.print.docket'),
      i18n.global.t('production.lots.detail.print.scrapTag'),
      i18n.global.t('production.lots.report.print'),
    ])
    const scrapItem = [...items].find((el) =>
      el.textContent?.includes(i18n.global.t('production.lots.detail.print.scrapTag')),
    )
    expect(scrapItem?.getAttribute('aria-disabled') ?? scrapItem?.className).toMatch(/true|disabled/)

    wrapper.unmount()
  })

  it('offers the inspection report without the print permission, since it downloads as well', async () => {
    const wrapper = mountHeader({ status: 'in_progress', canPrint: false, hasScrap: false })

    await wrapper.get('[data-testid="lot-inspection-report"]').trigger('click')

    expect(wrapper.emitted('report')).toHaveLength(1)
    wrapper.unmount()
  })
})
