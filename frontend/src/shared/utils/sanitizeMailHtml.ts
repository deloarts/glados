import DOMPurify from 'dompurify'

// Both sinks (MailComposeDialog's contenteditable body, and the supplier
// order-template preview) render this HTML directly into the DOM. The
// source is never trusted: order items and supplier templates are DB
// values a user with write:bought_items/write:suppliers controls, and both
// end up shown to *other* users who open the mail composer or the template
// editor.
//
// Allowlist scoped to what real saved supplier templates and
// buildTableHtml() actually produce (checked against live data): <p>,
// <strong>, <br>, plus the generated <table>/<th>/<td> with inline
// `style`. Nothing script-capable is on the list, DOMPurify strips
// event-handler attributes (onerror, onclick, ...) and dangerous elements
// (<script>, <iframe>, <object>, ...) regardless of ALLOWED_TAGS.
const ALLOWED_TAGS = [
  'p',
  'br',
  'div',
  'span',
  'strong',
  'b',
  'em',
  'i',
  'u',
  'ul',
  'ol',
  'li',
  'a',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'hr',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
]

const ALLOWED_ATTR = ['style', 'href', 'colspan', 'rowspan']

// Every surviving <a> gets a safe target/rel, DOMPurify's own
// recommendation for allowing `target` without opening a reverse-tabnabbing
// hole (a stripped `target` would just make the link open in the same tab,
// which is not itself unsafe, but forcing noopener/noreferrer here means
// the allowlist never has to omit `target` to stay safe).
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

/**
 * Sanitizes order-mail HTML (resolved templates, the compose body) before
 * it is written via `innerHTML`/`v-html`. Call this at every such sink;
 * never trust that the source has already been escaped upstream.
 */
export function sanitizeMailHtml(html: string): string {
  return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR })
}
