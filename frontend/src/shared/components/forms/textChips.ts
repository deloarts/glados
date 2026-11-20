/**
 * The values of a free-text chip input in the order given, each trimmed,
 * without empty ones and without repeats in another case, the first spelling
 * kept. The backend applies the same rule to the supplier order numbers of an
 * order on save.
 */
export function normaliseChips(values: readonly string[]): string[] {
  const seen = new Set<string>()
  const chips: string[] = []
  for (const value of values) {
    const chip = value.trim()
    const key = chip.toLocaleLowerCase()
    if (!chip || seen.has(key)) continue
    seen.add(key)
    chips.push(chip)
  }
  return chips
}
