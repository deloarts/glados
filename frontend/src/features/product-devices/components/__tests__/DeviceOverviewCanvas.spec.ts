import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import DeviceOverviewCanvas from '../DeviceOverviewCanvas.vue'

// jsdom lays nothing out: the viewport measures 0 × 0 and an image has no
// natural size, so the canvas works on its 1000 × 1000 fallback at scale 1
// with the image at the viewport's origin.
// Every canvas is unmounted after its test, which clears the zoom's settle
// timer; left running, it fires after the file's jsdom environment is gone.
const mounted: VueWrapper[] = []

async function mountCanvas(placing = true) {
  const wrapper = mountWithApp(DeviceOverviewCanvas, {
    props: {
      src: 'blob:overview',
      markers: [{ id: 1, number: 7, x: 0.25, y: 0.5, label: 'B01 Hubzylinder P1', highlighted: false }],
      placing,
    },
  })
  mounted.push(wrapper)
  await wrapper.get('img').trigger('load')
  await flushPromises()
  return wrapper
}

// The wheel and dragging apply the view on the next animation frame.
function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

// jsdom builds pointer events as MouseEvents whose coordinates cannot be
// set after construction, so they are dispatched ready-made.
async function pointer(target: Element, type: string, clientX: number, clientY: number) {
  target.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, clientX, clientY }))
  await nextFrame()
  await flushPromises()
}

describe('DeviceOverviewCanvas', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('shows the device number in the marker', async () => {
    const wrapper = await mountCanvas()
    expect(wrapper.get('[data-testid="device-overview-marker"] .marker-number').text()).toBe('7')
  })

  it('places a marker where a click lands on the image', async () => {
    const wrapper = await mountCanvas()
    const viewport = wrapper.get('[data-testid="device-overview-image"]')
    await pointer(viewport.element, 'pointerdown', 500, 250)
    await pointer(viewport.element, 'pointerup', 500, 250)
    expect(wrapper.emitted('place')).toEqual([[{ x: 0.5, y: 0.25 }]])
  })

  it('moves the image on a drag instead of placing a marker', async () => {
    const wrapper = await mountCanvas()
    const viewport = wrapper.get('[data-testid="device-overview-image"]')
    await pointer(viewport.element, 'pointerdown', 500, 250)
    await pointer(viewport.element, 'pointermove', 560, 300)
    await pointer(viewport.element, 'pointerup', 560, 300)
    expect(wrapper.emitted('place')).toBeUndefined()
    expect(wrapper.get('.overview-stage').attributes('style')).toContain('translate(60px, 50px)')
  })

  it('does not place a marker while placing is off', async () => {
    const wrapper = await mountCanvas(false)
    const viewport = wrapper.get('[data-testid="device-overview-image"]')
    await pointer(viewport.element, 'pointerdown', 500, 250)
    await pointer(viewport.element, 'pointerup', 500, 250)
    expect(wrapper.emitted('place')).toBeUndefined()
  })

  it('zooms with the wheel and the buttons', async () => {
    const wrapper = await mountCanvas()
    const zoom = () => wrapper.get('[data-testid="device-overview-zoom"]').text()
    expect(zoom()).toBe('100 %')
    await wrapper.get('[data-testid="device-overview-image"]').trigger('wheel', { deltaY: -500 })
    await nextFrame()
    await flushPromises()
    expect(Number.parseInt(zoom())).toBeGreaterThan(100)
    await wrapper.get('[aria-label="Fit to view"]').trigger('click')
    expect(zoom()).toBe('100 %')
  })

  it('shows a marker name only while the marker is highlighted', async () => {
    const wrapper = await mountCanvas()
    expect(wrapper.text()).not.toContain('B01 Hubzylinder P1')
    await wrapper.setProps({
      markers: [{ id: 1, number: 7, x: 0.25, y: 0.5, label: 'B01 Hubzylinder P1', highlighted: true }],
    })
    expect(wrapper.text()).toContain('B01 Hubzylinder P1')
  })

  it('shows a card with name, type and image per marker in the detailed view', async () => {
    const wrapper = await mountCanvas()
    await wrapper.setProps({
      detailed: true,
      markers: [
        {
          id: 1,
          number: 7,
          x: 0.25,
          y: 0.5,
          label: 'B01 Hubzylinder P1',
          highlighted: false,
          typeLabel: 'Linear drive | Pneumatics',
          imageUrl: 'blob:rendering',
        },
      ],
    })
    const card = wrapper.get('[data-testid="device-overview-card"]')
    expect(card.text()).toContain('B01 Hubzylinder P1')
    expect(card.text()).toContain('Linear drive | Pneumatics')
    expect(card.get('img').attributes('src')).toBe('blob:rendering')
  })

  it('folds several wheel events in one frame into one view update', async () => {
    const wrapper = await mountCanvas()
    const viewport = wrapper.get('[data-testid="device-overview-image"]')
    await viewport.trigger('wheel', { deltaY: -200 })
    await viewport.trigger('wheel', { deltaY: -200 })
    expect(wrapper.get('[data-testid="device-overview-zoom"]').text()).toBe('100 %')
    await nextFrame()
    await flushPromises()
    expect(wrapper.get('[data-testid="device-overview-zoom"]').text()).toBe(
      `${Math.round(Math.exp(0.6) * 100)} %`,
    )
  })

  it('places the markers in a layer that follows the view without scaling', async () => {
    const wrapper = await mountCanvas()
    const viewport = wrapper.get('[data-testid="device-overview-image"]')
    await pointer(viewport.element, 'pointerdown', 500, 250)
    await pointer(viewport.element, 'pointermove', 560, 300)
    const layer = wrapper.get('.overview-markers').attributes('style')
    expect(layer).toContain('--view-x: 60px')
    expect(layer).toContain('--view-width: 1000px')
    expect(wrapper.get('[data-testid="device-overview-marker"]').attributes('style')).toContain(
      '--marker-x: 0.25',
    )
  })

  it('switches the dot grid off and on and remembers the choice', async () => {
    localStorage.removeItem('glados.productDevices.overviewGrid')
    const wrapper = await mountCanvas()
    expect(wrapper.find('[data-testid="device-overview-grid"]').exists()).toBe(true)
    await wrapper.get('[data-testid="device-overview-grid-toggle"]').trigger('click')
    expect(wrapper.find('[data-testid="device-overview-grid"]').exists()).toBe(false)
    expect(localStorage.getItem('glados.productDevices.overviewGrid')).toBe('false')
    const again = await mountCanvas()
    expect(again.find('[data-testid="device-overview-grid"]').exists()).toBe(false)
    localStorage.removeItem('glados.productDevices.overviewGrid')
  })
})
