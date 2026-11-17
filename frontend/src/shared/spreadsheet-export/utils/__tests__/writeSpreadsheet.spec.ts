import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as XLSX from 'xlsx'

import { downloadBlob } from '@/core/utils/downloadBlob'
import { buildWorksheet } from '../buildWorksheet'
import { writeSpreadsheetFile } from '../writeSpreadsheet'

vi.mock('@/core/utils/downloadBlob', () => ({
  downloadBlob: vi.fn<(blob: Blob, filename: string) => void>(),
}))

interface Row {
  partNumber: string
  mass: number
  created: string
  url: string
}

async function writtenWorkbook(): Promise<{ workbook: XLSX.WorkBook; filename: string }> {
  const [blob, filename] = vi.mocked(downloadBlob).mock.calls[0]!
  const workbook = XLSX.read(await blob.arrayBuffer(), { cellNF: true })
  return { workbook, filename }
}

describe('writeSpreadsheetFile', () => {
  beforeEach(() => {
    vi.mocked(downloadBlob).mockReset()
  })

  it('downloads a workbook SheetJS reads back with types, formats, links and the autofilter', async () => {
    const worksheet = buildWorksheet<Row>(
      [{ partNumber: '00042', mass: 12.5, created: '2026-11-12T09:30:00Z', url: 'https://example.com/a' }],
      [
        { header: 'Part Number', value: (row) => row.partNumber },
        { header: 'Mass', value: (row) => row.mass },
        { header: 'Created', value: (row) => ({ iso: row.created }) },
        { header: 'Link', value: (row) => ({ text: row.url, url: row.url }) },
      ],
      'UTC',
    )

    await writeSpreadsheetFile(worksheet, { sheetName: 'Bought Items', filename: 'export.xlsx' })

    const { workbook, filename } = await writtenWorkbook()
    expect(filename).toBe('export.xlsx')
    expect(workbook.SheetNames).toEqual(['Bought Items'])

    const sheet = workbook.Sheets['Bought Items']!
    expect(sheet['!ref']).toBe('A1:D2')
    expect(sheet['!autofilter']).toEqual({ ref: 'A1:D2' })
    expect(sheet.A1?.v).toBe('Part Number')
    expect(sheet.A2).toMatchObject({ t: 's', v: '00042' })
    expect(sheet.B2).toMatchObject({ t: 'n', v: 12.5 })
    expect(sheet.C2).toMatchObject({ t: 'n', z: 'yyyy-mm-dd hh:mm' })
    expect(sheet.D2?.l?.Target).toBe('https://example.com/a')
  })
})
