import { describe, it, expect } from 'vitest'

import { buildSettingsAuditParams, type SettingsAuditFilterValues } from '../settingsAuditParams'

const EMPTY: SettingsAuditFilterValues = {
  changedById: null,
  settingsDomain: null,
  summary: null,
  changedFrom: null,
  changedTo: null,
}

describe('buildSettingsAuditParams', () => {
  it('sends only the page while no filter is set', () => {
    expect(buildSettingsAuditParams({ skip: 25, limit: 25 }, EMPTY)).toEqual({ skip: 25, limit: 25 })
  })

  it('maps every row filter to its request param', () => {
    const params = buildSettingsAuditParams(
      { skip: 0, limit: 50 },
      {
        changedById: 5,
        settingsDomain: 'mail',
        summary: 'SMTP',
        changedFrom: new Date(2026, 8, 1),
        changedTo: new Date(2026, 8, 3),
      },
    )

    expect(params).toEqual({
      skip: 0,
      limit: 50,
      changed_by_id: 5,
      settings_domain: 'mail',
      summary: 'SMTP',
      changed_from: '2026-09-01',
      changed_to: '2026-09-03',
    })
  })

  it('leaves out whitespace-only text and an open upper bound', () => {
    const params = buildSettingsAuditParams(
      { skip: 0, limit: 25 },
      { ...EMPTY, summary: '   ', changedFrom: new Date(2026, 8, 1) },
    )

    expect(params).toEqual({ skip: 0, limit: 25, changed_from: '2026-09-01' })
  })
})
