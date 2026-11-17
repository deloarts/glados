import { describe, it, expect, beforeEach, vi } from 'vitest'

import { CAKE_PHRASE, cakeify, collectCakeTargets, resetAndReload } from '../useCakeProtocol'
import { initEasterEggs, useEasterEggs } from '../useEasterEggs'

function mount(html: string): HTMLElement {
  document.body.innerHTML = html
  return document.body
}

/** What the sweep does, in one go rather than spread over four seconds. */
function sweep(root: HTMLElement): void {
  collectCakeTargets(root).forEach((node) => {
    node.nodeValue = cakeify(node.nodeValue ?? '')
  })
}

describe('cakeify', () => {
  it('replaces the prose', () => {
    expect(cakeify('Bought items')).toBe(CAKE_PHRASE)
  })

  // Neighbouring inline nodes would otherwise render as "lieThe cake is a lie".
  it('keeps the whitespace around it', () => {
    expect(cakeify('  Bought items  ')).toBe(`  ${CAKE_PHRASE}  `)
    expect(cakeify('\n  Total\n')).toBe(`\n  ${CAKE_PHRASE}\n`)
  })

  it('handles a single character', () => {
    expect(cakeify('x')).toBe(CAKE_PHRASE)
  })
})

describe('collectCakeTargets', () => {
  it('finds visible prose', () => {
    const root = mount('<div><p>Orders</p><span>Suppliers</span></div>')
    expect(collectCakeTargets(root)).toHaveLength(2)
  })

  it('ignores whitespace-only nodes', () => {
    const root = mount('<div>\n  <p>Orders</p>\n</div>')
    expect(collectCakeTargets(root)).toHaveLength(1)
  })

  it('skips script, style and title', () => {
    const root = mount(
      '<script>const a = "x"</script><style>.a { color: red }</style><title>Glados</title><p>Orders</p>',
    )
    const nodes = collectCakeTargets(root)
    expect(nodes).toHaveLength(1)
    expect(nodes[0]!.nodeValue).toBe('Orders')
  })

  it('skips anything inside a data-cake-exempt subtree', () => {
    const root = mount('<div data-cake-exempt><p>Do you want cake?</p></div><p>Orders</p>')
    const nodes = collectCakeTargets(root)
    expect(nodes).toHaveLength(1)
    expect(nodes[0]!.nodeValue).toBe('Orders')
  })

  // The sequence is one-way (nothing is ever put back), so anything the sweep
  // reaches is gone until the page is refreshed. Form fields staying out of its
  // way is the difference between a joke and eating someone's half-typed order.
  it('never touches what the user has typed', () => {
    const root = mount('<input value="ACME Ltd" /><textarea>draft note</textarea><p>Orders</p>')
    sweep(root)

    expect(root.querySelector('input')!.value).toBe('ACME Ltd')
    expect(root.querySelector('textarea')!.value).toBe('draft note')
  })

  // Icons paint through ::before content, so they are not text nodes and the
  // screen stays legible as a UI rather than a wall of nothing.
  it('leaves icon elements alone', () => {
    const root = mount('<i class="mdi mdi-cake-variant"></i><p>Orders</p>')
    sweep(root)

    expect(root.querySelector('i')!.className).toBe('mdi mdi-cake-variant')
  })

  it('converts every eligible node', () => {
    const root = mount('<p>Orders</p><span>Suppliers</span><div>Total: 12</div>')
    sweep(root)

    expect(root.querySelector('p')!.textContent).toBe(CAKE_PHRASE)
    expect(root.querySelector('span')!.textContent).toBe(CAKE_PHRASE)
    expect(root.querySelector('div')!.textContent).toBe(CAKE_PHRASE)
  })
})

// A reset that left the app red and still calling itself Aperture Science
// would not be much of a reset. Aperture mode is the only part of this that
// survives a reload on its own, so it has to be cleared explicitly.
describe('resetAndReload', () => {
  beforeEach(() => {
    initEasterEggs()
    localStorage.clear()
  })

  it('clears aperture mode before reloading', () => {
    const reload = vi.fn<() => void>()
    vi.stubGlobal('location', { reload })
    useEasterEggs().setAperture(true)
    expect(document.documentElement.classList.contains('aperture-mode')).toBe(true)

    resetAndReload()

    expect(useEasterEggs().apertureMode.value).toBe(false)
    expect(localStorage.getItem('apertureMode')).toBe('false')
    expect(document.documentElement.classList.contains('aperture-mode')).toBe(false)
    expect(reload).toHaveBeenCalledOnce()
    vi.unstubAllGlobals()
  })
})
