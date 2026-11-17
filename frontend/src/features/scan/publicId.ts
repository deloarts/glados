const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isPublicId(value: string): boolean {
  return UUID_RE.test(value.trim())
}

// The link labels and report pages print: any host, then /resolve/<public id>.
const RESOLVE_LINK_RE = /^https?:\/\/[^/]+(?:\/.*)?\/resolve\/([^/?#]+)\/?(?:[?#].*)?$/i

/**
 * The public id a scanned code holds, either as it is or inside a resolve
 * link from a label or a report page; null for anything else. The host of
 * the link is not checked, so a page printed from another address of the
 * same installation still opens here.
 */
export function publicIdFromCode(code: string): string | null {
  const text = code.trim()
  if (isPublicId(text)) return text
  const id = RESOLVE_LINK_RE.exec(text)?.[1]
  return id && isPublicId(decodeURIComponent(id)) ? decodeURIComponent(id) : null
}
