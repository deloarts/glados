/**
 * Table text is selectable so a part number or an order ID can be copied, but
 * most tables open the record on a row click, and a drag that selects text
 * inside a row ends in a click on that row. This guard swallows exactly that
 * click: one on a table body row while a selection inside the same row is
 * still standing. A plain click collapses the selection on mousedown and goes
 * through, and so does a click on a control inside the row. A ctrl, meta or
 * shift click goes through too: it picks rows, and a shift click extends the
 * text selection up to the clicked row as a side effect.
 */

const ROW_SELECTOR = '.p-datatable-tbody > tr'
const CONTROL_SELECTOR = 'a, button, input, select, textarea, label, [role="button"], [role="checkbox"]'

function swallowSelectingClick(event: MouseEvent): void {
  const target = event.target
  if (!(target instanceof Element)) return
  if (event.ctrlKey || event.metaKey || event.shiftKey) return
  const row = target.closest(ROW_SELECTOR)
  if (!row || target.closest(CONTROL_SELECTOR)) return
  const selection = target.ownerDocument.getSelection()
  if (!selection || selection.isCollapsed) return
  if (!row.contains(selection.anchorNode) && !row.contains(selection.focusNode)) return
  event.stopPropagation()
}

/** Starts guarding row clicks; returns what stops it again. */
export function installSelectionClickGuard(target: Window = window): () => void {
  target.addEventListener('click', swallowSelectingClick, { capture: true })
  return () => target.removeEventListener('click', swallowSelectingClick, { capture: true })
}
