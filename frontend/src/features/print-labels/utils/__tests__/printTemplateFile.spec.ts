import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { TemplateFileError, parseTemplateFile } from '@/shared/utils/templateFile'
import { printTemplateSettingsContent, printTemplateSettingsPatch } from '../printTemplateFile'
import type { PrintTemplateResponse } from '../../types/printTemplateResponse'

function template(overrides: Partial<PrintTemplateResponse> = {}): PrintTemplateResponse {
  return {
    classifier: 'scrap_tag',
    available_triggers: ['pieces_scrapped'],
    copies_rules: ['fixed', 'per_quantity'],
    ...overrides,
  } as PrintTemplateResponse
}

describe('printTemplateSettingsPatch', () => {
  it('reads the shipped scrap tag settings', () => {
    const text = readFileSync(resolve(process.cwd(), '../templates/print-templates/scrap_tag/settings.json'), 'utf8')
    const { patch, ignored } = printTemplateSettingsPatch(
      template(),
      parseTemplateFile(text, 'print_template'),
      false,
    )
    expect(ignored).toEqual([])
    expect(patch).toMatchObject({
      trigger: 'pieces_scrapped',
      designDpi: 203,
      labelWidthMm: 100,
      labelHeightMm: 150,
      copiesRule: 'fixed',
    })
    expect(patch.fieldMap?.lot_number).toBe('lot_number')
  })

  it('refuses the settings of another classifier', () => {
    let error: unknown
    try {
      printTemplateSettingsPatch(template(), { classifier: 'lot_label' }, false)
    } catch (e) {
      error = e
    }
    expect(error).toBeInstanceOf(TemplateFileError)
    expect((error as TemplateFileError).reason).toBe('wrongTarget')
  })

  it('ignores what the template does not offer and keeps the rest', () => {
    const { patch, ignored } = printTemplateSettingsPatch(
      template(),
      { classifier: 'scrap_tag', trigger: 'lot_created', paper: 'a4', copies_rule: 'weird', max_copies: 5, printer: 'x' },
      false,
    )
    expect(ignored.sort()).toEqual(['copies_rule', 'paper', 'printer', 'trigger'])
    expect(patch).toEqual({ maxCopies: 5 })
  })
})

describe('printTemplateSettingsContent', () => {
  it('writes what the patch reads back, leaving out unset values', () => {
    const settings = {
      trigger: null,
      paper: 'a4',
      designDpi: null,
      labelWidthMm: null,
      labelHeightMm: null,
      copiesRule: 'fixed',
      copiesFixed: 1,
      maxCopies: 50,
      fieldMap: { order_number: 'order_number' },
    }
    const content = printTemplateSettingsContent('order_docket', settings, true)
    expect(content).toEqual({
      classifier: 'order_docket',
      paper: 'a4',
      copies_rule: 'fixed',
      copies_fixed: 1,
      max_copies: 50,
      field_map: { order_number: 'order_number' },
    })
    const { patch } = printTemplateSettingsPatch(
      template({ classifier: 'order_docket', available_triggers: [] }),
      content,
      true,
    )
    expect(patch).toEqual({
      paper: 'a4',
      copiesRule: 'fixed',
      copiesFixed: 1,
      maxCopies: 50,
      fieldMap: { order_number: 'order_number' },
    })
  })
})
