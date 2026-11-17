import { describe, it, expect, afterEach } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import { mountWithApp } from '@/test-utils/mountWithApp'
import AppGanttChart from '../AppGanttChart.vue'

const task = {
  id: 1,
  text: 'Lot 1',
  start: new Date(2026, 0, 5),
  end: new Date(2026, 0, 9),
  type: 'task',
}

describe('AppGanttChart', () => {
  let wrapper: VueWrapper | undefined

  afterEach(() => {
    wrapper?.unmount()
    wrapper = undefined
  })

  // The SVAR themes link their icon font and Open Sans from cdn.svar.dev
  // unless told not to, which would send every viewer's address to a third
  // party. The chart ships the icon font itself instead. The theme alone
  // injects the links, so the gantt inside it, which needs a real layout
  // engine, is stubbed.
  it('adds nothing to the document head that loads from a third-party server', () => {
    wrapper = mountWithApp(AppGanttChart, {
      props: { tasks: [task] },
      attachTo: document.body,
      global: { stubs: { GanttComponentsGantt: true } },
    })

    expect(wrapper.find('.wx-willow-theme').exists()).toBe(true)
    const external = [...document.head.querySelectorAll('link, style')].filter((node) =>
      (node.outerHTML + node.textContent).includes('cdn.svar.dev'),
    )
    expect(external).toEqual([])
  })
})
