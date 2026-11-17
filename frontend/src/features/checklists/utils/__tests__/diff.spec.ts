import { describe, expect, it } from 'vitest'

import { CHECKLISTS } from '../definitions'
import { diffChecklists } from '../diff'

const hydraulics = CHECKLISTS.hydraulics

describe('checklist diff', () => {
  it('lists changed header fields and changed items in checklist order', () => {
    const diff = diffChecklists(
      hydraulics,
      {
        header: { legalBasis: 'directive', designation: 'Press 12', notes: 'Same' },
        answers: { 'marking.interchangeableLines': 'no', 'assessment.documents': 'yes', 'assessment.circuitFunctions': 'yes' },
        remarks: { 'marking.interchangeableLines': 'Marking missing' },
      },
      {
        header: { legalBasis: 'regulation', designation: 'Press 12', notes: 'Same', ownerNumber: 'P-1001' },
        answers: { 'marking.interchangeableLines': 'yes', 'assessment.documents': 'yes', 'assessment.typeCStandard': 'na' },
        remarks: { 'marking.interchangeableLines': 'Marking fitted' },
      },
    )

    expect(diff.header).toEqual([
      { field: 'ownerNumber', before: '', after: 'P-1001' },
      { field: 'legalBasis', before: 'directive', after: 'regulation' },
    ])
    expect(diff.items.map((change) => change.id)).toEqual([
      'assessment.circuitFunctions',
      'assessment.typeCStandard',
      'marking.interchangeableLines',
    ])
    const marking = diff.items[2]
    expect(marking).toMatchObject({
      before: { answer: 'no', remark: 'Marking missing' },
      after: { answer: 'yes', remark: 'Marking fitted' },
      answerChanged: true,
      remarkChanged: true,
    })
    expect(diff.items[0]).toMatchObject({ before: { answer: 'yes' }, after: { answer: null } })
    expect([...diff.changedIds]).toHaveLength(3)
  })

  it('keeps answers to items the type no longer has, last and without an item', () => {
    const diff = diffChecklists(
      hydraulics,
      { header: {}, answers: { 'retired.item': 'no' }, remarks: {} },
      { header: {}, answers: { 'assessment.documents': 'yes' }, remarks: {} },
    )
    expect(diff.items.map((change) => [change.id, change.item === null])).toEqual([
      ['assessment.documents', false],
      ['retired.item', true],
    ])
  })

  it('ignores whitespace-only remark changes and reports nothing for equal revisions', () => {
    const side = { header: { designation: 'A' }, answers: { 'assessment.documents': 'yes' }, remarks: {} }
    const diff = diffChecklists(hydraulics, side, {
      ...side,
      remarks: { 'assessment.documents': '  ' },
    })
    expect(diff.header).toEqual([])
    expect(diff.items).toEqual([])
  })
})
