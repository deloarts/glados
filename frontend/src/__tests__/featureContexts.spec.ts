import { readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, it, expect } from 'vitest'

import { buildImportGraph, featureEdges, featureOf, type ImportEdge } from './featureImportGraph'

/**
 * Architecture guard for the direction of imports between features. Every
 * feature belongs to one bounded context, the same seven the backend is cut
 * into, or to the read tier above them. A feature may import a feature of its
 * own context or of a context its context declares in DEPENDS_ON. The read
 * tier holds cross-context readers and pages that compose several contexts;
 * it may import every context, and nothing outside it imports it. Every
 * import kind counts, including `import type` and a lazy `import()`.
 *
 * Edges against the direction are allowed only as listed in UPWARD_IMPORTS,
 * each with its reason. A new one fails, and an entry that no longer matches
 * such an import fails too, so the list only shrinks. To reach a higher
 * context, let the page that hosts both compose them (a slot, a prop, or a
 * page in the higher feature), let the higher feature register its part
 * through a registry in `shared/` (the account page and the admin settings
 * tabs), or send the notification through `core/realtime` or a store event,
 * and remove the entry. Whether a feature
 * goes through the other feature's barrel is checked by the lint walls in
 * eslint.config.ts, not here.
 */

type Context =
  | 'platform'
  | 'catalogue'
  | 'workspace'
  | 'external-data'
  | 'fulfillment'
  | 'quality'
  | 'operations'
  | 'read'

// The features of each context. The CAD and external data context has no
// feature of its own yet: the PDM preview lives in `shared/pdm-preview` and
// the EPLAN Data Portal dialogs in `bought-items`.
const CONTEXT_FEATURES: Record<Context, string[]> = {
  platform: [
    'account',
    'admin-settings',
    'agents',
    'announcements',
    'auth',
    'holidays',
    'mail',
    'notifications',
    'users',
  ],
  catalogue: [
    'article-groups',
    'bought-items',
    'contacts',
    'customers',
    'fabrication-method-management',
    'fabrication-methods',
    'inspection-methods',
    'made-items',
    'product-families',
    'source-item-types',
    'source-items',
    'suppliers',
  ],
  workspace: ['meetings', 'product-devices', 'products', 'projects'],
  'external-data': [],
  fulfillment: ['buckets', 'orders', 'procurement', 'production', 'production-machines', 'quote-requests'],
  quality: ['checklists', 'print-dockets', 'print-labels', 'printers', 'production-qa', 'sequences', 'tools'],
  operations: ['infoscreens', 'terminals', 'time-tracking'],
  // Cross-context readers (dashboard, search, scan, the to-do list), the
  // handbook, and the pages that compose several contexts: the catalogue item
  // detail pages with their orders, lots and project usage, the catalogue
  // section that hands the item catalogues their order and lot dialogs, the
  // inspection method management page that picks QA machines, the resources
  // section, the production section with its QA tab, and the workspace
  // section with the product and project pages.
  read: [
    'catalogue',
    'catalogue-section',
    'dashboard',
    'handbook',
    'inspection-method-management',
    'production-section',
    'resources',
    'scan',
    'search',
    'todo',
    'workspace',
  ],
}

const ALL_CONTEXTS = Object.keys(CONTEXT_FEATURES) as Context[]

// The contexts each context may import, mirroring the backend's DEPENDS_ON.
// Quality and Operations are siblings and never import each other.
const DEPENDS_ON: Record<Context, Context[]> = {
  platform: [],
  catalogue: ['platform'],
  workspace: ['platform', 'catalogue'],
  'external-data': ['platform', 'catalogue'],
  fulfillment: ['platform', 'catalogue', 'workspace'],
  quality: ['platform', 'catalogue', 'workspace', 'fulfillment'],
  operations: ['platform', 'catalogue', 'fulfillment'],
  read: ALL_CONTEXTS.filter((context) => context !== 'read'),
}

// Feature imports against the declared direction, with the reason each one
// exists today.
const UPWARD_IMPORTS: Record<string, string> = {}

const FEATURES_DIR = resolve(__dirname, '../features')

function contextOf(feature: string): Context | undefined {
  return ALL_CONTEXTS.find((context) => CONTEXT_FEATURES[context].includes(feature))
}

function isAllowed(from: Context, to: Context): boolean {
  if (to === 'read') return from === 'read'
  return from === to || DEPENDS_ON[from].includes(to)
}

/** Feature edges that run against the declared direction, as `a -> b`. */
function upwardEdges(graph: ImportEdge[]): string[] {
  return [...featureEdges(graph)]
    .filter((edge) => {
      const [from, to] = edge.split(' -> ') as [string, string]
      const fromContext = contextOf(from)
      const toContext = contextOf(to)
      return fromContext && toContext && !isAllowed(fromContext, toContext)
    })
    .sort()
}

describe('feature contexts', () => {
  // Built once outside the tests, as the cycles spec does, because a scan of
  // every source file can outlast the per-test timeout under coverage.
  const graph = buildImportGraph()

  it('maps every feature folder to exactly one context', () => {
    const folders = readdirSync(FEATURES_DIR, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
    const mapped = ALL_CONTEXTS.flatMap((context) => CONTEXT_FEATURES[context])

    expect(folders.filter((feature) => !mapped.includes(feature))).toEqual([])
    expect(mapped.filter((feature) => !folders.includes(feature))).toEqual([])
    expect(mapped.filter((feature, i) => mapped.indexOf(feature) !== i)).toEqual([])
  })

  it('declares a dependency graph without cycles', () => {
    const visiting = new Set<Context>()
    const done = new Set<Context>()
    const cycles: string[] = []
    const visit = (context: Context, path: Context[]): void => {
      if (done.has(context)) return
      if (visiting.has(context)) {
        cycles.push([...path, context].join(' -> '))
        return
      }
      visiting.add(context)
      for (const next of DEPENDS_ON[context]) visit(next, [...path, context])
      visiting.delete(context)
      done.add(context)
    }
    for (const context of ALL_CONTEXTS) visit(context, [])
    expect(cycles).toEqual([])
  })

  it('imports features only along declared dependencies or as listed', () => {
    const unexpected = upwardEdges(graph).filter((edge) => !(edge in UPWARD_IMPORTS))
    expect(unexpected).toEqual([])
  })

  it('keeps no allowlist entry that no longer matches an upward import', () => {
    const upward = new Set(upwardEdges(graph))
    const stale = Object.keys(UPWARD_IMPORTS)
      .filter((edge) => !upward.has(edge))
      .sort()
    expect(stale).toEqual([])
  })

  it('keeps core and shared free of feature imports', () => {
    const offending = graph
      .filter((edge) => /^(core|shared)\//.test(edge.from) && featureOf(edge.to) !== null)
      .map((edge) => `${edge.from} -> ${edge.to}`)
    expect(offending).toEqual([])
  })
})
