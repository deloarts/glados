import { nextTick } from 'vue'
import type { Ref } from 'vue'

/**
 * Inserts text into a textarea's value at the caret, replacing the selection,
 * and puts the caret back after the inserted text, for the variable chips of
 * the mail template editors. Without a mounted textarea the text is appended.
 * `insertVar` and `insertTableToken` write the template syntax for a variable
 * and for a column of the order table.
 */
export function useCaretInsert(textarea: Ref<HTMLTextAreaElement | null>, model: Ref<string>) {
  function insertText(text: string): void {
    const el = textarea.value
    if (!el) {
      model.value += text
      return
    }
    const start = el.selectionStart
    const end = el.selectionEnd
    model.value = model.value.slice(0, start) + text + model.value.slice(end)
    void nextTick(() => {
      el.selectionStart = el.selectionEnd = start + text.length
      el.focus()
    })
  }

  function insertVar(varName: string): void {
    insertText(`{{ ${varName} }}`)
  }

  function insertTableToken(colKey: string): void {
    insertText(`{{ table: ${colKey} }}`)
  }

  return { insertText, insertVar, insertTableToken }
}
