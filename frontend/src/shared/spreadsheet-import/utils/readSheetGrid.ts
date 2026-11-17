/**
 * Reads the first worksheet of an Excel file into a grid of raw cell values,
 * one array per sheet row, so header detection can look at every row before
 * deciding which one holds the column names. Date cells come back as Date
 * objects. An empty workbook gives an empty grid.
 */
export async function readSheetGrid(file: File): Promise<unknown[][]> {
  // Loaded on demand: the full SheetJS build is otherwise shipped to every
  // visitor of a page that offers an import whether or not they ever use it.
  const XLSX = await import('xlsx')
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array', cellDates: true })
  const sheetName = workbook.SheetNames[0]
  const sheet = sheetName ? workbook.Sheets[sheetName] : undefined
  if (!sheet) return []
  return XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    header: 1,
    defval: null,
    raw: true,
    blankrows: true,
  })
}
