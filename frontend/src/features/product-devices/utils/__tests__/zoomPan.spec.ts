import { describe, expect, it } from 'vitest'

import { centreOn, fitView, gridLayout, scaleLimits, toImagePoint, zoomAt } from '../zoomPan'

const image = { width: 4000, height: 2000 }
const viewport = { width: 1000, height: 800 }

describe('zoomPan', () => {
  it('fits a large image into the viewport and centres it', () => {
    const view = fitView(image, viewport)
    expect(view.scale).toBeCloseTo(0.24)
    expect(view.x).toBeCloseTo(20)
    expect(view.y).toBeCloseTo(160)
  })

  it('keeps the image point under the cursor while zooming', () => {
    const view = fitView(image, viewport)
    const before = toImagePoint(view, image, 300, 400)!
    const zoomed = zoomAt(view, 3, 300, 400, scaleLimits(view.scale))
    const after = toImagePoint(zoomed, image, 300, 400)!
    expect(zoomed.scale).toBeCloseTo(view.scale * 3)
    expect(after.x).toBeCloseTo(before.x)
    expect(after.y).toBeCloseTo(before.y)
  })

  it('clamps the zoom to its limits', () => {
    const view = fitView(image, viewport)
    const limits = scaleLimits(view.scale)
    expect(zoomAt(view, 1000, 0, 0, limits).scale).toBe(limits.max)
    expect(zoomAt(view, 0.001, 0, 0, limits).scale).toBe(limits.min)
  })

  it('maps a click to a normalised image point, null outside the image', () => {
    const view = { scale: 0.5, x: 100, y: 50 }
    expect(toImagePoint(view, image, 100 + 1000, 50 + 500)).toEqual({ x: 0.5, y: 0.5 })
    expect(toImagePoint(view, image, 50, 50)).toBeNull()
  })

  it('centres a marker in the viewport', () => {
    const view = centreOn(image, viewport, 0.25, 0.75, 1)
    expect(toImagePoint(view, image, 500, 400)).toEqual({ x: 0.25, y: 0.75 })
  })

  it('keeps the dot grid spacing readable and moving with the image', () => {
    expect(gridLayout({ scale: 0.5, x: 0, y: 0 }, 0.5).step).toBe(24)
    expect(gridLayout({ scale: 1.5, x: 0, y: 0 }, 0.5).step).toBe(36)
    expect(gridLayout({ scale: 0.1, x: 0, y: 0 }, 0.5).step).toBeGreaterThanOrEqual(12)
    expect(gridLayout({ scale: 50, x: 0, y: 0 }, 0.5).step).toBeLessThanOrEqual(48)
    const layout = gridLayout({ scale: 0.5, x: 50, y: -10 }, 0.5)
    expect(layout.x).toBe(2)
    expect(layout.y).toBe(14)
  })
})
