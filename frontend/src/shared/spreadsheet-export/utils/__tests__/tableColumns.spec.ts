import { describe, expect, it } from 'vitest'

import { listCell, urlCell } from '../cells'
import { tableExportColumns } from '../tableColumns'

interface Row {
  id: number
  name: string
  tags: string[]
  image: null
}

const ROW: Row = { id: 3, name: 'Bolt', tags: ['a', 'b'], image: null }

describe('tableExportColumns', () => {
  it('keeps the visible order, writes raw values and runs the custom cells', () => {
    const columns = tableExportColumns<Row, keyof Row>({
      visibleColumns: [
        { field: 'name', header: 'Name' },
        { field: 'id', header: 'ID' },
        { field: 'tags', header: 'Tags' },
      ],
      cells: { tags: (row) => listCell(row.tags) },
    })

    expect(columns.map((column) => column.header)).toEqual(['Name', 'ID', 'Tags'])
    expect(columns.map((column) => column.value(ROW))).toEqual(['Bolt', 3, 'a, b'])
  })

  it('leaves a raw value that is neither text nor a number empty', () => {
    const [column] = tableExportColumns<Row, keyof Row>({
      visibleColumns: [{ field: 'tags', header: 'Tags' }],
    })

    expect(column?.value(ROW)).toBeNull()
  })

  it('skips columns, adds the after columns and appends the trailing ones', () => {
    const columns = tableExportColumns<Row, keyof Row>({
      visibleColumns: [
        { field: 'image', header: 'Image' },
        { field: 'name', header: 'Name' },
      ],
      skip: new Set(['image']),
      after: { name: { header: 'Name Length', value: (row) => row.name.length } },
      trailing: [{ header: 'Link', value: () => urlCell('https://example.com') }],
    })

    expect(columns.map((column) => column.header)).toEqual(['Name', 'Name Length', 'Link'])
    expect(columns[1]?.value(ROW)).toBe(4)
  })
})

describe('listCell', () => {
  it('joins the values that are set and is empty without any', () => {
    expect(listCell(['a', null, '', 'b'])).toBe('a, b')
    expect(listCell([null, undefined])).toBeNull()
  })
})
