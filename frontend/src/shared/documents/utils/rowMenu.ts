import type { MenuItem } from 'openvue/menuitem'

import type { DocumentPageAction } from '../composables/useDocumentPageAction'

type Translate = (key: string) => string

/** What a row may do; the document page checks again when it carries a step out. */
export interface DocumentRowPermissions {
  edit: boolean
  revise: boolean
  release: boolean
  invalidate: boolean
  delete: boolean
}

/** A step of a row, as the menu shows it. */
export type DocumentRowStep = keyof DocumentRowPermissions

/**
 * Why a step the row's state allows is still disabled, such as the missing
 * permission, keyed by step. A step left out, or with '', shows no reason.
 */
export type DocumentRowReasons = Partial<Record<DocumentRowStep, string>>

/**
 * Decides one step of a row. A step the row's state rules out is disabled
 * without a reason, since no permission would change that. Otherwise the
 * first non-empty blocker, such as a missing permission or another user's
 * edit lock, disables it and is its reason.
 */
export function documentRowStep(stateAllows: boolean, blockers: string[]): { can: boolean; reason: string } {
  if (!stateAllows) return { can: false, reason: '' }
  const reason = blockers.find((blocker) => blocker !== '') ?? ''
  return { can: reason === '', reason }
}

/** Splits decided steps into the menu's `can` and `reasons`. */
export function documentRowSteps<K extends string>(
  steps: Record<K, { can: boolean; reason: string }>,
): { can: Record<K, boolean>; reasons: Record<K, string> } {
  const entries = Object.entries(steps) as [K, { can: boolean; reason: string }][]
  return {
    can: Object.fromEntries(entries.map(([name, step]) => [name, step.can])) as Record<K, boolean>,
    reasons: Object.fromEntries(entries.map(([name, step]) => [name, step.reason])) as Record<K, string>,
  }
}

export interface DocumentRowMenuOptions {
  open: () => void
  openInNewTab: () => void
  copyLink: () => void
  /** Left out for a kind of document without a report. */
  print?: () => void
  remove: () => void
  /** Opens the document with one of the steps only its page takes. */
  pageAction: (action: DocumentPageAction) => void
  can: DocumentRowPermissions
  /**
   * The reasons of the disabled steps, shown as the entry's title by a
   * ContextMenu that binds disabledItemTooltipPt.
   */
  reasons?: DocumentRowReasons
  /** Steps of one kind of document only, shown before Delete. */
  extra?: MenuItem[]
}

/**
 * The context menu of a controlled document row, such as a calculation:
 * opening and sharing it, its editing and history, its revision steps and
 * deleting a draft. Steps the row cannot take are shown disabled, so the
 * menu keeps its shape, and a step the row's state allows names in its
 * title why it is still disabled.
 */
export function documentRowMenu(options: DocumentRowMenuOptions, t: Translate): MenuItem[] {
  const { can } = options
  const step = (action: DocumentPageAction) => () => options.pageAction(action)
  const title = (name: DocumentRowStep) => (can[name] ? undefined : options.reasons?.[name] || undefined)
  return [
    { label: t('documents.menu.open'), icon: 'mdi mdi-open-in-app', command: options.open },
    { label: t('documents.menu.openInNewTab'), icon: 'mdi mdi-open-in-new', command: options.openInNewTab },
    { separator: true },
    { label: t('documents.menu.edit'), icon: 'mdi mdi-pencil-outline', disabled: !can.edit, title: title('edit'), command: step('edit') },
    { label: t('documents.menu.history'), icon: 'mdi mdi-history', command: step('history') },
    ...(options.print
      ? [{ label: t('documents.menu.print'), icon: 'mdi mdi-printer-outline', command: options.print }]
      : []),
    { label: t('documents.menu.copyLink'), icon: 'mdi mdi-link-variant', command: options.copyLink },
    { separator: true },
    { label: t('documents.menu.revise'), icon: 'mdi mdi-source-branch-plus', disabled: !can.revise, title: title('revise'), command: step('revise') },
    {
      label: t('documents.menu.release'),
      icon: 'mdi mdi-check-decagram-outline',
      disabled: !can.release,
      title: title('release'),
      command: step('release'),
    },
    {
      label: t('documents.menu.invalidate'),
      icon: 'mdi mdi-alert-octagon-outline',
      disabled: !can.invalidate,
      title: title('invalidate'),
      command: step('invalidate'),
    },
    ...(options.extra ?? []),
    { separator: true },
    { label: t('documents.menu.delete'), icon: 'mdi mdi-delete-outline', disabled: !can.delete, title: title('delete'), command: options.remove },
  ]
}
