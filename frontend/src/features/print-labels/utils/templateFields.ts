/**
 * Placeholders of a ZPL label source. Must match the backend's
 * placeholders_in() regex, so detection matches validation.
 */
const PLACEHOLDER_RE = /\{([a-z_][a-z0-9_]*)\}/g

export function detectZplPlaceholders(source: string): string[] {
  const found = new Set<string>()
  for (const match of source.matchAll(PLACEHOLDER_RE)) {
    if (match[1]) found.add(match[1])
  }
  return [...found].sort()
}

/**
 * Fields of a JSON docket block spec. Must match the backend's
 * fields_in_docket_spec(): the fields of text, image and qr blocks plus every
 * positions table column, so detection matches validation. Malformed JSON
 * detects nothing, since the textarea is usually mid-edit. "@" fields are
 * filled per page by the renderer and are not mappable.
 */
export function detectDocketFields(source: string): string[] {
  let parsed: unknown
  try {
    parsed = JSON.parse(source)
  } catch {
    return []
  }
  if (typeof parsed !== 'object' || parsed === null) return []

  const found = new Set<string>()

  const blocks = (parsed as { blocks?: unknown }).blocks
  if (Array.isArray(blocks)) {
    for (const block of blocks) {
      if (typeof block !== 'object' || block === null) continue
      const field = (block as { field?: unknown }).field
      if (typeof field === 'string' && field) found.add(field)
    }
  }

  const columns = (parsed as { table?: { columns?: unknown } }).table?.columns
  if (Array.isArray(columns)) {
    for (const column of columns) {
      if (typeof column !== 'object' || column === null) continue
      const fields = (column as { fields?: unknown }).fields
      if (!Array.isArray(fields)) continue
      for (const field of fields) {
        if (typeof field === 'string' && field) found.add(field)
      }
    }
  }

  return [...found].filter((field) => !field.startsWith('@')).sort()
}
