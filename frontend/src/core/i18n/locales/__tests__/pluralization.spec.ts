// Migrate manual (s)/(e)/(en) pluralization to vue-i18n plural syntax. This
// spec is the whole point of the migration test: it resolves every converted
// key directly against the live locale messages, for 0/1/n, in both enGB and
// deAT, without mounting a component: a call site can only ever pass a
// count through to t(), the rendering itself is entirely a function of the
// message + count + locale.
//
// The English expectations are written out. The German ones are read from
// the de-AT locale file, so this spec holds no German text: the message is
// split into its three plural forms, the form vue-i18n's default rule picks
// for the count (0, 1, many) is taken and its placeholders are filled in.
import { describe, it, expect, afterEach } from 'vitest'

import { i18n } from '@/core/i18n'
import deAT from '@/core/i18n/locales/de-AT'
import type { AppLocale } from '@/core/i18n'

const t = i18n.global.t as (key: string, ...args: unknown[]) => string

function setLocale(locale: AppLocale): void {
  i18n.global.locale.value = locale
}

afterEach(() => {
  setLocale('enGB')
})

function deAtSource(key: string): string {
  const value = key
    .split('.')
    .reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], deAT)
  if (typeof value !== 'string') throw new Error(`de-AT has no message at ${key}`)
  return value
}

function deAtForms(key: string): string[] {
  return deAtSource(key)
    .split('|')
    .map((form) => form.trim())
}

/** The text the de-AT message for `key` should render for `count`. */
function expectedDeAt(key: string, count: number, named: Record<string, string> = {}): string {
  const forms = deAtForms(key)
  const form = forms.length === 1 ? forms[0]! : forms[Math.min(count, 2)]!
  const values: Record<string, string> = { count: String(count), n: String(count), ...named }
  return form.replace(/\{(\w+)\}/g, (placeholder, name: string) => values[name] ?? placeholder)
}

interface PluralCase {
  key: string
  en: [zero: string, one: string, many: string]
  /** the "many" count used to render the 3rd form, 5 unless overridden */
  many?: number
}

const cases: PluralCase[] = [
  {
    key: 'login.errors.lockedOutFor',
    en: [
      'Too many failed attempts. Try again shortly.',
      'Too many failed attempts. Try again in 1 minute.',
      'Too many failed attempts. Try again in 5 minutes.',
    ],
  },
  {
    key: 'settings.apiKeys.revokedAll',
    en: ['No API keys revoked.', 'Revoked 1 API key.', 'Revoked 5 API keys.'],
  },
  {
    key: 'account.pat.revokedAll',
    en: ['No tokens revoked.', 'Revoked 1 token.', 'Revoked 5 tokens.'],
  },
  {
    key: 'adminSettings.storage.migrateDialog.result.migrated',
    en: ['No files migrated', '1 file migrated', '5 files migrated'],
  },
  {
    key: 'adminSettings.storage.migrateDialog.result.failed',
    en: ['No files failed', '1 file failed', '5 files failed'],
  },
  {
    key: 'adminSettings.backups.files.restoreResult',
    en: ['No files restored.', 'Restored 1 file.', 'Restored 5 files.'],
  },
  {
    key: 'account.sessions.othersRevoked',
    en: [
      'No other sessions signed out.',
      '1 other session signed out.',
      '5 other sessions signed out.',
    ],
  },
  // selectionSummary: same EN text, a different German noun per feature.
  {
    key: 'boughtItems.edit.selectionSummary',
    en: ['No items selected', '1 item selected', '5 items selected'],
  },
  {
    key: 'sourceItems.edit.selectionSummary',
    en: ['No items selected', '1 item selected', '5 items selected'],
  },
  {
    key: 'madeItems.edit.selectionSummary',
    en: ['No items selected', '1 item selected', '5 items selected'],
  },
  // selectedCount ("demand(s)"): identical text in each locale across the 3 features.
  {
    key: 'boughtItems.demands.procure.selectedCount',
    en: ['No demands selected', '1 demand selected', '5 demands selected'],
  },
  {
    key: 'sourceItems.demands.procure.selectedCount',
    en: ['No demands selected', '1 demand selected', '5 demands selected'],
  },
  {
    key: 'madeItems.demands.manageLots.selectedCount',
    en: ['No demands selected', '1 demand selected', '5 demands selected'],
  },
  {
    key: 'boughtItems.demands.batchCreate.createSuccess',
    en: ['No demands created.', '1 demand created.', '5 demands created.'],
  },
  {
    key: 'madeItems.demands.autoAssign.success',
    en: ['No lots created.', '1 lot created.', '5 lots created.'],
  },
  {
    key: 'madeItems.catalogue.processes.grouping.groupCount',
    en: [
      'No groups, carried over to new lots as shared positions',
      '1 group, carried over to new lots as shared positions',
      '5 groups, carried over to new lots as shared positions',
    ],
  },
  {
    key: 'production.lots.detail.state.notPlanned',
    en: ['No unplanned positions', '1 position not planned', '5 positions not planned'],
  },
  {
    key: 'production.lots.detail.state.deliveryLateTooltip',
    en: [
      'On the required delivery date.',
      '1 day past the required delivery date.',
      '5 days past the required delivery date.',
    ],
  },
  {
    key: 'production.lots.detail.state.deliveryWillBeLateTooltip',
    en: [
      'Currently forecast on the required delivery date.',
      'Currently forecast 1 day past the required delivery date.',
      'Currently forecast 5 days past the required delivery date.',
    ],
  },
  {
    key: 'production.lots.detail.state.deliveryCompletedLateTooltip',
    en: [
      'On the required delivery date.',
      '1 day past the required delivery date.',
      '5 days past the required delivery date.',
    ],
  },
  {
    key: 'production.lots.detail.grouping.positionCount',
    en: ['No positions', '1 position', '5 positions'],
  },
  {
    key: 'production.lots.detail.manageOrders.unassignedCount',
    en: ['No unassigned positions', '1 unassigned position', '5 unassigned positions'],
  },
  {
    key: 'production.lots.detail.manageProduction.unassignedCount',
    en: ['No unassigned positions', '1 unassigned position', '5 unassigned positions'],
  },
  {
    key: 'production.lots.detail.manageProduction.needsMachineCount',
    en: [
      'No positions need a machine',
      '1 position needs a machine',
      '5 positions need a machine',
    ],
  },
  {
    key: 'printLabels.controls.disableAllPrintersDone',
    en: ['No printers disabled.', 'Disabled 1 printer.', 'Disabled 5 printers.'],
  },
  {
    key: 'printDockets.controls.disableAllPrintersDone',
    en: ['No printers disabled.', 'Disabled 1 printer.', 'Disabled 5 printers.'],
  },
  {
    key: 'printLabels.controls.disableAutoPrintDone',
    en: [
      'No labels had auto-print disabled.',
      'Disabled auto-print on 1 label.',
      'Disabled auto-print on 5 labels.',
    ],
  },
  {
    key: 'printDockets.controls.disableAutoPrintDone',
    en: [
      'No dockets had auto-print disabled.',
      'Disabled auto-print on 1 docket.',
      'Disabled auto-print on 5 dockets.',
    ],
  },
  {
    key: 'productionQueue.board.poolMachineCount',
    en: ['No machines', '1 machine', '5 machines'],
  },
  {
    key: 'productionSchedule.autoPlan.skipped',
    en: [
      'No pinned or in-progress orders skipped.',
      'Skipped 1 pinned or in-progress order.',
      'Skipped 5 pinned or in-progress orders.',
    ],
  },
  {
    key: 'productionSchedule.autoPlan.skippedTodaysPlanned',
    en: [
      'No orders already planned for today left untouched.',
      'Left 1 order already planned for today untouched.',
      'Left 5 orders already planned for today untouched.',
    ],
  },
  // The two "N allocations" fragments, tested standalone before the
  // composite-sentence tests below exercise them together.
  {
    key: 'boughtItems.demands.detail.allocationsCountPhrase',
    many: 3,
    en: ['0 allocations', '1 allocation', '3 allocations'],
  },
  {
    key: 'sourceItems.demands.detail.allocationsCountPhrase',
    many: 3,
    en: ['0 allocations', '1 allocation', '3 allocations'],
  },
  {
    key: 'production.lots.detail.forceStatus.inProgressOrdersPhrase',
    many: 3,
    en: [
      'no in-progress production orders',
      '1 in-progress production order',
      '3 in-progress production orders',
    ],
  },
  {
    key: 'production.lots.detail.forceStatus.orderItemsPhrase',
    many: 3,
    en: ['no order items', '1 order item', '3 order items'],
  },
]

describe('locale plural forms (0 / 1 / n, enGB + deAT)', () => {
  it.each(cases)('$key', ({ key, en, many = 5 }) => {
    setLocale('enGB')
    expect(t(key, 0)).toBe(en[0])
    expect(t(key, 1)).toBe(en[1])
    expect(t(key, many)).toBe(en[2])

    setLocale('deAT')
    expect(deAtForms(key)).toHaveLength(3)
    expect(t(key, 0)).toBe(expectedDeAt(key, 0))
    expect(t(key, 1)).toBe(expectedDeAt(key, 1))
    expect(t(key, many)).toBe(expectedDeAt(key, many))
  })

  // Every plural branch must resolve to real text, never leak the raw
  // pipe-delimited source string (the known risk for a missed
  // call site / wrong param name).
  it.each(cases)('$key never renders the raw pipe-delimited message', ({ key, many = 5 }) => {
    for (const locale of ['enGB', 'deAT'] as const) {
      setLocale(locale)
      for (const count of [0, 1, many]) {
        expect(t(key, count)).not.toContain(' | ')
      }
    }
  })
})

describe('unmappedPlaceholders (printLabels / printDockets): count-selected, {names} interpolated', () => {
  it('printLabels: pluralizes on count and still interpolates the joined names list', () => {
    setLocale('enGB')
    expect(t('printLabels.editor.errors.unmappedPlaceholders', { count: 0, names: '' })).toBe(
      'No unmapped placeholders in the field map',
    )
    expect(
      t('printLabels.editor.errors.unmappedPlaceholders', { count: 1, names: 'sku' }),
    ).toBe('1 unmapped placeholder in the field map: sku')
    expect(
      t('printLabels.editor.errors.unmappedPlaceholders', { count: 2, names: 'sku, batch' }),
    ).toBe('2 unmapped placeholders in the field map: sku, batch')

    setLocale('deAT')
    expect(deAtForms('printLabels.editor.errors.unmappedPlaceholders')).toHaveLength(3)
    for (const [count, names] of [
      [0, ''],
      [1, 'sku'],
      [2, 'sku, batch'],
    ] as const) {
      expect(t('printLabels.editor.errors.unmappedPlaceholders', { count, names })).toBe(
        expectedDeAt('printLabels.editor.errors.unmappedPlaceholders', count, { names }),
      )
    }
  })

  it('printDockets: pluralizes on count and still interpolates the joined names list', () => {
    setLocale('enGB')
    expect(t('printDockets.editor.errors.unmappedPlaceholders', { count: 0, names: '' })).toBe(
      'No unmapped fields in the field map',
    )
    expect(
      t('printDockets.editor.errors.unmappedPlaceholders', { count: 1, names: 'sku' }),
    ).toBe('1 unmapped field in the field map: sku')
    expect(
      t('printDockets.editor.errors.unmappedPlaceholders', { count: 2, names: 'sku, batch' }),
    ).toBe('2 unmapped fields in the field map: sku, batch')

    setLocale('deAT')
    expect(deAtForms('printDockets.editor.errors.unmappedPlaceholders')).toHaveLength(3)
    for (const [count, names] of [
      [0, ''],
      [1, 'sku'],
      [2, 'sku, batch'],
    ] as const) {
      expect(t('printDockets.editor.errors.unmappedPlaceholders', { count, names })).toBe(
        expectedDeAt('printDockets.editor.errors.unmappedPlaceholders', count, { names }),
      )
    }
  })
})

// The two composite sentences (autoAllocateSuccess, forceStatus.*.warning) each
// pluralize two independent counts in one message, unsupported by a single
// t(key, count) call, so the call sites resolve each count through its own
// fragment key first, then interpolate both resolved phrases into a
// non-pluralized sentence shell. These tests exercise that exact composition,
// covering a 0/1/n mix across the two counts (not just the diagonal).
describe('autoAllocateSuccess (two independent counts composed via a fragment key)', () => {
  function composeBought(created: number, updated: number): string {
    const createdPhrase = t('boughtItems.demands.detail.allocationsCountPhrase', created)
    const updatedPhrase = t('boughtItems.demands.detail.allocationsCountPhrase', updated)
    return t('boughtItems.demands.detail.autoAllocateSuccess', { createdPhrase, updatedPhrase })
  }
  function composeSource(created: number, updated: number): string {
    const createdPhrase = t('sourceItems.demands.detail.allocationsCountPhrase', created)
    const updatedPhrase = t('sourceItems.demands.detail.allocationsCountPhrase', updated)
    return t('sourceItems.demands.detail.autoAllocateSuccess', { createdPhrase, updatedPhrase })
  }
  function expectedDeAtSuccess(
    feature: 'boughtItems' | 'sourceItems',
    created: number,
    updated: number,
  ): string {
    const phraseKey = `${feature}.demands.detail.allocationsCountPhrase`
    return expectedDeAt(`${feature}.demands.detail.autoAllocateSuccess`, 0, {
      createdPhrase: expectedDeAt(phraseKey, created),
      updatedPhrase: expectedDeAt(phraseKey, updated),
    })
  }

  it('boughtItems: created and updated pluralize independently, in both locales', () => {
    setLocale('enGB')
    expect(composeBought(0, 1)).toBe('Created 0 allocations, updated 1 allocation.')
    expect(composeBought(1, 0)).toBe('Created 1 allocation, updated 0 allocations.')
    expect(composeBought(3, 2)).toBe('Created 3 allocations, updated 2 allocations.')

    setLocale('deAT')
    expect(composeBought(0, 1)).toBe(expectedDeAtSuccess('boughtItems', 0, 1))
    expect(composeBought(1, 0)).toBe(expectedDeAtSuccess('boughtItems', 1, 0))
    expect(composeBought(3, 2)).toBe(expectedDeAtSuccess('boughtItems', 3, 2))
  })

  it('sourceItems: created and updated pluralize independently, in both locales', () => {
    setLocale('enGB')
    expect(composeSource(0, 1)).toBe('Created 0 allocations, updated 1 allocation.')
    setLocale('deAT')
    expect(composeSource(0, 1)).toBe(expectedDeAtSuccess('sourceItems', 0, 1))
  })
})

describe('forceStatus.{complete,cancel}.warning (two independent counts composed via a fragment key)', () => {
  function composeWarning(action: 'complete' | 'cancel', orders: number, items: number): string {
    const ordersPhrase = t('production.lots.detail.forceStatus.inProgressOrdersPhrase', orders)
    const itemsPhrase = t('production.lots.detail.forceStatus.orderItemsPhrase', items)
    return t(`production.lots.detail.forceStatus.${action}.warning`, { ordersPhrase, itemsPhrase })
  }
  function expectedDeAtWarning(action: 'complete' | 'cancel', orders: number, items: number): string {
    return expectedDeAt(`production.lots.detail.forceStatus.${action}.warning`, 0, {
      ordersPhrase: expectedDeAt('production.lots.detail.forceStatus.inProgressOrdersPhrase', orders),
      itemsPhrase: expectedDeAt('production.lots.detail.forceStatus.orderItemsPhrase', items),
    })
  }

  it('complete: pluralizes orders and items independently, in both locales', () => {
    setLocale('enGB')
    expect(composeWarning('complete', 0, 0)).toBe(
      'The lot closes short at what its last step has produced. This touches no in-progress production orders and no order items: a production order stops at the pieces it processed and is canceled when it processed none, and an order item is closed short at what was delivered and canceled when nothing was. Nothing is booked as delivered. This cannot be undone.',
    )
    expect(composeWarning('complete', 1, 2)).toBe(
      'The lot closes short at what its last step has produced. This touches 1 in-progress production order and 2 order items: a production order stops at the pieces it processed and is canceled when it processed none, and an order item is closed short at what was delivered and canceled when nothing was. Nothing is booked as delivered. This cannot be undone.',
    )

    setLocale('deAT')
    expect(composeWarning('complete', 0, 0)).toBe(expectedDeAtWarning('complete', 0, 0))
    expect(composeWarning('complete', 1, 2)).toBe(expectedDeAtWarning('complete', 1, 2))
  })

  it('cancel: pluralizes orders and items independently, in both locales', () => {
    setLocale('enGB')
    expect(composeWarning('cancel', 3, 1)).toBe(
      'This cancels 3 in-progress production orders and affects 1 order item. An order item with nothing delivered is canceled, but one already ordered from the supplier stays open for purchasing to settle, and one with pieces delivered is closed short at those pieces. This cannot be undone.',
    )

    setLocale('deAT')
    expect(composeWarning('cancel', 3, 1)).toBe(expectedDeAtWarning('cancel', 3, 1))
  })
})

describe('dead users.* keys removed (11-Low)', () => {
  it('no longer resolve - t() falls through to the raw key path', () => {
    setLocale('enGB')
    expect(t('users.title')).toBe('users.title')
    expect(t('users.fullName')).toBe('users.fullName')
    expect(t('users.email')).toBe('users.email')
  })
})
