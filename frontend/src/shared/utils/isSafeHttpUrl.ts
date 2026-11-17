/**
 * True only when `value` parses as an absolute `http:`/`https:` URL.
 *
 * Used to gate admin-configured URLs (e.g. the Office Launcher's SharePoint
 * tile) before they land in an `href`. Vue does not sanitise `:href`, so a
 * stored value that holds something like `javascript:alert(1)`, however it
 * got there, would run on click; this check holds client-side whatever the
 * server validated on save.
 */
export function isSafeHttpUrl(value: string): boolean {
  if (!value) return false
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

/**
 * Trims `value` and returns it only when it is safe to bind to an `href`,
 * otherwise `undefined`. Safe means an absolute `http:`/`https:` URL per
 * `isSafeHttpUrl`, plus `mailto:` links when `options.allowMailto` is set,
 * since those hand off to the mail client rather than executing anything.
 * Meant to gate any admin- or user-supplied string before it reaches a
 * template's `:href`, the same class of stored value `isSafeHttpUrl` exists
 * for.
 */
export function safeHref(
  value: string | null | undefined,
  options?: { allowMailto?: boolean },
): string | undefined {
  if (value === null || value === undefined) return undefined
  const trimmedValue = value.trim()
  if (!trimmedValue) return undefined
  if (isSafeHttpUrl(trimmedValue)) return trimmedValue
  if (options?.allowMailto && /^mailto:/i.test(trimmedValue)) return trimmedValue
  return undefined
}
