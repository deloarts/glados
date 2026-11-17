import { createApp, h, nextTick } from 'vue'
import type { Component } from 'vue'
import { createI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'
import { FORMAT_LOCALE_KEY } from '@/core/i18n/composables/useLocaleFormat'
import { LOCALE_MESSAGES } from '@/core/i18n/localeMessages'
import { REPORT_COLORS, REPORT_FONTS } from './palette'

/**
 * Turns a drawing the app already shows, a Vue component that renders an
 * SVG, into a self-contained SVG string for a PDF report. The component is
 * mounted off-screen in the report's language, with the theme's colour
 * variables set to the report palette, so the drawing looks the same
 * whatever theme the user has. Its computed styles are then written onto the
 * elements as attributes, because pdfmake reads attributes, not CSS.
 */

/** The theme variables drawings use, mapped onto the report palette. */
const THEME_VARIABLES: Record<string, string> = {
  '--p-text-color': REPORT_COLORS.ink,
  '--p-text-muted-color': REPORT_COLORS.muted,
  '--p-primary-color': REPORT_COLORS.accent,
  '--p-red-500': REPORT_COLORS.fail,
  '--p-orange-500': REPORT_COLORS.warn,
  '--p-green-500': REPORT_COLORS.pass,
  '--p-content-background': '#ffffff',
  '--p-content-border-color': REPORT_COLORS.rule,
}

/** Presentation properties copied from the computed style onto each element. */
const PROPERTIES = [
  'fill',
  'fill-opacity',
  'stroke',
  'stroke-width',
  'stroke-opacity',
  'stroke-dasharray',
  'stroke-linecap',
  'stroke-linejoin',
  'opacity',
  'font-size',
  'font-weight',
  'font-style',
  'text-anchor',
] as const

export interface RenderedDrawing {
  svg: string
  /** The text of the drawing's figcaption, when it has one. */
  caption: string | null
}

/** Values that are the SVG default anyway and need no attribute. */
const DEFAULTS: Partial<Record<(typeof PROPERTIES)[number], string>> = {
  'fill-opacity': '1',
  'stroke-opacity': '1',
  opacity: '1',
  'stroke-dasharray': 'none',
  'stroke-linecap': 'butt',
  'stroke-linejoin': 'miter',
  'font-style': 'normal',
  'text-anchor': 'start',
}

/**
 * A theme variable that is still in the value, as some engines report it
 * unresolved, becomes its report colour; otherwise its fallback is used.
 */
function resolveVariables(value: string): string {
  return value.replace(/var\((--[\w-]+)(?:\s*,\s*([^)]+))?\)/g, (match, name: string, fallback?: string) => {
    return THEME_VARIABLES[name] ?? fallback?.trim() ?? match
  })
}

/** "rgb(1, 2, 3)" stays, a fully transparent colour becomes none, "url("#a")" loses its quotes. */
function normaliseValue(property: (typeof PROPERTIES)[number], value: string): string | null {
  const trimmed = resolveVariables(value.trim())
  if (trimmed === '' || trimmed === DEFAULTS[property] || trimmed.includes('var(')) return null
  // A keyword such as "medium" would not mean anything to pdfmake.
  if (property === 'font-size' && !/^[\d.]+(px)?$/.test(trimmed)) return null
  if (/^rgba\(.*,\s*0\)$/.test(trimmed)) return 'none'
  if (trimmed.startsWith('url(')) return trimmed.replace(/["']/g, '')
  if (property === 'stroke-dasharray') return trimmed.replace(/px/g, '').replace(/,\s*/g, ' ')
  if (property === 'font-size' || property === 'stroke-width') return trimmed.replace(/px$/, '')
  return trimmed
}

function applyStyles(source: Element, target: Element): void {
  const style = window.getComputedStyle(source)
  for (const property of PROPERTIES) {
    // An attribute the drawing set itself, such as a pattern fill, wins.
    if (source.hasAttribute(property)) continue
    const value = normaliseValue(property, style.getPropertyValue(property))
    if (value !== null) target.setAttribute(property, value)
  }
  target.removeAttribute('class')
  target.removeAttribute('style')
  for (const attribute of Array.from(target.attributes)) {
    if (attribute.name.startsWith('data-')) target.removeAttribute(attribute.name)
  }
  if (target.tagName.toLowerCase() === 'text' || target.tagName.toLowerCase() === 'tspan') {
    target.setAttribute('font-family', REPORT_FONTS.body)
  }
  const sourceChildren = Array.from(source.children)
  const targetChildren = Array.from(target.children)
  sourceChildren.forEach((child, index) => {
    const twin = targetChildren[index]
    if (twin) applyStyles(child, twin)
  })
}

/**
 * pdfmake paints a text's fill and then its stroke, so a halo drawn with
 * `paint-order: stroke` would cover the letters. The halo goes into a copy
 * underneath instead, and the text itself keeps only its fill.
 */
function splitHalos(source: Element, target: Element): void {
  const sources = Array.from(source.querySelectorAll('text'))
  const targets = Array.from(target.querySelectorAll('text'))
  sources.forEach((text, index) => {
    const twin = targets[index]
    if (!twin) return
    const style = window.getComputedStyle(text)
    const stroke = twin.getAttribute('stroke')
    if (!style.getPropertyValue('paint-order').startsWith('stroke') || !stroke || stroke === 'none') return
    const halo = twin.cloneNode(true) as Element
    halo.setAttribute('fill', stroke)
    for (const node of [halo, ...Array.from(halo.querySelectorAll('tspan'))]) node.setAttribute('fill', stroke)
    twin.parentNode?.insertBefore(halo, twin)
    twin.setAttribute('stroke', 'none')
    for (const node of Array.from(twin.querySelectorAll('tspan'))) node.setAttribute('stroke', 'none')
  })
}

/** A rendered SVG element as a string with its computed styles as attributes. */
export function serializeSvg(svg: SVGSVGElement): string {
  const clone = svg.cloneNode(true) as SVGSVGElement
  applyStyles(svg, clone)
  splitHalos(svg, clone)
  const viewBox = svg.viewBox.baseVal
  if (viewBox && viewBox.width > 0 && viewBox.height > 0) {
    clone.setAttribute('width', String(viewBox.width))
    clone.setAttribute('height', String(viewBox.height))
  }
  clone.setAttribute('font-family', REPORT_FONTS.body)
  clone.removeAttribute('role')
  clone.removeAttribute('aria-label')
  return new XMLSerializer().serializeToString(clone)
}

/**
 * Mounts `component` with `props` off-screen in `locale` and returns its
 * first SVG as a string, or null when it rendered none.
 */
export async function renderComponentSvg(
  component: Component,
  props: Record<string, unknown>,
  locale: AppLocale,
): Promise<RenderedDrawing | null> {
  const host = document.createElement('div')
  host.setAttribute('aria-hidden', 'true')
  host.style.cssText = 'position: fixed; left: -10000px; top: 0; width: 640px; pointer-events: none;'
  for (const [name, value] of Object.entries(THEME_VARIABLES)) host.style.setProperty(name, value)
  document.body.appendChild(host)

  const app = createApp({ render: () => h(component, props) })
  app.use(createI18n({ legacy: false, locale, fallbackLocale: 'enGB', messages: LOCALE_MESSAGES }))
  app.provide(FORMAT_LOCALE_KEY, locale)
  try {
    app.mount(host)
    await nextTick()
    const svg = host.querySelector('svg')
    if (!svg) return null
    const caption = host.querySelector('figcaption')?.textContent?.trim() || null
    return { svg: serializeSvg(svg), caption }
  } finally {
    app.unmount()
    host.remove()
  }
}
