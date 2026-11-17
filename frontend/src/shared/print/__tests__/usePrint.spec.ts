import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import { printProviderKey, usePrint, type PrintProvider } from '../usePrint'

function capture(provide: Record<symbol, unknown> = {}): PrintProvider {
  let provider!: PrintProvider
  mount(
    defineComponent({
      setup() {
        provider = usePrint()
        return () => h('div')
      },
    }),
    { global: { provide } },
  )
  return provider
}

describe('usePrint', () => {
  it('fails every print when no provider is installed', async () => {
    const provider = capture()
    await expect(provider.print({ root_type: 'made_item', root_id: 1, items: [] })).rejects.toThrow('No print provider is installed')
    await expect(provider.printLotScrapTag(1)).rejects.toThrow('No print provider is installed')
    await expect(provider.download('order_docket', 'order', 1)).rejects.toThrow('No print provider is installed')
    await expect(provider.hasDefaultPrinter('scrap_tag')).resolves.toBe(false)
  })

  it('returns the installed provider', () => {
    const installed = { hasDefaultPrinter: () => Promise.resolve(true) } as unknown as PrintProvider
    expect(capture({ [printProviderKey as symbol]: installed })).toBe(installed)
  })
})
