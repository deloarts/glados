import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  isImportable,
  mailTemplateFileName,
  mailTemplateFileTarget,
  parseMailTemplateFile,
  planMailTemplateImport,
  serializeMailTemplateFile,
} from '../mailTemplateFile'

const DOCUMENT = `<!DOCTYPE html>
<html lang="en">
<head>
  <title>Welcome to {{ app_name }}</title>
</head>
<body><p>Hi</p></body>
</html>
`

describe('mail template file names', () => {
  it('reads kind and language from the file name', () => {
    expect(mailTemplateFileTarget('welcome.enGB.html')).toEqual({ kind: 'welcome', language: 'enGB' })
    expect(mailTemplateFileTarget('disk_space_warning.deAT.htm')).toEqual({
      kind: 'disk_space_warning',
      language: 'deAT',
    })
    expect(mailTemplateFileTarget('welcome.html')).toBeNull()
    expect(mailTemplateFileTarget('welcome (1).enGB.html')).toBeNull()
  })

  it('writes the name the import reads back', () => {
    expect(mailTemplateFileTarget(mailTemplateFileName('test_mail', 'deAT'))).toEqual({
      kind: 'test_mail',
      language: 'deAT',
    })
  })
})

describe('parseMailTemplateFile', () => {
  it('takes the subject from the title and keeps a full document whole', () => {
    expect(parseMailTemplateFile(DOCUMENT)).toEqual({ subject: 'Welcome to {{ app_name }}', body: DOCUMENT })
  })

  it('takes the leading title line out of a fragment', () => {
    const text = '<title>Order {{ order_number }} &amp; more</title>\n<p>Dear supplier</p>\n'
    expect(parseMailTemplateFile(text)).toEqual({
      subject: 'Order {{ order_number }} & more',
      body: '<p>Dear supplier</p>\n',
    })
  })

  it('reads a shipped template from the repo', () => {
    const text = readFileSync(resolve(process.cwd(), '../templates/mail/system/welcome.enGB.html'), 'utf8')
    const { subject, body } = parseMailTemplateFile(text)
    expect(subject).not.toBe('')
    expect(body).toBe(text)
  })

  it('reads a shipped compose fragment from the repo', () => {
    const text = readFileSync(resolve(process.cwd(), '../templates/mail/compose/order.enGB.html'), 'utf8')
    const { subject, body } = parseMailTemplateFile(text)
    expect(subject).toBe('Purchase order')
    expect(body).not.toContain('<title>')
    expect(body).toContain('{{ table:')
  })
})

describe('serializeMailTemplateFile', () => {
  it('writes the subject into the title of a full document', () => {
    const text = serializeMailTemplateFile({ subject: 'Hello <you>', body: DOCUMENT })
    expect(text).toContain('<title>Hello &lt;you&gt;</title>')
    expect(parseMailTemplateFile(text).subject).toBe('Hello <you>')
  })

  it('round-trips a fragment', () => {
    const content = { subject: 'Request {{ number }}', body: '<p>Dear supplier</p>\n' }
    expect(parseMailTemplateFile(serializeMailTemplateFile(content))).toEqual(content)
  })

  it('adds a title to a document head without one', () => {
    const body = '<html><head><meta charset="UTF-8"></head><body></body></html>'
    const content = parseMailTemplateFile(serializeMailTemplateFile({ subject: 'Hi', body }))
    expect(content.subject).toBe('Hi')
    expect(content.body).toContain('<head>\n  <title>Hi</title>')
  })
})

describe('planMailTemplateImport', () => {
  const kinds = ['welcome', 'test_mail']
  const languages = ['enGB', 'deAT']
  const configured = new Set(['welcome.enGB'])

  function plan(names: string[]) {
    return planMailTemplateImport(
      names.map((name) => ({ name, text: `<title>${name}</title>\n<p></p>` })),
      kinds,
      languages,
      (kind, language) => configured.has(`${kind}.${language}`),
    )
  }

  it('tells new from replacing and unusable files', () => {
    const rows = plan([
      'welcome.enGB.html',
      'welcome.deAT.html',
      'order.enGB.html',
      'welcome.frFR.html',
      'readme.html',
    ])
    expect(rows.map((r) => r.status)).toEqual(['replaces', 'new', 'unknownKind', 'unknownLanguage', 'badName'])
    expect(rows.filter(isImportable).map((r) => r.fileName)).toEqual(['welcome.enGB.html', 'welcome.deAT.html'])
  })

  it('lets the last file of a pair picked twice count', () => {
    const rows = plan(['test_mail.enGB.html', 'test_mail.enGB.htm'])
    expect(rows.map((r) => r.status)).toEqual(['duplicate', 'new'])
  })
})
