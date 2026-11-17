/** The response header the print template endpoints list render warnings in. */
export const PREVIEW_WARNINGS_HEADER = 'x-preview-warnings'

/**
 * The warnings of a rendered print template, read from the comma separated
 * `x-preview-warnings` header value. Missing or empty gives no warnings.
 */
export function parsePreviewWarnings(header: unknown): string[] {
  if (typeof header !== 'string' || header === '') return []
  return header
    .split(',')
    .map((w) => w.trim())
    .filter(Boolean)
}
