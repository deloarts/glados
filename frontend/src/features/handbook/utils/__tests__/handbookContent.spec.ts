import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import {
  handbookSlugs,
  hasHandbookDoc,
  loadHandbookDoc,
  loadHandbookTree,
  verifiedDay,
} from '../handbookContent'
import { HANDBOOK_SECTIONS } from '../handbookSections'

// frontend/src/features/handbook/utils/__tests__ -> repo root.
const REPO_ROOT = join(__dirname, '..', '..', '..', '..', '..', '..')
const CONTENT_DIR = join(__dirname, '..', '..', 'content')

// A page's title read straight from its Markdown source, so the German
// expectations stay in the de-AT content files instead of this spec.
function sourceTitle(localeDir: 'en-GB' | 'de-AT', slug: string): string {
  const source = readFileSync(join(CONTENT_DIR, localeDir, `${slug}.md`), 'utf-8')
  return /^title:\s*(.+)$/m.exec(source)?.[1]?.trim() ?? ''
}

describe('handbookContent', () => {
  it('lists the documented slugs from the English source directory', () => {
    const slugs = handbookSlugs()

    expect(slugs).toContain('production/auto-plan')
    // Sorted, and carrying no locale directory or extension.
    expect(slugs).toEqual([...slugs].sort())
    for (const slug of slugs) {
      expect(slug).not.toContain('.md')
      // Exactly one level of nesting: <section>/<page>.
      expect(slug.split('/')).toHaveLength(2)
    }
  })

  it('knows which pages have a doc', () => {
    expect(hasHandbookDoc('production/auto-plan')).toBe(true)
    expect(hasHandbookDoc('production/not-written-yet')).toBe(false)
    expect(hasHandbookDoc(undefined)).toBe(false)
  })

  it('loads a translated doc with its frontmatter and section', async () => {
    const doc = await loadHandbookDoc('production/auto-plan', 'deAT')

    expect(doc).not.toBeNull()
    expect(doc?.translated).toBe(true)
    expect(doc?.locale).toBe('deAT')
    expect(doc?.section).toBe('production')
    expect(doc?.page).toBe('auto-plan')
    expect(doc?.frontmatter.title).toBe(sourceTitle('de-AT', 'production/auto-plan'))
    expect(doc?.frontmatter.title).not.toBe(sourceTitle('en-GB', 'production/auto-plan'))
    // The trail back to the behaviour being described, so a backend change
    // has something greppable pointing at the docs that describe it.
    expect(doc?.frontmatter.sourceRefs).toContain(
      'backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py',
    )
  })

  // Loads and renders every doc in both locales, which takes seconds on its
  // own and more than the default five under the load of the full run.
  it('every sourceRefs entry, in every locale, resolves to a real file', { timeout: 30_000 }, async () => {
    const slugs = handbookSlugs()
    expect(slugs.length).toBeGreaterThan(0)

    const missing: string[] = []
    for (const slug of slugs) {
      for (const locale of ['enGB', 'deAT'] as const) {
        const doc = await loadHandbookDoc(slug, locale)
        for (const ref of doc?.frontmatter.sourceRefs ?? []) {
          if (!existsSync(join(REPO_ROOT, ref))) missing.push(`${slug} (${locale}): ${ref}`)
        }
      }
    }
    expect(missing).toEqual([])
  })

  it('reduces lastVerified to its calendar day whatever YAML made of it', async () => {
    expect(verifiedDay('2026-11-10T00:00:00.000Z')).toBe('2026-11-10')
    expect(verifiedDay('2026-11-10')).toBe('2026-11-10')
    expect(verifiedDay(new Date('2026-11-10T00:00:00.000Z'))).toBe('2026-11-10')
    expect(verifiedDay(new Date('not a date'))).toBeUndefined()
    expect(verifiedDay('last week')).toBeUndefined()
    expect(verifiedDay(undefined)).toBeUndefined()

    const doc = await loadHandbookDoc('production/auto-plan', 'deAT')
    expect(doc?.frontmatter.lastVerified).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('returns null for a slug nobody has written yet', async () => {
    expect(await loadHandbookDoc('production/not-written-yet', 'enGB')).toBeNull()
  })

  it('resolves a doc outside the production section in both locales', async () => {
    const english = await loadHandbookDoc('account/access-tokens', 'enGB')
    expect(english?.section).toBe('account')
    expect(english?.frontmatter.title).toBe('Access Tokens')

    const german = await loadHandbookDoc('account/access-tokens', 'deAT')
    expect(german?.translated).toBe(true)
    expect(german?.frontmatter.title).toBe(sourceTitle('de-AT', 'account/access-tokens'))
    expect(german?.frontmatter.title).not.toBe('Access Tokens')
  })

  it('builds a tree covering every section, documented or not', async () => {
    const tree = await loadHandbookTree('enGB')

    // The nav shows the whole app, so empty sections are present too, in
    // the same order as the app's own navigation.
    expect(tree.map((entry) => entry.section)).toEqual(HANDBOOK_SECTIONS.map((s) => s.key))

    const production = tree.find((entry) => entry.section === 'production')
    expect(production?.docs.map((doc) => doc.slug)).toContain('production/auto-plan')

    const todo = tree.find((entry) => entry.section === 'todo')
    expect(todo?.docs).toEqual([])
  })

  it('memoises the tree per locale', async () => {
    // The tree loads on every handbook page, so a second call must not
    // re-import every doc.
    expect(loadHandbookTree('enGB')).toBe(loadHandbookTree('enGB'))
    expect(loadHandbookTree('enGB')).not.toBe(loadHandbookTree('deAT'))
  })
})
