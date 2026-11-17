import { describe, it, expect } from 'vitest'

import { detectDocketFields, detectZplPlaceholders } from '../templateFields'

describe('detectZplPlaceholders', () => {
  it('returns each lower-case brace token once, sorted', () => {
    expect(detectZplPlaceholders('^FD{b_field}^FS^FD{a1}^FS{b_field}{Upper}{1x}')).toEqual([
      'a1',
      'b_field',
    ])
  })
})

describe('detectDocketFields', () => {
  it('collects block and table column fields, skips "@" fields, and sorts', () => {
    const spec = JSON.stringify({
      blocks: [{ field: 'lot_number' }, { field: '@page' }, { type: 'line' }],
      table: { columns: [{ fields: ['qty', 'name'] }, { fields: 'not-a-list' }] },
    })
    expect(detectDocketFields(spec)).toEqual(['lot_number', 'name', 'qty'])
  })

  it('detects nothing in malformed or non-object JSON', () => {
    expect(detectDocketFields('{"blocks": [')).toEqual([])
    expect(detectDocketFields('42')).toEqual([])
  })
})
