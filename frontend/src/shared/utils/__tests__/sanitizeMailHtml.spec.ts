import { describe, it, expect } from 'vitest'

import { sanitizeMailHtml } from '../sanitizeMailHtml'

describe('sanitizeMailHtml', () => {
  it('strips <script> tags entirely', () => {
    const out = sanitizeMailHtml('<p>Hi</p><script>alert(document.cookie)</script>')
    expect(out).not.toContain('<script')
    expect(out).not.toContain('alert')
    expect(out).toContain('<p>Hi</p>')
  })

  it('strips onerror/onclick and other event-handler attributes', () => {
    const out = sanitizeMailHtml('<img src=x onerror="alert(1)">')
    expect(out).not.toContain('onerror')
    expect(out).not.toContain('alert')
  })

  it('strips javascript: URLs from links', () => {
    const out = sanitizeMailHtml('<a href="javascript:alert(1)">click</a>')
    expect(out).not.toContain('javascript:')
  })

  it('strips iframe/object/embed', () => {
    expect(sanitizeMailHtml('<iframe src="//evil.example"></iframe>')).not.toContain('iframe')
    expect(sanitizeMailHtml('<object data="//evil.example"></object>')).not.toContain('object')
    expect(sanitizeMailHtml('<embed src="//evil.example">')).not.toContain('embed')
  })

  it('keeps the basic formatting + table markup real templates use', () => {
    const html =
      '<p>Dear <strong>Supplier</strong>,</p><br>' +
      '<table style="border-collapse:collapse"><thead><tr>' +
      '<th style="padding:4px">Article</th></tr></thead><tbody><tr>' +
      '<td style="padding:4px">Widget</td></tr></tbody></table>'

    const out = sanitizeMailHtml(html)

    expect(out).toContain('<p>Dear <strong>Supplier</strong>,</p>')
    expect(out).toContain('<table')
    expect(out).toContain('style="border-collapse:collapse"')
    expect(out).toContain('<td style="padding:4px">Widget</td>')
  })

  it('forces a safe target/rel on surviving links', () => {
    const out = sanitizeMailHtml('<a href="https://example.com">link</a>')
    expect(out).toContain('target="_blank"')
    expect(out).toContain('rel="noopener noreferrer"')
  })

  it('drops disallowed tags but keeps their safe text content', () => {
    const out = sanitizeMailHtml('<video><source src="x"></video>Hello')
    expect(out).not.toContain('<video')
    expect(out).not.toContain('<source')
    expect(out).toContain('Hello')
  })
})
