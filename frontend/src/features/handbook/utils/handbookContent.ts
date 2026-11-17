import type { Component } from 'vue'

import { HANDBOOK_SECTIONS } from './handbookSections'
import type { AppLocale } from '@/core/i18n'

// Content lives as markdown under content/<locale>/<section>/<page>.md and
// is compiled to Vue components at build time. The lazy glob gives each doc
// its own chunk. Every export besides default is a frontmatter key.
type MarkdownModule = Partial<HandbookFrontmatter> & { default: Component }

const modules = import.meta.glob<MarkdownModule>('../content/*/*/*.md')

// Directory names follow the locale files (en-GB.ts), not the i18n keys
// (enGB), so the two sets of translated content sit under matching names.
const LOCALE_DIRS: Record<AppLocale, string> = {
  enGB: 'en-GB',
  deAT: 'de-AT',
}

// English is the source language: a doc must exist here to count as existing
// at all, and a missing translation falls back to it rather than 404ing.
const SOURCE_LOCALE: AppLocale = 'enGB'

export interface HandbookFrontmatter {
  title: string
  summary?: string
  /** Position within its section; unordered docs sort after ordered ones. */
  order?: number
  /**
   * Where the described behaviour actually lives, so a backend change has a
   * greppable trail back to the docs that describe it.
   */
  sourceRefs?: string[]
  /** Calendar day (YYYY-MM-DD) the prose was last checked against those sources. */
  lastVerified?: string
}

export interface HandbookDoc {
  /** `<section>/<page>`, which is also its path under /handbook. */
  slug: string
  section: string
  page: string
  component: Component
  frontmatter: HandbookFrontmatter
  /** The locale actually rendered, which is the source locale on fallback. */
  locale: AppLocale
  /** False when the requested locale had no translation of this doc. */
  translated: boolean
}

export interface HandbookSectionDocs {
  section: string
  docs: HandbookDoc[]
}

function modulePath(slug: string, locale: AppLocale): string {
  return `../content/${LOCALE_DIRS[locale]}/${slug}.md`
}

export function sectionOf(slug: string): string {
  return slug.split('/')[0] ?? ''
}

export function pageOf(slug: string): string {
  return slug.split('/')[1] ?? ''
}

/** Every documented slug (`<section>/<page>`), in alphabetical order. */
export function handbookSlugs(): string[] {
  const prefix = `../content/${LOCALE_DIRS[SOURCE_LOCALE]}/`
  return Object.keys(modules)
    .filter((path) => path.startsWith(prefix))
    .map((path) => path.slice(prefix.length, -'.md'.length))
    .sort()
}

export function hasHandbookDoc(slug: string | undefined): boolean {
  return Boolean(slug) && modulePath(slug as string, SOURCE_LOCALE) in modules
}

/**
 * The calendar day of a `lastVerified` value. YAML reads an unquoted
 * `2026-11-10` as a timestamp, which reaches the browser as a Date or as its
 * ISO string at midnight UTC, so only the day part carries meaning.
 */
export function verifiedDay(value: unknown): string | undefined {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? undefined : value.toISOString().slice(0, 10)
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10)
  return undefined
}

/**
 * Loads one doc, preferring `locale` and falling back to English. Returns null
 * for a slug that has no English source doc.
 */
export async function loadHandbookDoc(
  slug: string,
  locale: AppLocale,
): Promise<HandbookDoc | null> {
  const translated = modules[modulePath(slug, locale)]
  const loader = translated ?? modules[modulePath(slug, SOURCE_LOCALE)]
  if (!loader) return null

  const { default: component, ...frontmatter } = await loader()
  return {
    slug,
    section: sectionOf(slug),
    page: pageOf(slug),
    component,
    // Falling back to the slug keeps a doc that forgot its frontmatter
    // readable instead of rendering an empty heading.
    frontmatter: { title: slug, ...frontmatter, lastVerified: verifiedDay(frontmatter.lastVerified) },
    locale: translated ? locale : SOURCE_LOCALE,
    translated: Boolean(translated),
  }
}

// The nav tree needs every doc's title, so entering the handbook loads them
// all once, memoised per locale.
const treeCache = new Map<AppLocale, Promise<HandbookSectionDocs[]>>()

function byOrderThenTitle(a: HandbookDoc, b: HandbookDoc): number {
  const orderA = a.frontmatter.order ?? Number.MAX_SAFE_INTEGER
  const orderB = b.frontmatter.order ?? Number.MAX_SAFE_INTEGER
  if (orderA !== orderB) return orderA - orderB
  return a.frontmatter.title.localeCompare(b.frontmatter.title)
}

/**
 * Every section in nav order with its docs, including sections that have no
 * docs yet. The tree shows the whole app, not only the documented parts.
 */
export function loadHandbookTree(locale: AppLocale): Promise<HandbookSectionDocs[]> {
  const cached = treeCache.get(locale)
  if (cached) return cached

  const pending = (async () => {
    const docs = await Promise.all(handbookSlugs().map((slug) => loadHandbookDoc(slug, locale)))
    const loaded = docs.filter((doc): doc is HandbookDoc => doc !== null)

    return HANDBOOK_SECTIONS.map(({ key }) => ({
      section: key,
      docs: loaded.filter((doc) => doc.section === key).sort(byOrderThenTitle),
    }))
  })()

  treeCache.set(locale, pending)
  return pending
}
