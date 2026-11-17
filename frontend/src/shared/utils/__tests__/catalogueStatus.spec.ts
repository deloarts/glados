import { describe, expect, it } from 'vitest'

import { catalogueStatusTagSeverity, pdmSyncStateSeverity } from '../catalogueStatus'

describe('catalogueStatusTagSeverity', () => {
  it.each([
    ['active', 'success'],
    ['replaced', 'warn'],
    ['inactive', 'danger'],
  ] as const)('maps the %s status to %s', (status, severity) => {
    expect(catalogueStatusTagSeverity(status)).toBe(severity)
  })

  it('shows an unknown status like an inactive one', () => {
    expect(catalogueStatusTagSeverity('archived')).toBe('danger')
  })
})

describe('pdmSyncStateSeverity', () => {
  it.each([
    ['synced', 'success'],
    ['missing', 'warn'],
    ['conflict', 'danger'],
  ] as const)('maps the %s state to %s', (state, severity) => {
    expect(pdmSyncStateSeverity(state)).toBe(severity)
  })
})
