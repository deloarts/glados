import { describe, expect, it } from 'vitest'

import type { PlcTag, PlcTagList } from '../../types/productDevice'
import { buildPlcTagRows } from '../plcTagExport'

const TAG: PlcTag = {
  device_id: 1,
  device_name: 'B01-B Spannzylinder P1',
  device_name_ascii: 'B01_B_Spannzylinder_P1',
  component_id: 10,
  signal_index: 0,
  name: 'di_B01_B_Spannzylinder_P1_AUS',
  tag_table: 'Standard-Variablentabelle',
  address: 'I150.0',
  comment: 'B01-B Spannzylinder P1: ausgefahren',
  signal_type: 'di',
  safety: false,
  data_type: '',
  overridden: false,
  too_long: false,
  duplicate: false,
  manual_id: null,
}

describe('buildPlcTagRows', () => {
  it('writes one column per export column, constants included', () => {
    const list: PlcTagList = {
      environment: {
        id: 1,
        name: 'TIA',
        max_tag_length: 128,
        export_sheet: 'PLC Tags',
        export_columns: [
          { header: 'Name', source: 'tag_name', value: null },
          { header: 'Path', source: 'tag_table', value: null },
          { header: 'Logical Address', source: 'address', value: null },
          { header: 'Hmi Visible', source: 'constant', value: 'True' },
        ],
      },
      tags: [TAG, { ...TAG, name: 'dq_x', address: null }],
    }
    expect(buildPlcTagRows(list)).toEqual([
      ['Name', 'Path', 'Logical Address', 'Hmi Visible'],
      ['di_B01_B_Spannzylinder_P1_AUS', 'Standard-Variablentabelle', 'I150.0', 'True'],
      ['dq_x', 'Standard-Variablentabelle', '', 'True'],
    ])
  })
})
