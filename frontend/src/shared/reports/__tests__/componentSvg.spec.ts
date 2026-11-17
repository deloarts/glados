import { afterEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { renderComponentSvg, serializeSvg } from '../utils/componentSvg'
import { REPORT_COLORS } from '../utils/palette'

function svgElement(markup: string): SVGSVGElement {
  const host = document.createElement('div')
  host.innerHTML = markup
  document.body.appendChild(host)
  return host.querySelector('svg') as SVGSVGElement
}

function parse(svg: string): Document {
  return new DOMParser().parseFromString(svg, 'image/svg+xml')
}

describe('serializeSvg', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('writes the computed colours as attributes, theme variables in the report palette', () => {
    const svg = svgElement(
      '<svg viewBox="0 0 120 60" class="sketch" data-v-1="">' +
        '<line x1="0" y1="0" x2="10" y2="10" class="sk-dim" style="stroke: var(--p-text-color); stroke-width: 1.5px" />' +
        '<rect fill="url(#hatch)" width="5" height="5" style="stroke: var(--p-red-500)" />' +
        '</svg>',
    )

    const doc = parse(serializeSvg(svg))
    const line = doc.querySelector('line')!
    const rect = doc.querySelector('rect')!

    expect(doc.querySelector('parsererror')).toBeNull()
    expect(line.getAttribute('stroke')).toBe(REPORT_COLORS.ink)
    expect(line.getAttribute('stroke-width')).toBe('1.5')
    expect(line.hasAttribute('class')).toBe(false)
    expect(line.hasAttribute('style')).toBe(false)
    expect(rect.getAttribute('fill')).toBe('url(#hatch)')
    expect(rect.getAttribute('stroke')).toBe(REPORT_COLORS.fail)
    expect(doc.documentElement.getAttribute('width')).toBe('120')
    expect(doc.documentElement.getAttribute('font-family')).toBe('Carlito')
    expect(doc.documentElement.hasAttribute('data-v-1')).toBe(false)
  })

  it('leaves the source element as it was', () => {
    const svg = svgElement('<svg viewBox="0 0 10 10"><circle r="2" class="dot" style="fill: var(--p-primary-color)" /></svg>')

    serializeSvg(svg)

    expect(svg.querySelector('circle')!.getAttribute('class')).toBe('dot')
    expect(svg.querySelector('circle')!.hasAttribute('fill')).toBe(false)
  })
})

describe('renderComponentSvg', () => {
  const Drawing = defineComponent({
    setup() {
      const { t } = useI18n()
      const { formatNumber } = useLocaleFormat()
      return () =>
        h('figure', [
          h('svg', { viewBox: '0 0 200 40' }, [
            h('text', { x: 1, y: 20 }, `${t('reports.document.page', { page: 1, pages: 2 })}: ${formatNumber(1.5)}`),
          ]),
          h('figcaption', ' Side view '),
        ])
    },
  })

  it('renders the drawing in the language of the report and cleans up', async () => {
    const drawing = await renderComponentSvg(Drawing, {}, 'deAT')

    expect(parse(drawing!.svg).querySelector('text')!.textContent).toBe('Seite 1 von 2: 1,5')
    expect(drawing!.caption).toBe('Side view')
    expect(document.body.children).toHaveLength(0)
  })

  it('answers null for a component without a drawing', async () => {
    const Empty = defineComponent({ setup: () => () => h('p', 'nothing to draw') })

    expect(await renderComponentSvg(Empty, {}, 'enGB')).toBeNull()
  })
})
