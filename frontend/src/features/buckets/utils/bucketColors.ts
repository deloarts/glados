/**
 * Palette for new bucket colors. The text color is computed from the
 * background with readableTextColor().
 */
export const BUCKET_COLOR_PALETTE: readonly string[] = [
  '#ef4444', // red
  '#f97316', // orange
  '#eab308', // yellow
  '#22c55e', // green
  '#14b8a6', // teal
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
]

/**
 * Picks the least used palette color, so a new bucket stands out without the
 * user choosing. Ties go to palette order.
 */
export function pickNextColor(existingColors: string[]): string {
  const counts = new Map<string, number>(BUCKET_COLOR_PALETTE.map((color) => [color, 0]))

  for (const color of existingColors) {
    if (counts.has(color)) {
      counts.set(color, (counts.get(color) ?? 0) + 1)
    }
  }

  let best = '#3b82f6'
  let bestCount = Infinity
  for (const color of BUCKET_COLOR_PALETTE) {
    const count = counts.get(color) ?? 0
    if (count < bestCount) {
      bestCount = count
      best = color
    }
  }

  return best
}
