// Messages for spreadsheetImport, merged into the en-GB locale.
export default {
  columnNames: {
    open: 'Column Names',
    title: 'Column Names',
    intro:
      'The header row of the file needs one of these names per column. Case and extra spaces do not matter, and a column with another name can be assigned by hand after the upload. Fields marked * are required.',
    field: 'Field',
    names: 'Recognised Column Names',
    none: 'No names set, assign the column by hand.',
    loadFailed: 'The column names could not be loaded.',
  },
  errors: {
    emptyFile: 'The file has no data rows.',
    headerNotFound:
      'No header row found. Check that the file has a header row with these columns: {fields}. The column names are set under Settings, Data import.',
    tooManyRows: 'The file has {count} data rows, this import accepts at most {limit}.',
  },
}
