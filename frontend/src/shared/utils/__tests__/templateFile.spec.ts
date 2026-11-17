import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  TEMPLATE_FILE_KINDS,
  TemplateFileError,
  parseTemplateFile,
  requireStringList,
  serializeTemplateFile,
  templateFileKindOf,
  templateFileName,
  unknownKeys,
} from '../templateFile'

function reasonOf(fn: () => unknown): string | undefined {
  try {
    fn()
  } catch (error) {
    if (error instanceof TemplateFileError) return error.reason
  }
  return undefined
}

describe('parseTemplateFile', () => {
  it('returns the content without the header', () => {
    const text = serializeTemplateFile('plc_environment', { name: 'TIA', max_tag_length: 128 })
    expect(parseTemplateFile(text, 'plc_environment')).toEqual({ name: 'TIA', max_tag_length: 128 })
  })

  it('refuses text that is no JSON', () => {
    expect(reasonOf(() => parseTemplateFile('^XA^XZ', 'print_template'))).toBe('invalidJson')
  })

  it('refuses JSON without a header', () => {
    expect(reasonOf(() => parseTemplateFile('{"page": {}}', 'print_template'))).toBe('notTemplate')
  })

  it('refuses a file of another kind and names it', () => {
    const text = serializeTemplateFile('pdm_variable_maps', {})
    let error: unknown
    try {
      parseTemplateFile(text, 'plc_environment')
    } catch (e) {
      error = e
    }
    expect(error).toBeInstanceOf(TemplateFileError)
    expect((error as TemplateFileError).reason).toBe('wrongKind')
    expect((error as TemplateFileError).detail).toBe('pdm_variable_maps')
  })

  it('refuses an unknown format version', () => {
    const text = JSON.stringify({ glados_template: 'plc_environment', version: 2 })
    expect(reasonOf(() => parseTemplateFile(text, 'plc_environment'))).toBe('unsupportedVersion')
  })
})

describe('templateFileKindOf', () => {
  it('tells a template file from a plain source file', () => {
    expect(templateFileKindOf(serializeTemplateFile('print_template', {}))).toBe('print_template')
    expect(templateFileKindOf('{"page": {"width_mm": 148}}')).toBeNull()
    expect(templateFileKindOf('^XA^XZ')).toBeNull()
  })
})

describe('content helpers', () => {
  it('names the key of an invalid value', () => {
    let error: unknown
    try {
      requireStringList({ names: ['a', 3] }, 'names')
    } catch (e) {
      error = e
    }
    expect((error as TemplateFileError).reason).toBe('invalidContent')
    expect((error as TemplateFileError).detail).toBe('names')
  })

  it('lists the keys an import does not use', () => {
    expect(unknownKeys({ name: 'x', colour: 'red' }, ['name'])).toEqual(['colour'])
  })

  it('builds a file name from a display name', () => {
    expect(templateFileName('Siemens TIA Portal', 'json')).toBe('siemens_tia_portal.json')
    expect(templateFileName('Ältere Umgebung / 2', 'json')).toBe('altere_umgebung_2.json')
    expect(templateFileName('  ', 'json')).toBe('template.json')
  })
})

// The repo's templates folder is what admins import by hand, so every JSON
// file in it with a header must name a known kind in the current version.
describe('the templates folder', () => {
  const root = resolve(process.cwd(), '../templates')

  function jsonFiles(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const path = join(dir, entry.name)
      if (entry.isDirectory()) return jsonFiles(path)
      return entry.name.endsWith('.json') ? [path] : []
    })
  }

  const files = jsonFiles(root)
  const docketSources = files.filter((file) => file.endsWith('source.json'))
  const templateFiles = files.filter((file) => !file.endsWith('source.json'))

  it('is not empty', () => {
    expect(templateFiles.length).toBeGreaterThan(0)
  })

  it.each(docketSources)('leaves the docket source %s without a header', (file) => {
    expect(templateFileKindOf(readFileSync(file, 'utf8'))).toBeNull()
  })

  it.each(templateFiles)('holds a template file of a known kind in %s', (file) => {
    const text = readFileSync(file, 'utf8')
    const kind = templateFileKindOf(text)
    expect(TEMPLATE_FILE_KINDS as readonly (string | null)[]).toContain(kind)
    expect(() => parseTemplateFile(text, kind as (typeof TEMPLATE_FILE_KINDS)[number])).not.toThrow()
  })
})
