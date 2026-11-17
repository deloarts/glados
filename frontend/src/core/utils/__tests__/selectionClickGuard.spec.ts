import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { installSelectionClickGuard } from '../selectionClickGuard'

describe('installSelectionClickGuard', () => {
  let uninstall: () => void
  let rowClick: ReturnType<typeof vi.fn<(event: MouseEvent) => void>>

  beforeEach(() => {
    document.body.innerHTML = `
      <table><tbody class="p-datatable-tbody">
        <tr id="row"><td id="cell">PN-1234</td><td><button id="action">Edit</button></td></tr>
        <tr id="other"><td id="other-cell">PN-5678</td></tr>
      </tbody></table>`
    rowClick = vi.fn<(event: MouseEvent) => void>()
    document.getElementById('row')!.addEventListener('click', rowClick)
    uninstall = installSelectionClickGuard()
  })

  afterEach(() => {
    uninstall()
    document.getSelection()?.removeAllRanges()
    document.body.innerHTML = ''
  })

  function selectText(id: string): void {
    const range = document.createRange()
    range.selectNodeContents(document.getElementById(id)!)
    const selection = document.getSelection()!
    selection.removeAllRanges()
    selection.addRange(range)
  }

  function click(id: string, init: MouseEventInit = {}): void {
    document.getElementById(id)!.dispatchEvent(new MouseEvent('click', { bubbles: true, ...init }))
  }

  it('lets a plain row click through', () => {
    click('cell')
    expect(rowClick).toHaveBeenCalledOnce()
  })

  it('swallows the click that ends a text selection inside the row', () => {
    selectText('cell')
    click('cell')
    expect(rowClick).not.toHaveBeenCalled()
  })

  it('lets a click on a control inside the row through', () => {
    selectText('cell')
    click('action')
    expect(rowClick).toHaveBeenCalledOnce()
  })

  it('lets a shift or ctrl click through, since it picks rows', () => {
    selectText('cell')
    click('cell', { shiftKey: true })
    click('cell', { ctrlKey: true })
    expect(rowClick).toHaveBeenCalledTimes(2)
  })

  it('ignores a selection that sits in another row', () => {
    selectText('other-cell')
    click('cell')
    expect(rowClick).toHaveBeenCalledOnce()
  })

  it('stops guarding once uninstalled', () => {
    uninstall()
    selectText('cell')
    click('cell')
    expect(rowClick).toHaveBeenCalledOnce()
  })
})
