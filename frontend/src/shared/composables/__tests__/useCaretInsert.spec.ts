import { describe, it, expect } from 'vitest'
import { nextTick, ref, watch } from 'vue'

import { useCaretInsert } from '../useCaretInsert'

describe('useCaretInsert', () => {
  it('appends the text when no textarea is mounted', () => {
    const model = ref('Hi ')
    const { insertVar } = useCaretInsert(ref(null), model)

    insertVar('supplier')

    expect(model.value).toBe('Hi {{ supplier }}')
  })

  it('replaces the selection and puts the caret after the inserted text', async () => {
    const textarea = document.createElement('textarea')
    document.body.appendChild(textarea)
    const model = ref('Dear NAME, thanks')
    // Stands in for the v-model binding, which renders the new value before the caret moves.
    watch(model, (value) => (textarea.value = value), { flush: 'sync' })
    textarea.value = model.value
    textarea.setSelectionRange(5, 9)
    const { insertTableToken } = useCaretInsert(ref(textarea), model)

    insertTableToken('quantity')
    await nextTick()

    expect(model.value).toBe('Dear {{ table: quantity }}, thanks')
    expect(textarea.selectionStart).toBe(5 + '{{ table: quantity }}'.length)
    expect(document.activeElement).toBe(textarea)
    textarea.remove()
  })
})
