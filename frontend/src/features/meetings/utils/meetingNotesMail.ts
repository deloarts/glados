/**
 * The pieces of the meeting notes mail the send dialog works out itself:
 * the default text with its `{{ var }}` placeholders filled, which
 * documents still fit next to the PDF under the attachment limit, and the
 * addresses typed into a recipient field.
 */

export type MeetingNotesMailVars = Record<string, string>

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const PLACEHOLDER = /\{\{\s*(\w+)\s*\}\}/g

/**
 * The template's placeholders filled with the values. The body is HTML, so
 * every value is escaped there; the subject is plain text and takes the
 * values as they are. A placeholder without a value stays as written, so
 * the user sees it and can fill it in.
 */
export function fillMeetingNotesTemplate(template: string, vars: MeetingNotesMailVars, html: boolean): string {
  return template.replace(PLACEHOLDER, (whole, key: string) => {
    const value = vars[key]
    if (value === undefined) return whole
    return html ? escapeHtml(value) : value
  })
}

export const BYTES_PER_MB = 1024 * 1024

/** A size such as "2.4 MB", as the server names sizes in its refusals. */
export function formatMegabytes(bytes: number): string {
  return `${(bytes / BYTES_PER_MB).toFixed(1)} MB`
}

export interface AttachmentCandidate {
  id: number
  name: string
  size: number
}

export interface AttachmentFit<T extends AttachmentCandidate> {
  attached: T[]
  leftOut: T[]
  /** The bytes of the PDF and the documents attached. */
  total: number
}

/**
 * Which documents go along with the PDF under the limit: taken in their
 * order, each one that still fits after the PDF and the ones before it,
 * the rule the server applies when it checks the mail.
 */
export function fitAttachments<T extends AttachmentCandidate>(
  pdfBytes: number,
  documents: readonly T[],
  limitMb: number,
): AttachmentFit<T> {
  const limit = limitMb * BYTES_PER_MB
  let total = pdfBytes
  const attached: T[] = []
  const leftOut: T[] = []
  for (const document of documents) {
    if (total + document.size > limit) {
      leftOut.push(document)
      continue
    }
    total += document.size
    attached.push(document)
  }
  return { attached, leftOut, total }
}

const ADDRESS = /^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$/

/** Whether the text looks like one e-mail address; the server checks it properly. */
export function isMailAddress(value: string): boolean {
  return ADDRESS.test(value.trim())
}

/** The addresses typed or pasted into a recipient field, split at commas, semicolons and spaces. */
export function splitAddresses(value: string): string[] {
  return value
    .split(/[\s,;]+/)
    .map((part) => part.trim().replace(/^<|>$/g, ''))
    .filter(Boolean)
}

/** The list with the address added once, compared without regard to case. */
export function addAddress(list: readonly string[], address: string): string[] {
  const lower = address.toLowerCase()
  return list.some((entry) => entry.toLowerCase() === lower) ? [...list] : [...list, address]
}

export function removeAddress(list: readonly string[], address: string): string[] {
  const lower = address.toLowerCase()
  return list.filter((entry) => entry.toLowerCase() !== lower)
}

export function hasAddress(list: readonly string[], address: string): boolean {
  const lower = address.toLowerCase()
  return list.some((entry) => entry.toLowerCase() === lower)
}
