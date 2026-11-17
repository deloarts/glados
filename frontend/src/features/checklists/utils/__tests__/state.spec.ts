import { describe, expect, it } from 'vitest'

import { CHECKLISTS } from '../definitions'
import { answersFromRecord, emptyHeader, headerFromRecord, headerToRecord } from '../state'

describe('stored checklist header', () => {
  it('round-trips through the stored record, leaving empty fields out', () => {
    const header = { ...emptyHeader(new Date(2026, 9, 9)), ownerNumber: 'P-1001', designation: 'Press 12' }
    const record = headerToRecord(header)

    expect(record).toEqual({ legalBasis: 'directive', ownerNumber: 'P-1001', designation: 'Press 12' })
    expect(headerFromRecord(record)).toEqual({ ...header, legalBasis: 'directive' })
  })

  it('drops unknown keys, clears invalid dates and derives a missing legal basis', () => {
    const header = headerFromRecord({ productId: '7', assessedOn: '31.02.2027', placingOnMarket: '2027-03-01' })

    expect(header).not.toHaveProperty('productId')
    expect(header.assessedOn).toBe('')
    expect(header.legalBasis).toBe('regulation')
  })
})

describe('stored answers', () => {
  it('keeps answers and remarks of known items and counts the rest', () => {
    const read = answersFromRecord(
      CHECKLISTS.hydraulics,
      { 'assessment.documents': 'yes', 'assessment.gone': 'no', 'assessment.circuitFunctions': 'maybe' },
      { 'assessment.documents': 'Checked', 'assessment.gone': 'Old remark', 'assessment.typeCStandard': '  ' },
    )

    expect(read.answers).toEqual({ 'assessment.documents': 'yes' })
    expect(read.remarks).toEqual({ 'assessment.documents': 'Checked' })
    expect(read.dropped).toBe(2)
  })
})
