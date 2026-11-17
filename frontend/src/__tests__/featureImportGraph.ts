import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import ts from 'typescript'

/**
 * Builds the import graph of `src/` from the source files themselves, so the
 * architecture spec can find import cycles between features without a lint
 * plugin. Specs and test helpers are left out because they never ship.
 *
 * An edge is `type` when the whole declaration is `import type` or
 * `export type`, which the compiler erases. With `verbatimModuleSyntax`, an
 * import whose named specifiers are all inline `type` still survives as a
 * bare side-effect import, so it counts as a static runtime edge. A dynamic
 * `import()` loads lazily and cannot take part in an evaluation-order cycle.
 */

export type EdgeKind = 'static' | 'type' | 'dynamic'

export interface ImportEdge {
  from: string
  to: string
  kind: EdgeKind
}

const SRC_ROOT = resolve(__dirname, '..')
const SKIPPED_DIRS = new Set(['__tests__', 'test-utils', 'generated', 'locales'])
const SOURCE_FILE = /\.(ts|vue)$/
const VUE_SCRIPT = /<script\b[^>]*>([\s\S]*?)<\/script>/g

function collectSourceFiles(dir: string): string[] {
  const files: string[] = []
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry)
    if (statSync(fullPath).isDirectory()) {
      if (!SKIPPED_DIRS.has(entry)) files.push(...collectSourceFiles(fullPath))
    } else if (SOURCE_FILE.test(entry) && !entry.endsWith('.d.ts') && !entry.endsWith('.spec.ts')) {
      files.push(fullPath)
    }
  }
  return files
}

function scriptSource(file: string): string {
  const text = readFileSync(file, 'utf8')
  if (!file.endsWith('.vue')) return text
  return [...text.matchAll(VUE_SCRIPT)].map((match) => match[1] ?? '').join('\n')
}

function resolveSpecifier(fromFile: string, specifier: string): string | null {
  let base: string
  if (specifier.startsWith('@/')) base = join(SRC_ROOT, specifier.slice(2))
  else if (specifier.startsWith('.')) base = resolve(dirname(fromFile), specifier)
  else return null
  const candidates = [base, `${base}.ts`, `${base}.vue`, join(base, 'index.ts')]
  for (const candidate of candidates) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate
  }
  return null
}

function isTypeOnlyImport(node: ts.ImportDeclaration): boolean {
  return node.importClause?.isTypeOnly === true
}

function importsOf(file: string): { specifier: string; kind: EdgeKind }[] {
  const source = ts.createSourceFile(file, scriptSource(file), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const found: { specifier: string; kind: EdgeKind }[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      found.push({ specifier: node.moduleSpecifier.text, kind: isTypeOnlyImport(node) ? 'type' : 'static' })
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      found.push({ specifier: node.moduleSpecifier.text, kind: node.isTypeOnly ? 'type' : 'static' })
    } else if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments[0] &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      found.push({ specifier: node.arguments[0].text, kind: 'dynamic' })
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

/** Every resolved in-repo import edge, with paths relative to `src/`. */
export function buildImportGraph(): ImportEdge[] {
  const edges: ImportEdge[] = []
  for (const file of collectSourceFiles(SRC_ROOT)) {
    for (const { specifier, kind } of importsOf(file)) {
      const target = resolveSpecifier(file, specifier)
      if (target) edges.push({ from: relative(SRC_ROOT, file), to: relative(SRC_ROOT, target), kind })
    }
  }
  return edges
}

/** The feature a `src/`-relative path belongs to, or null outside `features/`. */
export function featureOf(path: string): string | null {
  const match = /^features\/([^/]+)\//.exec(path)
  return match?.[1] ?? null
}

/** Strongly connected components with more than one node, each sorted. */
export function cyclicComponents(nodes: Iterable<string>, edges: [string, string][]): string[][] {
  const adjacency = new Map<string, string[]>()
  for (const node of nodes) adjacency.set(node, [])
  for (const [from, to] of edges) adjacency.get(from)?.push(to)

  const index = new Map<string, number>()
  const lowLink = new Map<string, number>()
  const onStack = new Set<string>()
  const stack: string[] = []
  const components: string[][] = []
  let counter = 0

  const strongConnect = (node: string): void => {
    index.set(node, counter)
    lowLink.set(node, counter)
    counter += 1
    stack.push(node)
    onStack.add(node)
    for (const next of adjacency.get(node) ?? []) {
      if (!index.has(next)) {
        strongConnect(next)
        lowLink.set(node, Math.min(lowLink.get(node)!, lowLink.get(next)!))
      } else if (onStack.has(next)) {
        lowLink.set(node, Math.min(lowLink.get(node)!, index.get(next)!))
      }
    }
    if (lowLink.get(node) === index.get(node)) {
      const component: string[] = []
      let member: string | undefined
      do {
        member = stack.pop()!
        onStack.delete(member)
        component.push(member)
      } while (member !== node)
      if (component.length > 1) components.push(component.sort())
    }
  }

  for (const node of adjacency.keys()) {
    if (!index.has(node)) strongConnect(node)
  }
  return components
}

/**
 * Module cycles over static runtime edges that span more than one feature.
 * Such a cycle passes through a feature barrel and makes module evaluation
 * order depend on which side is imported first.
 */
export function crossFeatureModuleCycles(edges: ImportEdge[]): string[][] {
  const runtime = edges.filter((edge) => edge.kind === 'static')
  const nodes = new Set(runtime.flatMap((edge) => [edge.from, edge.to]))
  return cyclicComponents(
    nodes,
    runtime.map((edge) => [edge.from, edge.to]),
  ).filter((component) => new Set(component.map(featureOf).filter(Boolean)).size > 1)
}

/** Feature dependency edges as `a -> b`, counting every import kind. */
export function featureEdges(edges: ImportEdge[]): Set<string> {
  const result = new Set<string>()
  for (const edge of edges) {
    const from = featureOf(edge.from)
    const to = featureOf(edge.to)
    if (from && to && from !== to) result.add(`${from} -> ${to}`)
  }
  return result
}

/** Feature edges that lie on a cycle, that is inside a cyclic component. */
export function cyclicFeatureEdges(edges: ImportEdge[]): string[] {
  const pairs = [...featureEdges(edges)].map((edge) => edge.split(' -> ') as [string, string])
  const nodes = new Set(pairs.flat())
  const componentOf = new Map<string, number>()
  cyclicComponents(nodes, pairs).forEach((component, i) => {
    for (const feature of component) componentOf.set(feature, i)
  })
  return pairs
    .filter(([from, to]) => componentOf.has(from) && componentOf.get(from) === componentOf.get(to))
    .map(([from, to]) => `${from} -> ${to}`)
    .sort()
}
