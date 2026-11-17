/**
 * The JSON format of a template file, the one an admin imports into a
 * settings editor or exports from it, and the format of the files in the
 * repo's `templates/` folder. Every file starts with a header naming what it
 * holds and the format version, so a file dropped into the wrong editor is
 * refused with a clear reason instead of filling half a form.
 */

export const TEMPLATE_FILE_VERSION = 1

export const TEMPLATE_FILE_KINDS = [
  'print_template',
  'plc_environment',
  'data_import_column_names',
  'pdm_variable_maps',
] as const

export type TemplateFileKind = (typeof TEMPLATE_FILE_KINDS)[number]

const HEADER_KEYS = ['glados_template', 'version']

export type TemplateFileErrorReason =
  | 'invalidJson'
  | 'notTemplate'
  | 'wrongKind'
  | 'unsupportedVersion'
  | 'invalidContent'
  | 'wrongTarget'

/**
 * Why a template file could not be read. `detail` carries the found kind for
 * `wrongKind`, the found version for `unsupportedVersion`, the offending key
 * for `invalidContent`, and what the file belongs to for `wrongTarget`, such
 * as a print template file of another classifier.
 */
export class TemplateFileError extends Error {
  constructor(
    readonly reason: TemplateFileErrorReason,
    readonly detail: string = '',
  ) {
    super(`${reason}${detail ? `: ${detail}` : ''}`)
    this.name = 'TemplateFileError'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * The kind a text names in its header, or null when the text is no template
 * file at all. Lets an editor that accepts several files tell a template
 * file from a plain source file such as a docket layout.
 */
export function templateFileKindOf(text: string): string | null {
  try {
    const parsed: unknown = JSON.parse(text)
    if (isRecord(parsed) && typeof parsed.glados_template === 'string') return parsed.glados_template
  } catch {
    // Not JSON, so not a template file.
  }
  return null
}

/** The content of a template file of `kind`, without its header. */
export function parseTemplateFile(text: string, kind: TemplateFileKind): Record<string, unknown> {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new TemplateFileError('invalidJson')
  }
  if (!isRecord(parsed) || typeof parsed.glados_template !== 'string') {
    throw new TemplateFileError('notTemplate')
  }
  if (parsed.glados_template !== kind) {
    throw new TemplateFileError('wrongKind', parsed.glados_template)
  }
  if (parsed.version !== TEMPLATE_FILE_VERSION) {
    throw new TemplateFileError('unsupportedVersion', String(parsed.version))
  }
  return Object.fromEntries(Object.entries(parsed).filter(([key]) => !HEADER_KEYS.includes(key)))
}

/** A template file of `kind` holding `content`, as the text written to disk. */
export function serializeTemplateFile(kind: TemplateFileKind, content: Record<string, unknown>): string {
  return `${JSON.stringify({ glados_template: kind, version: TEMPLATE_FILE_VERSION, ...content }, null, 2)}\n`
}

/** The string at `key`, or a TemplateFileError naming the key. */
export function requireString(content: Record<string, unknown>, key: string): string {
  const value = content[key]
  if (typeof value !== 'string') throw new TemplateFileError('invalidContent', key)
  return value
}

/** The string at `key`, null when it is null or absent. */
export function optionalString(content: Record<string, unknown>, key: string): string | null {
  const value = content[key]
  if (value === undefined || value === null) return null
  if (typeof value !== 'string') throw new TemplateFileError('invalidContent', key)
  return value
}

/** The finite number at `key`, or a TemplateFileError naming the key. */
export function requireNumber(content: Record<string, unknown>, key: string): number {
  const value = content[key]
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TemplateFileError('invalidContent', key)
  return value
}

/** The finite number at `key`, null when it is null or absent. */
export function optionalNumber(content: Record<string, unknown>, key: string): number | null {
  const value = content[key]
  if (value === undefined || value === null) return null
  return requireNumber(content, key)
}

/** The object of strings at `key`, or a TemplateFileError naming the key. */
export function requireStringMap(content: Record<string, unknown>, key: string): Record<string, string> {
  const value = content[key]
  if (!isRecord(value) || Object.values(value).some((v) => typeof v !== 'string')) {
    throw new TemplateFileError('invalidContent', key)
  }
  return value as Record<string, string>
}

/** The list of objects at `key`, or a TemplateFileError naming the key. */
export function requireRecordList(content: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = content[key]
  if (!Array.isArray(value) || !value.every(isRecord)) throw new TemplateFileError('invalidContent', key)
  return value
}

/** The object at `key`, or a TemplateFileError naming the key. */
export function requireRecord(content: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = content[key]
  if (!isRecord(value)) throw new TemplateFileError('invalidContent', key)
  return value
}

/** The list of strings at `key`, or a TemplateFileError naming the key. */
export function requireStringList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key]
  if (!Array.isArray(value) || value.some((v) => typeof v !== 'string')) {
    throw new TemplateFileError('invalidContent', key)
  }
  return value as string[]
}

/** The keys of `content` an import does not use, for the "ignored" report. */
export function unknownKeys(content: Record<string, unknown>, known: readonly string[]): string[] {
  return Object.keys(content).filter((key) => !known.includes(key))
}

/** A file name made from a display name: lower case, words joined by underscores. */
export function templateFileName(name: string, extension: string): string {
  const stem =
    name
      .normalize('NFKD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'template'
  return `${stem}.${extension}`
}
