import { reactive } from 'vue'

/**
 * The field bookkeeping of a form that edits several selected items at
 * once. A field whose value differs across the selection is mixed and shows
 * `multipleValues` until the user edits it, and only the fields the user
 * edited overwrite the items when the form is saved.
 */
export function useSelectionEdit<F extends object, I>(form: F, multipleValues: () => string) {
  type Field = keyof F

  // Fields with differing values across the selection that the user has not
  // edited yet.
  const mixedFields = reactive(new Set<Field>()) as Set<Field>

  // Only edited fields overwrite the selected items.
  const dirtyFields = reactive(new Set<Field>()) as Set<Field>

  function applyFieldFromSelection<K extends Field>(
    field: K,
    items: I[],
    getter: (item: I) => F[K],
    emptyValue: F[K],
  ): void {
    const first = getter(items[0]!)
    if (items.every((item) => getter(item) === first)) {
      form[field] = first
    } else {
      form[field] = emptyValue
      mixedFields.add(field)
    }
  }

  function markDirty(field: Field): void {
    dirtyFields.add(field)
    mixedFields.delete(field)
  }

  function placeholderFor(field: Field, fallback?: string): string | undefined {
    return mixedFields.has(field) && !dirtyFields.has(field) ? multipleValues() : fallback
  }

  function clearFields(): void {
    dirtyFields.clear()
    mixedFields.clear()
  }

  return { mixedFields, dirtyFields, applyFieldFromSelection, markDirty, placeholderFor, clearFields }
}
