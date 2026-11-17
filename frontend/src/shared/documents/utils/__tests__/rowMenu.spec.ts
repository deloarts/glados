import { describe, expect, it, vi } from 'vitest'

import { documentRowMenu, documentRowStep, documentRowSteps } from '../rowMenu'
import type { DocumentRowMenuOptions, DocumentRowPermissions } from '../rowMenu'

const t = (key: string) => key

function options(can: DocumentRowPermissions, reasons: DocumentRowMenuOptions['reasons']): DocumentRowMenuOptions {
  return {
    open: vi.fn<() => void>(),
    openInNewTab: vi.fn<() => void>(),
    copyLink: vi.fn<() => void>(),
    remove: vi.fn<() => void>(),
    pageAction: vi.fn<() => void>(),
    can,
    reasons,
  }
}

describe('documentRowStep', () => {
  it('disables a step the state rules out without a reason', () => {
    expect(documentRowStep(false, ['missing'])).toEqual({ can: false, reason: '' })
  })

  it('disables a step the state allows with its first blocker as reason', () => {
    expect(documentRowStep(true, ['', 'first', 'second'])).toEqual({ can: false, reason: 'first' })
  })

  it('allows a step with no blocker', () => {
    expect(documentRowStep(true, ['', ''])).toEqual({ can: true, reason: '' })
  })
})

describe('documentRowSteps', () => {
  it('splits decided steps into can and reasons', () => {
    expect(
      documentRowSteps({ edit: { can: true, reason: '' }, delete: { can: false, reason: 'why' } }),
    ).toEqual({ can: { edit: true, delete: false }, reasons: { edit: '', delete: 'why' } })
  })
})

describe('documentRowMenu', () => {
  const can = { edit: false, revise: true, release: false, invalidate: false, delete: false }

  it('gives a disabled step its reason as title and leaves others without one', () => {
    const menu = documentRowMenu(
      options(can, { edit: 'needs write', revise: 'ignored', release: '', delete: 'needs manage' }),
      t,
    )
    const title = (label: string) => menu.find((item) => item.label === label)?.title
    expect(title('documents.menu.edit')).toBe('needs write')
    expect(title('documents.menu.revise')).toBeUndefined()
    expect(title('documents.menu.release')).toBeUndefined()
    expect(title('documents.menu.invalidate')).toBeUndefined()
    expect(title('documents.menu.delete')).toBe('needs manage')
  })
})
