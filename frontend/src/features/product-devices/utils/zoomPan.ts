/**
 * The arithmetic of the device overview canvas: an image of `width` ×
 * `height` pixels drawn at `scale` and shifted by (`x`, `y`) inside a
 * viewport. Kept pure so the zoom and click mapping are testable without a
 * browser layout.
 */

export interface View {
  scale: number
  x: number
  y: number
}

export interface Size {
  width: number
  height: number
}

/** Margin left around the image when it is fitted, as a share of the viewport. */
const FIT_MARGIN = 0.04

/** The view that shows the whole image centred in the viewport. */
export function fitView(image: Size, viewport: Size): View {
  if (image.width <= 0 || image.height <= 0 || viewport.width <= 0 || viewport.height <= 0) {
    return { scale: 1, x: 0, y: 0 }
  }
  const scale =
    Math.min(viewport.width / image.width, viewport.height / image.height) * (1 - FIT_MARGIN)
  return {
    scale,
    x: (viewport.width - image.width * scale) / 2,
    y: (viewport.height - image.height * scale) / 2,
  }
}

/**
 * The zoom range: from half the fitted size up to twenty times it, and at
 * least to the image's own pixels at four times.
 */
export function scaleLimits(fitScale: number): { min: number; max: number } {
  return { min: fitScale / 2, max: Math.max(fitScale * 20, 4) }
}

/**
 * The view zoomed by `factor` around the viewport point (`px`, `py`), which
 * stays over the same image point. The scale is clamped to `limits`.
 */
export function zoomAt(
  view: View,
  factor: number,
  px: number,
  py: number,
  limits: { min: number; max: number },
): View {
  const scale = Math.min(limits.max, Math.max(limits.min, view.scale * factor))
  const k = scale / view.scale
  return { scale, x: px - (px - view.x) * k, y: py - (py - view.y) * k }
}

/**
 * The image position, normalised to 0..1, under the viewport point. Null
 * when the point lies outside the image.
 */
export function toImagePoint(
  view: View,
  image: Size,
  px: number,
  py: number,
): { x: number; y: number } | null {
  const x = (px - view.x) / view.scale / image.width
  const y = (py - view.y) / view.scale / image.height
  if (x < 0 || x > 1 || y < 0 || y > 1) return null
  return { x, y }
}

/**
 * The view that puts the normalised image point (`nx`, `ny`) into the
 * middle of the viewport at the given scale.
 */
export function centreOn(
  image: Size,
  viewport: Size,
  nx: number,
  ny: number,
  scale: number,
): View {
  return {
    scale,
    x: viewport.width / 2 - nx * image.width * scale,
    y: viewport.height / 2 - ny * image.height * scale,
  }
}

/** The base spacing of the background dot grid, in screen pixels at the fitted size. */
const GRID_BASE_PX = 24

/**
 * The dot grid's spacing and offset in screen pixels for the view, so the
 * grid moves with the image like an editor's canvas. The spacing follows the
 * zoom but is halved or doubled to stay between 12 and 48 pixels, which
 * keeps the dots neither crowded nor sparse at any zoom. The offset lies in
 * 0..spacing, ready to shift a grid layer that starts one spacing before the
 * viewport.
 */
export function gridLayout(view: View, fitScale: number): { step: number; x: number; y: number } {
  let step = GRID_BASE_PX * (fitScale > 0 ? view.scale / fitScale : 1)
  while (step < GRID_BASE_PX / 2) step *= 2
  while (step > GRID_BASE_PX * 2) step /= 2
  const wrap = (value: number) => ((value % step) + step) % step
  return { step, x: wrap(view.x), y: wrap(view.y) }
}
