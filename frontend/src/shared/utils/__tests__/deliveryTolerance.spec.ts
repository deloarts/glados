import { describe, it, expect } from 'vitest'

import { emptyTolerances, tolerancesToSave } from '../deliveryTolerance'

describe('tolerancesToSave', () => {
  const item = { over_delivery_tolerance_percent: 5, under_delivery_tolerance_percent: null }

  it('keeps the item values the user did not edit', () => {
    expect(tolerancesToSave(emptyTolerances(), item, new Set())).toEqual(item)
  })

  it('sends an edited value, an emptied one as null', () => {
    const form = { over_delivery_tolerance_percent: null, under_delivery_tolerance_percent: 2 }
    const edited = new Set(['over_delivery_tolerance_percent', 'under_delivery_tolerance_percent'])

    expect(tolerancesToSave(form, item, edited)).toEqual(form)
  })
})
