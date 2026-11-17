import { describe, it, expect } from 'vitest'

import { buildImportGraph, crossFeatureModuleCycles, cyclicFeatureEdges, featureEdges } from './featureImportGraph'

/**
 * Architecture guard for imports between features. Two rules:
 *
 * No module cycle may span two features. A feature barrel re-exports
 * components, so importing it evaluates everything it re-exports. When a
 * module reached from one barrel imports a second barrel that leads back to
 * the first, module evaluation order depends on which feature loads first.
 * This rule has no allowlist.
 *
 * Feature-level cycles, where features depend on each other through any
 * import including `import type`, are allowed only as listed below. A new
 * cycle fails, and an entry that no longer lies on a cycle fails too, so the
 * list only shrinks. Break a cycle by moving the shared piece to `shared/`
 * or to the feature that owns it.
 */

// Feature pairs that import each other, with the reason the dependency runs
// both ways.
const ALLOWED_MUTUAL_IMPORTS: Record<string, string> = {}

// Single-direction edges that close a longer cycle through the pairs above.
// They are listed so that a new edge inside the tangle fails as well.
const ALLOWED_CYCLIC_EDGES: Record<string, string> = {}

function allowedEdges(): Set<string> {
  const edges = new Set(Object.keys(ALLOWED_CYCLIC_EDGES))
  for (const pair of Object.keys(ALLOWED_MUTUAL_IMPORTS)) {
    const [a, b] = pair.split(' <-> ')
    edges.add(`${a} -> ${b}`)
    edges.add(`${b} -> ${a}`)
  }
  return edges
}

describe('feature import cycles', () => {
  const graph = buildImportGraph()

  it('has no module cycle that spans two features', () => {
    expect(crossFeatureModuleCycles(graph)).toEqual([])
  })

  it('has no feature-level cycle outside the allowlist', () => {
    const allowed = allowedEdges()
    const unexpected = cyclicFeatureEdges(graph).filter((edge) => !allowed.has(edge))
    expect(unexpected).toEqual([])
  })

  it('keeps no allowlist entry that is no longer on a cycle', () => {
    const cyclic = new Set(cyclicFeatureEdges(graph))
    const stale = [...allowedEdges()].filter((edge) => !cyclic.has(edge)).sort()
    expect(stale).toEqual([])
  })

  it('lists as mutual only pairs that still import each other', () => {
    const edges = featureEdges(graph)
    const oneWay = Object.keys(ALLOWED_MUTUAL_IMPORTS).filter((pair) => {
      const [a, b] = pair.split(' <-> ')
      return !edges.has(`${a} -> ${b}`) || !edges.has(`${b} -> ${a}`)
    })
    expect(oneWay).toEqual([])
  })
})
