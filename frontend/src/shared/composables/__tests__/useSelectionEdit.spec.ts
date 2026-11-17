import { describe, it, expect } from 'vitest'
import { reactive } from 'vue'

import { useSelectionEdit } from '../useSelectionEdit'

interface Form {
  name: string
  mass: number | null
}

function setup() {
  const form = reactive<Form>({ name: '', mass: null })
  return { form, ...useSelectionEdit<Form, Form>(form, () => 'Multiple values') }
}

describe('useSelectionEdit', () => {
  it('takes a value every selected item shares', () => {
    const { form, applyFieldFromSelection, placeholderFor } = setup()

    applyFieldFromSelection('mass', [{ name: 'a', mass: 3 }, { name: 'b', mass: 3 }], (i) => i.mass, null)

    expect(form.mass).toBe(3)
    expect(placeholderFor('mass', 'fallback')).toBe('fallback')
  })

  it('marks a differing value as mixed until the user edits it', () => {
    const { form, applyFieldFromSelection, placeholderFor, markDirty, dirtyFields } = setup()

    applyFieldFromSelection('mass', [{ name: 'a', mass: 3 }, { name: 'b', mass: 4 }], (i) => i.mass, null)

    expect(form.mass).toBeNull()
    expect(placeholderFor('mass')).toBe('Multiple values')
    markDirty('mass')
    expect(placeholderFor('mass')).toBeUndefined()
    expect(dirtyFields.has('mass')).toBe(true)
  })

  it('forgets every mixed and edited field on clear', () => {
    const { applyFieldFromSelection, markDirty, clearFields, mixedFields, dirtyFields } = setup()
    applyFieldFromSelection('mass', [{ name: 'a', mass: 3 }, { name: 'b', mass: 4 }], (i) => i.mass, null)
    markDirty('name')

    clearFields()

    expect(mixedFields.size).toBe(0)
    expect(dirtyFields.size).toBe(0)
  })
})
