import { describe, it, expect } from 'vitest'

import { isSafeHttpUrl, safeHref } from '../isSafeHttpUrl'

describe('isSafeHttpUrl', () => {
  it('accepts absolute http(s) URLs', () => {
    expect(isSafeHttpUrl('https://contoso.sharepoint.com/sites/hub')).toBe(true)
    expect(isSafeHttpUrl('http://intranet.local/hub')).toBe(true)
  })

  it('rejects the empty string', () => {
    expect(isSafeHttpUrl('')).toBe(false)
  })

  it('rejects non-http(s) schemes', () => {
    expect(isSafeHttpUrl('javascript:alert(1)')).toBe(false)
    expect(isSafeHttpUrl('data:text/html,<script>alert(1)</script>')).toBe(false)
    expect(isSafeHttpUrl('ftp://example.com/file')).toBe(false)
  })

  it('rejects unparsable values', () => {
    expect(isSafeHttpUrl('not a url')).toBe(false)
    expect(isSafeHttpUrl('/relative/path')).toBe(false)
  })
})

describe('safeHref', () => {
  it('returns an https URL unchanged', () => {
    expect(safeHref('https://example.com')).toBe('https://example.com')
  })

  it('returns an http URL unchanged', () => {
    expect(safeHref('http://example.com')).toBe('http://example.com')
  })

  it('rejects a mailto link by default', () => {
    expect(safeHref('mailto:foo@example.com')).toBeUndefined()
  })

  it('accepts a mailto link when allowMailto is set', () => {
    expect(safeHref('mailto:foo@example.com', { allowMailto: true })).toBe('mailto:foo@example.com')
  })

  it('accepts a mixed-case mailto link when allowMailto is set', () => {
    expect(safeHref('MAILTO:foo@example.com', { allowMailto: true })).toBe('MAILTO:foo@example.com')
  })

  it('rejects a javascript: URL', () => {
    expect(safeHref('javascript:alert(1)')).toBeUndefined()
  })

  it('rejects a mixed-case javascript: URL', () => {
    expect(safeHref('JavaScript:alert(1)')).toBeUndefined()
  })

  it('rejects a data: URL', () => {
    expect(safeHref('data:text/html,<script>alert(1)</script>')).toBeUndefined()
  })

  it('rejects a vbscript: URL', () => {
    expect(safeHref('vbscript:msgbox(1)')).toBeUndefined()
  })

  it('rejects a file: URL', () => {
    expect(safeHref('file:///etc/passwd')).toBeUndefined()
  })

  it('rejects a protocol-relative URL', () => {
    expect(safeHref('//evil.com')).toBeUndefined()
  })

  it('rejects the empty string', () => {
    expect(safeHref('')).toBeUndefined()
  })

  it('rejects a whitespace-only value', () => {
    expect(safeHref('   ')).toBeUndefined()
  })

  it('rejects null', () => {
    expect(safeHref(null)).toBeUndefined()
  })

  it('rejects undefined', () => {
    expect(safeHref(undefined)).toBeUndefined()
  })

  it('trims a safe URL before returning it', () => {
    expect(safeHref('  https://example.com  ')).toBe('https://example.com')
  })
})
