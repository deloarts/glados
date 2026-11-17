/**
 * The file format of a mail template: one HTML file per kind and language,
 * named `<kind>.<language>.html`, whose `<title>` is the subject. A full
 * document keeps its `<title>` in the body, as the stored templates do. A
 * fragment, such as a supplier template, has no head of its own, so the
 * export puts the subject in a leading `<title>` line and the import takes
 * that line out of the body again.
 */

const FILE_NAME = /^([a-z][a-z_]*)\.([A-Za-z]{4})\.html?$/
const TITLE = /<title[^>]*>([\s\S]*?)<\/title>/i
const LEADING_TITLE = /^\s*<title[^>]*>[\s\S]*?<\/title>[^\S\n]*\n?/i
const FULL_DOCUMENT = /<(html|head)[\s>]/i
const HEAD_OPEN = /<head(\s[^>]*)?>/i

export interface MailTemplateFileTarget {
  kind: string
  language: string
}

export interface MailTemplateFileContent {
  subject: string
  body: string
}

/** The kind and language a file name stands for, or null for any other name. */
export function mailTemplateFileTarget(fileName: string): MailTemplateFileTarget | null {
  const match = FILE_NAME.exec(fileName)
  if (!match) return null
  return { kind: match[1]!, language: match[2]! }
}

export function mailTemplateFileName(kind: string, language: string): string {
  return `${kind}.${language}.html`
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function unescapeHtml(text: string): string {
  return text
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
}

export function parseMailTemplateFile(text: string): MailTemplateFileContent {
  const match = TITLE.exec(text)
  const subject = match ? unescapeHtml(match[1]!.trim()) : ''
  const body = FULL_DOCUMENT.test(text) ? text : text.replace(LEADING_TITLE, '')
  return { subject, body }
}

export function serializeMailTemplateFile({ subject, body }: MailTemplateFileContent): string {
  const title = `<title>${escapeHtml(subject)}</title>`
  if (TITLE.test(body)) return body.replace(TITLE, () => title)
  if (HEAD_OPEN.test(body)) return body.replace(HEAD_OPEN, (head) => `${head}\n  ${title}`)
  return `${title}\n${body}`
}

export type MailTemplateImportStatus =
  | 'new'
  | 'replaces'
  | 'badName'
  | 'unknownKind'
  | 'unknownLanguage'
  | 'duplicate'

export interface MailTemplateImportRow {
  fileName: string
  kind: string | null
  language: string | null
  subject: string
  body: string
  status: MailTemplateImportStatus
}

/** Whether a row of an import plan is saved when the admin confirms it. */
export function isImportable(row: MailTemplateImportRow): boolean {
  return row.status === 'new' || row.status === 'replaces'
}

/**
 * What importing the picked files would do, one row per file. A file is
 * importable when its name names a known kind and an enabled language; it
 * replaces the current template when that pair is configured already. When
 * a pair is picked twice, the last file counts and the earlier ones are
 * marked as duplicates.
 */
export function planMailTemplateImport(
  files: { name: string; text: string }[],
  kinds: readonly string[],
  languages: readonly string[],
  isConfigured: (kind: string, language: string) => boolean,
): MailTemplateImportRow[] {
  const rows = files.map((file): MailTemplateImportRow => {
    const target = mailTemplateFileTarget(file.name)
    const { subject, body } = parseMailTemplateFile(file.text)
    const row = { fileName: file.name, subject, body }
    if (!target) return { ...row, kind: null, language: null, status: 'badName' }
    const { kind, language } = target
    let status: MailTemplateImportStatus
    if (!kinds.includes(kind)) status = 'unknownKind'
    else if (!languages.includes(language)) status = 'unknownLanguage'
    else status = isConfigured(kind, language) ? 'replaces' : 'new'
    return { ...row, kind, language, status }
  })
  const seen = new Set<string>()
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i]!
    if (!isImportable(row)) continue
    const key = `${row.kind}.${row.language}`
    if (seen.has(key)) row.status = 'duplicate'
    seen.add(key)
  }
  return rows
}
