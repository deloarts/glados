// Duplicate-detection canonicalization for source item dimensions. Accepts
// an ASCII "x" and a lowercase "ø" as well. Only a box's three numbers are
// permutation-equivalent; other shapes only get number normalization.
//
// Must agree exactly with backend/src/modules/catalogue/domain/services/dimension_spec.py, or
// the duplicate warning and the backend's 409 disagree.

const NUMBER = String.raw`-?\d+(?:\.\d+)?`
const SEP = String.raw`\s*[×xX*]\s*`
const DIA = `[Øø]`

const HOLLOW_ROD_RE = new RegExp(`^${DIA}(${NUMBER})${SEP}(${NUMBER})${SEP}(${NUMBER})$`)
const ROD_RE = new RegExp(`^${DIA}(${NUMBER})${SEP}(${NUMBER})$`)
const HOLLOW_BOX_RE = new RegExp(`^(${NUMBER})${SEP}(${NUMBER})${SEP}(${NUMBER})${SEP}(${NUMBER})$`)
const BOX_RE = new RegExp(`^(${NUMBER})${SEP}(${NUMBER})${SEP}(${NUMBER})$`)

// String surgery, so no float round trip can drift.
function normalizeNumber(raw: string): string {
  if (!raw.includes('.')) return raw
  const stripped = raw.replace(/0+$/, '')
  return stripped.endsWith('.') ? stripped.slice(0, -1) : stripped
}

export function canonicalizeDimension(dimension: string | null | undefined): string | null {
  if (dimension == null) return null
  const trimmed = dimension.trim().replace(/\s+/g, ' ')
  if (trimmed === '') return null

  const hollowRod = HOLLOW_ROD_RE.exec(trimmed)
  if (hollowRod) {
    const [a, b, c] = [hollowRod[1]!, hollowRod[2]!, hollowRod[3]!].map(normalizeNumber)
    return `Ø${a} × ${b} × ${c}`
  }

  const rod = ROD_RE.exec(trimmed)
  if (rod) {
    const [a, b] = [rod[1]!, rod[2]!].map(normalizeNumber)
    return `Ø${a} × ${b}`
  }

  const hollowBox = HOLLOW_BOX_RE.exec(trimmed)
  if (hollowBox) {
    const [a, b, c, d] = [hollowBox[1]!, hollowBox[2]!, hollowBox[3]!, hollowBox[4]!].map(
      normalizeNumber,
    )
    return `${a} × ${b} × ${c} × ${d}`
  }

  const box = BOX_RE.exec(trimmed)
  if (box) {
    const numbers = [box[1]!, box[2]!, box[3]!].map(normalizeNumber)
    numbers.sort((x, y) => Number.parseFloat(y) - Number.parseFloat(x))
    return numbers.join(' × ')
  }

  return trimmed
}

export function areDimensionsEquivalent(
  a: string | null | undefined,
  b: string | null | undefined,
): boolean {
  return canonicalizeDimension(a) === canonicalizeDimension(b)
}

/** The four structured shapes SourceItemDimensionInput.vue can produce. */
export type DimensionShape = 'box' | 'hollow-box' | 'rod' | 'hollow-rod'

/**
 * Classifies a dimension into a structured shape with the same regexes as
 * canonicalizeDimension, or null for anything else. Picks the placeholder
 * for items without files.
 */
export function detectDimensionShape(dimension: string | null | undefined): DimensionShape | null {
  if (dimension == null) return null
  const trimmed = dimension.trim().replace(/\s+/g, ' ')
  if (trimmed === '') return null

  if (HOLLOW_ROD_RE.test(trimmed)) return 'hollow-rod'
  if (ROD_RE.test(trimmed)) return 'rod'
  if (HOLLOW_BOX_RE.test(trimmed)) return 'hollow-box'
  if (BOX_RE.test(trimmed)) return 'box'
  return null
}
