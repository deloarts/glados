/**
 * The visible texts of pdfmake content, in reading order: what `text` holds,
 * walking into stacks, columns, table bodies and lists. Style names, colours
 * and layout values are left out, so a spec can assert on what a report says.
 */
const CONTAINERS = ['text', 'stack', 'columns', 'table', 'body', 'ul', 'ol', 'content'] as const

export function reportTexts(content: unknown): string[] {
  if (typeof content === 'string') return [content]
  if (Array.isArray(content)) return content.flatMap(reportTexts)
  if (content && typeof content === 'object') {
    const node = content as Record<string, unknown>
    return CONTAINERS.flatMap((key) => (key in node ? reportTexts(node[key]) : []))
  }
  return []
}
