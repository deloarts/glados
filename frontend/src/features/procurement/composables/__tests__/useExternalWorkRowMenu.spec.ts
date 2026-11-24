import { describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { useExternalWorkRowMenu } from '../useExternalWorkRowMenu'
import { makeExternalWorkRow } from '../../__tests__/externalWorkFixtures'

import type { MenuItem } from 'openvue/menuitem'
import type { ExternalWorkRow } from '../../types/externalWork'

function menuFor(row: ExternalWorkRow, permissions: string[]): MenuItem[] {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  let items: MenuItem[] = []
  const Host = defineComponent({
    setup() {
      const menu = useExternalWorkRowMenu(vi.fn<() => Promise<void>>().mockResolvedValue())
      menu.menuRow.value = row
      items = menu.items.value
      return () => null
    },
  })
  mountWithApp(Host, { pinia, plugins: [makeTestRouter()] }).unmount()
  return items.filter((item) => !item.separator)
}

function entry(items: MenuItem[], label: string): MenuItem {
  const found = items.find((item) => String(item.label).startsWith(label))
  if (!found) throw new Error(`no menu entry ${label}`)
  return found
}

const WRITERS = [Permission.WRITE_ORDERS, Permission.WRITE_LOTS]

describe('useExternalWorkRowMenu', () => {
  it('offers the suggestion and the supplier choice for work nobody has ordered', () => {
    const items = menuFor(
      makeExternalWorkRow({ suggested_supplier_id: 14, suggested_supplier_name: 'Härterei Demo' }),
      WRITERS,
    )

    expect(entry(items, 'Use Suggestion').label).toBe('Use Suggestion: Härterei Demo')
    expect(entry(items, 'Use Suggestion').disabled).toBe(false)
    expect(entry(items, 'Choose Supplier').disabled).toBe(false)
    expect(entry(items, 'Remove From Order').disabled).toBe(true)
    expect(entry(items, 'Record Provision').disabled).toBe(true)
  })

  it('lets ordered work leave its order until pieces went to the supplier', () => {
    const ordered = makeExternalWorkRow({ order_item_id: 9, order_id: 7, supplier_name: 'Härterei Demo' })

    const before = menuFor(ordered, WRITERS)
    const after = menuFor({ ...ordered, handed_over_quantity: 3 }, WRITERS)

    expect(entry(before, 'Use Suggestion').disabled).toBe(true)
    expect(entry(before, 'Remove From Order').disabled).toBe(false)
    expect(entry(before, 'Record Provision').disabled).toBe(false)
    expect(entry(after, 'Remove From Order').disabled).toBe(true)
    expect(entry(after, 'Remove From Order').title).toBe('Pieces went to the supplier already.')
  })

  it('names the missing permission on the supplier entries', () => {
    const items = menuFor(makeExternalWorkRow({ suggested_supplier_id: 14 }), [])

    expect(entry(items, 'Choose Supplier').disabled).toBe(true)
    expect(String(entry(items, 'Choose Supplier').title)).toContain('Orders')
  })
})
