export type DiffLineKind = 'same' | 'added' | 'removed'

export interface DiffLine {
  kind: DiffLineKind
  text: string
}

/**
 * The lines of `before` and `after` as one list, each kept, added or
 * removed, from their longest common subsequence. Card bodies are short, so
 * the quadratic table is fine.
 */
export function lineDiff(before: string, after: string): DiffLine[] {
  const a = before ? before.split('\n') : []
  const b = after ? after.split('\n') : []
  const table: number[][] = Array.from({ length: a.length + 1 }, () => Array.from({ length: b.length + 1 }, () => 0))
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      const row = table[i] as number[]
      row[j] =
        a[i] === b[j]
          ? (table[i + 1]?.[j + 1] ?? 0) + 1
          : Math.max(table[i + 1]?.[j] ?? 0, row[j + 1] ?? 0)
    }
  }
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: 'same', text: a[i] as string })
      i += 1
      j += 1
    } else if ((table[i + 1]?.[j] ?? 0) >= (table[i]?.[j + 1] ?? 0)) {
      out.push({ kind: 'removed', text: a[i] as string })
      i += 1
    } else {
      out.push({ kind: 'added', text: b[j] as string })
      j += 1
    }
  }
  while (i < a.length) out.push({ kind: 'removed', text: a[i++] as string })
  while (j < b.length) out.push({ kind: 'added', text: b[j++] as string })
  return out
}
