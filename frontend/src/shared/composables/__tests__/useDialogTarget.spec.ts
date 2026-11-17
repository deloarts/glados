import { describe, it, expect } from 'vitest'

import { useDialogTarget } from '../useDialogTarget'

interface Item {
  id: number
}

describe('useDialogTarget', () => {
  it('starts with no target and hidden', () => {
    const { target, visible } = useDialogTarget<Item>()

    expect(target.value).toBeNull()
    expect(visible.value).toBe(false)
  })

  it('open() sets the target and shows the dialog', () => {
    const { target, visible, open } = useDialogTarget<Item>()
    const item: Item = { id: 7 }

    open(item)

    expect(target.value).toEqual(item)
    expect(visible.value).toBe(true)
  })

  it('close() hides the dialog but leaves the target in place', () => {
    const { target, visible, open, close } = useDialogTarget<Item>()
    const item: Item = { id: 7 }
    open(item)

    close()

    expect(visible.value).toBe(false)
    expect(target.value).toEqual(item)
  })

  it('a second open() replaces the target', () => {
    const { target, open } = useDialogTarget<Item>()
    open({ id: 1 })

    open({ id: 2 })

    expect(target.value).toEqual({ id: 2 })
  })

  it('setting visible false directly (e.g. via v-model:visible) leaves the target untouched', () => {
    const { target, visible, open } = useDialogTarget<Item>()
    open({ id: 3 })

    visible.value = false

    expect(target.value).toEqual({ id: 3 })
  })
})
