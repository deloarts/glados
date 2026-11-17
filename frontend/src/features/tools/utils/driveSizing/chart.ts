import type { FormulaSymbol } from './display'

/**
 * Tick values for a chart axis: steps of 1, 2 or 5 times a power of ten,
 * about `target` of them across the range, always including zero when the
 * range contains it.
 */
export function niceTicks(min: number, max: number, target = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [min]
  const rough = (max - min) / Math.max(1, target)
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step =
    [1, 2, 5, 10].map((factor) => factor * magnitude).find((candidate) => candidate >= rough) ?? rough
  const ticks: number[] = []
  for (let value = Math.ceil(min / step) * step; value <= max + step * 1e-9; value += step) {
    ticks.push(Math.abs(value) < step * 1e-9 ? 0 : Number(value.toPrecision(12)))
  }
  return ticks
}

/** A horizontal line for a limit or a characteristic value, labelled with its symbol. */
export interface ChartReference {
  value: number
  symbol: FormulaSymbol
  tone: 'limit' | 'rated' | 'mean'
}

/** The drawing box of a chart in SVG units, the plot inside the margins for the labels. */
export const CHART_BOX = { width: 640, height: 240, left: 52, right: 64, top: 16, bottom: 30 } as const

export const CHART_PLOT = {
  width: CHART_BOX.width - CHART_BOX.left - CHART_BOX.right,
  height: CHART_BOX.height - CHART_BOX.top - CHART_BOX.bottom,
} as const

export interface ChartLayout {
  x: (time: number) => number
  y: (value: number) => number
  xTicks: number[]
  yTicks: number[]
  /** The curve as an SVG path. */
  line: string
  /** The area between the curve and zero. */
  area: string
  /** Reference labels, pushed apart where they would overlap. */
  labels: Array<{ reference: ChartReference; y: number }>
}

// Labels of reference lines that lie close together, such as the rated and
// the RMS torque, are pushed apart so they never print over each other.
const LABEL_GAP = 14

/**
 * Where everything of a chart goes, shared by the chart on the page and the
 * one in the PDF report. Zero always sits inside the plot, and the range is
 * padded so neither the curve nor a reference line touches the frame.
 */
export function chartLayout(
  points: ReadonlyArray<readonly [number, number]>,
  duration: number,
  references: readonly ChartReference[] = [],
): ChartLayout {
  const values = [0, ...points.map(([, value]) => value), ...references.map((reference) => reference.value)]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = (max - min || 1) * 0.08
  const lo = min < 0 ? min - pad : 0
  const hi = max > 0 ? max + pad : lo === 0 ? 1 : 0
  const span = duration > 0 ? duration : 1
  const x = (time: number) => CHART_BOX.left + (time / span) * CHART_PLOT.width
  const y = (value: number) => CHART_BOX.top + ((hi - value) / (hi - lo)) * CHART_PLOT.height

  const line = points
    .map(([time, value], i) => `${i === 0 ? 'M' : 'L'}${x(time).toFixed(1)} ${y(value).toFixed(1)}`)
    .join(' ')
  const first = points[0]
  const last = points[points.length - 1]
  const zero = y(0).toFixed(1)
  const area =
    first && last ? `${line} L${x(last[0]).toFixed(1)} ${zero} L${x(first[0]).toFixed(1)} ${zero} Z` : ''

  const labels = references
    .map((reference) => ({ reference, y: y(reference.value) + 4 }))
    .sort((a, b) => a.y - b.y)
  labels.forEach((label, i) => {
    const above = labels[i - 1]
    if (above && label.y - above.y < LABEL_GAP) label.y = above.y + LABEL_GAP
  })

  return { x, y, xTicks: niceTicks(0, span, 8), yTicks: niceTicks(lo, hi, 5), line, area, labels }
}
