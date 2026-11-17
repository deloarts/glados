import { describe, it, expect } from 'vitest'

import { buildPdmReconciliationExportRows } from '../pdmReconciliationExport'

import type { PdmReconciliationFinding } from '../../types/adminSettingsTypes'

function makeFinding(overrides: Partial<PdmReconciliationFinding> = {}): PdmReconciliationFinding {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    run_id: 1,
    category: 'stuck_file',
    severity: 'warning',
    kind: 'made',
    item_id: 99,
    file_id: 42,
    part_number: 'PUR-26-00001',
    revision: 'A',
    message: 'File has not been ingested for 9 days.',
    count: 1,
    created_at: '2026-09-04T10:00:03Z',
    ...overrides,
  }
}

describe('buildPdmReconciliationExportRows', () => {
  const labels = {
    category: (category: string) => `category:${category}`,
    severity: (severity: string) => `severity:${severity}`,
    kind: (kind: string | null) => (kind === null ? 'kind:none' : `kind:${kind}`),
  }

  it('maps each finding to the fixed export column set, resolving labels through the given functions', () => {
    const rows = buildPdmReconciliationExportRows([makeFinding()], labels)

    expect(rows).toEqual([
      {
        category: 'category:stuck_file',
        severity: 'severity:warning',
        kind: 'kind:made',
        partNumber: 'PUR-26-00001',
        revision: 'A',
        message: 'File has not been ingested for 9 days.',
        count: 1,
      },
    ])
  })

  it('renders null part_number/revision/kind as blank rather than a placeholder dash', () => {
    const rows = buildPdmReconciliationExportRows(
      [makeFinding({ kind: null, part_number: null, revision: null })],
      labels,
    )

    expect(rows[0]).toMatchObject({ partNumber: '', revision: '', kind: 'kind:none' })
  })

  it('preserves input order and produces one row per finding', () => {
    const rows = buildPdmReconciliationExportRows(
      [
        makeFinding({ id: 1, category: 'stuck_file' }),
        makeFinding({ id: 2, category: 'revision_lag' }),
        makeFinding({ id: 3, category: 'duplicate_part_number' }),
      ],
      labels,
    )

    expect(rows.map((r) => r.category)).toEqual([
      'category:stuck_file',
      'category:revision_lag',
      'category:duplicate_part_number',
    ])
  })

  it('returns an empty array for an empty findings list', () => {
    expect(buildPdmReconciliationExportRows([], labels)).toEqual([])
  })
})
