/**
 * The Markdown subset of meeting cards, in the browser. A card body is
 * Markdown limited to what the card editor offers: one heading level written
 * `### `, paragraphs with line breaks, bold, italic, bullet and numbered lists
 * two levels deep, links to http, https and mailto addresses, inline code,
 * mentions `@[Name](user:<id>)` and images `![alt](file:<id>)`. Everything
 * else becomes text.
 *
 * This module is a port of the backend's `meeting_markdown.py`, which
 * normalises every saved body to one canonical spelling. Both sides test
 * against `backend/tests/fixtures/meeting_markdown_cases.json`, so a body the
 * editor writes is the body the backend keeps, and a body loaded into the
 * editor and written back is unchanged. A change to the rules goes into both
 * files and the fixtures together.
 *
 * The editor works on a ProseMirror document. `markdownToDoc` builds one from
 * Markdown and `docToMarkdown` writes it back in canonical form, both through
 * the same block and inline tree the normaliser uses.
 */

// ── The inline and block tree ─────────────────────────────────────────

export type CardInline =
  | { kind: 'text'; text: string }
  | { kind: 'break' }
  | { kind: 'code'; code: string }
  | { kind: 'mention'; name: string; userId: number }
  | { kind: 'image'; alt: string; fileId: number }
  | { kind: 'link'; children: CardInline[]; url: string }
  | { kind: 'strong'; children: CardInline[] }
  | { kind: 'em'; children: CardInline[] }

export interface CardListItem {
  inline: CardInline[]
  number: number
  children: CardList[]
}

export interface CardList {
  kind: 'list'
  ordered: boolean
  items: CardListItem[]
}

export type CardBlock = { kind: 'heading'; inline: CardInline[] } | { kind: 'paragraph'; inline: CardInline[] } | CardList

/**
 * Which user ids a mention may name and which file ids an image may show.
 * Without them every id counts, as in the editor, which cannot know them
 * all; the backend checks them on save.
 */
export interface CardMarkdownRefs {
  users?: ReadonlySet<number>
  files?: ReadonlySet<number>
}

// ── Inline parsing ────────────────────────────────────────────────────

const PUNCTUATION = new Set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
const MENTION_RE = /@\[([^[\]\n]+)\]\(user:(\d+)\)/y
const IMAGE_RE = /!\[([^[\]\n]*)\]\(([^()\s]*)\)/y
const FILE_URL_RE = /^file:(\d+)$/
const LINK_RE = /\[((?:[^[\]\n\\]|\\.)*)\]\(([^()\s]+)\)/y
const ALLOWED_LINK = /^(https?:\/\/|mailto:)\S+$/i
const WORD_RE = /^[\p{L}\p{N}]$/u
const SPACE_RE = /^\s$/

function isWord(char: string | undefined): boolean {
  return char !== undefined && WORD_RE.test(char)
}

function isSpace(char: string | undefined): boolean {
  return char !== undefined && SPACE_RE.test(char)
}

function matchAt(re: RegExp, s: string, i: number): RegExpExecArray | null {
  re.lastIndex = i
  return re.exec(s)
}

function runLength(s: string, i: number, char: string): number {
  let end = i
  while (end < s.length && s[end] === char) end += 1
  return end - i
}

/**
 * Where the backtick run that closes the code span opened at `start` begins:
 * the next run of the same length on the same line. -1 when there is none.
 */
function codeSpanEnd(s: string, start: number, run: number): number {
  const lineEnd = s.indexOf('\n', start)
  const limit = lineEnd === -1 ? s.length : lineEnd
  let i = start + run
  while (i < limit) {
    if (s[i] === '`') {
      const length = runLength(s, i, '`')
      if (length === run) return i
      i += length
      continue
    }
    i += 1
  }
  return -1
}

/**
 * The index of the delimiter that closes one opened before `start`: one
 * preceded by a non-space, not part of a longer run for a single delimiter,
 * and for an underscore not followed by a word character. Code spans are
 * skipped. -1 when there is none.
 */
function findCloser(s: string, start: number, delimiter: string): number {
  const char = delimiter[0] as string
  const width = delimiter.length
  let i = start
  while (i < s.length) {
    if (s[i] === '\\') {
      i += 2
      continue
    }
    if (s[i] === '`') {
      const run = runLength(s, i, '`')
      const end = codeSpanEnd(s, i, run)
      i = end !== -1 ? end + run : i + run
      continue
    }
    if (s[i] === char) {
      const run = runLength(s, i, char)
      if (
        run >= width &&
        i > start &&
        !isSpace(s[i - 1]) &&
        (width === 2 || run === 1) &&
        !(char === '_' && i + run < s.length && isWord(s[i + run]))
      ) {
        return width === 1 ? i : i + run - width
      }
      i += run
      continue
    }
    i += 1
  }
  return -1
}

function acceptsUser(refs: CardMarkdownRefs, id: number): boolean {
  return refs.users === undefined || refs.users.has(id)
}

function acceptsFile(refs: CardMarkdownRefs, id: number): boolean {
  return refs.files === undefined || refs.files.has(id)
}

export function parseCardInline(s: string, refs: CardMarkdownRefs = {}, inLink = false): CardInline[] {
  const nodes: CardInline[] = []
  let buf = ''

  function flush(): void {
    if (buf) {
      nodes.push({ kind: 'text', text: buf })
      buf = ''
    }
  }

  let i = 0
  while (i < s.length) {
    const char = s[i] as string
    if (char === '\\' && i + 1 < s.length && PUNCTUATION.has(s[i + 1] as string)) {
      buf += s[i + 1]
      i += 2
      continue
    }
    if (char === '\n') {
      flush()
      nodes.push({ kind: 'break' })
      i += 1
      continue
    }
    if (char === '`') {
      const run = runLength(s, i, '`')
      const end = codeSpanEnd(s, i, run)
      if (end === -1) {
        buf += '`'.repeat(run)
        i += run
        continue
      }
      let code = s.slice(i + run, end)
      if (code.length > 1 && code.startsWith(' ') && code.endsWith(' ') && code.trim()) {
        code = code.slice(1, -1)
      }
      flush()
      nodes.push({ kind: 'code', code })
      i = end + run
      continue
    }
    if (char === '@' && !inLink) {
      const match = matchAt(MENTION_RE, s, i)
      if (match) {
        const name = (match[1] as string).trim()
        const userId = Number(match[2])
        if (acceptsUser(refs, userId) && name) {
          flush()
          nodes.push({ kind: 'mention', name, userId })
        } else {
          buf += `@${name}`
        }
        i = MENTION_RE.lastIndex
        continue
      }
    }
    if (char === '!' && !inLink) {
      const match = matchAt(IMAGE_RE, s, i)
      if (match) {
        const alt = (match[1] as string).trim()
        const fileMatch = FILE_URL_RE.exec(match[2] as string)
        if (fileMatch && acceptsFile(refs, Number(fileMatch[1]))) {
          flush()
          nodes.push({ kind: 'image', alt, fileId: Number(fileMatch[1]) })
        } else {
          buf += alt
        }
        i = IMAGE_RE.lastIndex
        continue
      }
    }
    if (char === '[' && !inLink) {
      const match = matchAt(LINK_RE, s, i)
      if (match) {
        const end = LINK_RE.lastIndex
        const children = parseCardInline(match[1] as string, refs, true)
        const url = match[2] as string
        flush()
        if (ALLOWED_LINK.test(url) && children.length) nodes.push({ kind: 'link', children, url })
        else nodes.push(...children)
        i = end
        continue
      }
    }
    if (char === '*' || char === '_') {
      const run = runLength(s, i, char)
      const opens =
        i + run < s.length && !isSpace(s[i + run]) && !(char === '_' && i > 0 && isWord(s[i - 1]))
      if (opens && run >= 2) {
        const end = findCloser(s, i + 2, char + char)
        if (end !== -1) {
          flush()
          nodes.push({ kind: 'strong', children: parseCardInline(s.slice(i + 2, end), refs, inLink) })
          i = end + 2
          continue
        }
      }
      if (opens && run === 1) {
        const end = findCloser(s, i + 1, char)
        if (end !== -1) {
          flush()
          nodes.push({ kind: 'em', children: parseCardInline(s.slice(i + 1, end), refs, inLink) })
          i = end + 1
          continue
        }
      }
      buf += char.repeat(run)
      i += run
      continue
    }
    buf += char
    i += 1
  }
  flush()
  return nodes
}

// ── Serialising inline nodes ──────────────────────────────────────────

const LINE_START_ESCAPES: [RegExp, string][] = [
  [/^(\+ |[-*>])/, '\\$1'],
  [/^(#{1,6})(\s|$)/, '\\$1$2'],
  [/^(\d+)([.)])(\s|$)/, '$1\\$2$3'],
  [/^(=+\s*)$/, '\\$1'],
]
const TABLE_DELIMITER = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/

function escapeText(text: string): string {
  return text.replace(/[`*\\~[\]_]/g, (match, offset: number) => {
    if (
      match === '_' &&
      offset > 0 &&
      offset < text.length - 1 &&
      isWord(text[offset - 1]) &&
      isWord(text[offset + 1])
    ) {
      return '_'
    }
    return '\\' + match
  })
}

function escapeLineStart(text: string): string {
  let escaped = TABLE_DELIMITER.test(text) ? text.replaceAll('|', '\\|') : text
  for (const [pattern, replacement] of LINE_START_ESCAPES) {
    escaped = escaped.replace(pattern, replacement)
  }
  return escaped
}

function serialiseCode(code: string): string {
  const longest = Math.max(0, ...(code.match(/`+/g) ?? []).map((run) => run.length))
  const fence = '`'.repeat(longest + 1)
  // A reader strips one space on each side of a span that has both, so a
  // span that starts or ends with a backtick or a space gets one more.
  const spaced = code.startsWith(' ') && code.endsWith(' ') && code.trim() !== ''
  const pad = code.startsWith('`') || code.endsWith('`') || spaced ? ' ' : ''
  return `${fence}${pad}${code}${pad}${fence}`
}

/** A mention name or image alt text, without the characters that would end it. */
function label(text: string): string {
  return text.replace(/[[\]\n]/g, '').trim()
}

export function serialiseCardInline(nodes: CardInline[], continuation = '', atLineStart = true): string {
  const out: string[] = []
  let lineStart = atLineStart
  for (const node of nodes) {
    if (node.kind === 'break') {
      out.push('\n' + continuation)
      lineStart = true
      continue
    }
    if (node.kind === 'text') {
      const text = escapeText(node.text)
      out.push(lineStart ? escapeLineStart(text) : text)
    } else if (node.kind === 'code') {
      out.push(serialiseCode(node.code))
    } else if (node.kind === 'mention') {
      out.push(`@[${label(node.name)}](user:${node.userId})`)
    } else if (node.kind === 'image') {
      out.push(`![${label(node.alt)}](file:${node.fileId})`)
    } else if (node.kind === 'link') {
      out.push(`[${serialiseCardInline(node.children, continuation, false)}](${node.url})`)
    } else {
      const inner = serialiseCardInline(node.children, continuation, false)
      if (!inner.trim()) {
        out.push(inner)
      } else {
        const mark = node.kind === 'strong' ? '**' : '*'
        out.push(`${mark}${inner}${mark}`)
      }
    }
    lineStart = false
  }
  return out.join('')
}

// ── Blocks ────────────────────────────────────────────────────────────

const HEADING_RE = /^ {0,3}### +(.*?)(?: +#+)? *$/
const ITEM_RE = /^( *)([-*+]|\d{1,9}[.)])(?: +(.*))?$/

interface LineItem {
  ordered: boolean
  number: number
  lines: string[]
  children: LineList[]
}

interface LineList {
  ordered: boolean
  items: LineItem[]
}

type LineBlock = { kind: 'paragraph'; lines: string[] } | { kind: 'heading'; text: string } | ({ kind: 'list' } & LineList)

function expandTabs(line: string): string {
  const stripped = line.replace(/^[ \t]+/, '')
  const indent = line.slice(0, line.length - stripped.length).replaceAll('\t', '    ')
  return indent + stripped
}

function itemOf(match: RegExpExecArray): LineItem {
  const marker = match[2] as string
  const ordered = /\d/.test(marker[0] as string)
  return {
    ordered,
    number: ordered ? Number(marker.slice(0, -1)) : 0,
    lines: [(match[3] ?? '').trim()],
    children: [],
  }
}

function parseLineBlocks(source: string): LineBlock[] {
  const lines = source
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n')
    .split('\n')
    .map((line) => expandTabs(line).trimEnd())
  const blocks: LineBlock[] = []
  let paragraph: string[] | null = null
  let current: ({ kind: 'list' } & LineList) | null = null
  let lastItem: LineItem | null = null
  let afterBlank = false

  for (const line of lines) {
    if (!line.trim()) {
      paragraph = null
      afterBlank = true
      continue
    }
    // "**bold**" starts with a marker character but no space follows it, so
    // it is no list item.
    const itemMatch = ITEM_RE.exec(line)
    if (itemMatch) {
      const item = itemOf(itemMatch)
      const parent = current?.items.at(-1)
      paragraph = null
      if ((itemMatch[1] as string).length >= 2 && parent) {
        const last = parent.children.at(-1)
        if (last && last.ordered === item.ordered) last.items.push(item)
        else parent.children.push({ ordered: item.ordered, items: [item] })
      } else if (current && current.ordered === item.ordered) {
        current.items.push(item)
      } else {
        current = { kind: 'list', ordered: item.ordered, items: [item] }
        blocks.push(current)
      }
      lastItem = item
      afterBlank = false
      continue
    }
    if (current && lastItem) {
      const indented = line.length - line.replace(/^ +/, '').length >= 2
      if (!afterBlank || indented) {
        lastItem.lines.push(line.trim())
        afterBlank = false
        continue
      }
    }
    current = null
    lastItem = null
    afterBlank = false
    const heading = HEADING_RE.exec(line)
    if (heading && (heading[1] as string).trim()) {
      paragraph = null
      blocks.push({ kind: 'heading', text: (heading[1] as string).trim() })
      continue
    }
    if (paragraph === null) {
      paragraph = []
      blocks.push({ kind: 'paragraph', lines: paragraph })
    }
    paragraph.push(line.trim())
  }
  return blocks
}

function treeList(list: LineList, refs: CardMarkdownRefs): CardList {
  return {
    kind: 'list',
    ordered: list.ordered,
    items: list.items.map((item) => ({
      inline: parseCardInline(item.lines.join('\n'), refs),
      number: item.number,
      children: item.children.map((child) => treeList(child, refs)),
    })),
  }
}

/** The body as blocks of inline trees, read with the rules of the subset. */
export function parseCardMarkdown(body: string, refs: CardMarkdownRefs = {}): CardBlock[] {
  return parseLineBlocks(body).map((block): CardBlock => {
    if (block.kind === 'heading') return { kind: 'heading', inline: parseCardInline(block.text, refs) }
    if (block.kind === 'paragraph') {
      return { kind: 'paragraph', inline: parseCardInline(block.lines.join('\n'), refs) }
    }
    return treeList(block, refs)
  })
}

function renderList(list: CardList, indent: string, level: number): string[] {
  const out: string[] = []
  const start = list.ordered ? (list.items[0]?.number ?? 1) : 0
  const width = list.ordered ? String(start + list.items.length - 1).length : 0
  list.items.forEach((item, offset) => {
    let marker = '- '
    if (list.ordered) {
      const number = String(start + offset)
      marker = ' '.repeat(Math.max(0, width - number.length)) + `${number}. `
    }
    const continuation = indent + ' '.repeat(marker.length)
    const text = serialiseCardInline(item.inline, continuation)
    out.push(text ? (indent + marker + text).trimEnd() : (indent + marker).trimEnd())
    for (const child of item.children) {
      out.push(...renderList(child, level === 1 ? continuation : indent, 2))
    }
  })
  return out
}

/** The blocks written out in the canonical spelling. */
export function renderCardBlocks(blocks: CardBlock[]): string {
  const rendered: string[] = []
  for (const block of blocks) {
    if (block.kind === 'heading') {
      const text = serialiseCardInline(block.inline, '', false)
      if (text.trim()) rendered.push('### ' + text)
    } else if (block.kind === 'paragraph') {
      const text = serialiseCardInline(block.inline)
      if (text.trim()) rendered.push(text)
    } else if (block.items.length) {
      rendered.push(renderList(block, '', 1).join('\n'))
    }
  }
  return rendered.join('\n\n')
}

/** The body in canonical form, as the backend keeps it. */
export function normaliseCardMarkdown(body: string, refs: CardMarkdownRefs = {}): string {
  return renderCardBlocks(parseCardMarkdown(body, refs))
}

// ── The editor's document ─────────────────────────────────────────────

/** A ProseMirror node or mark as JSON, the shape Tiptap reads and writes. */
export interface CardDocMark {
  type: string
  attrs?: Record<string, unknown>
}

export interface CardDocNode {
  type: string
  attrs?: Record<string, unknown>
  marks?: CardDocMark[]
  content?: CardDocNode[]
  text?: string
}

function withMarks(node: CardDocNode, marks: CardDocMark[]): CardDocNode {
  return marks.length ? { ...node, marks } : node
}

function inlineToDoc(nodes: CardInline[], marks: CardDocMark[] = []): CardDocNode[] {
  const out: CardDocNode[] = []
  for (const node of nodes) {
    switch (node.kind) {
      case 'text':
        if (node.text) out.push(withMarks({ type: 'text', text: node.text }, marks))
        break
      case 'break':
        out.push({ type: 'hardBreak' })
        break
      case 'code':
        if (node.code) out.push({ type: 'text', text: node.code, marks: [...marks, { type: 'code' }] })
        break
      case 'mention':
        out.push(withMarks({ type: 'mention', attrs: { id: String(node.userId), label: node.name } }, marks))
        break
      case 'image':
        out.push(withMarks({ type: 'image', attrs: { fileId: node.fileId, alt: node.alt } }, marks))
        break
      case 'link':
        out.push(...inlineToDoc(node.children, [...marks, { type: 'link', attrs: { href: node.url } }]))
        break
      case 'strong':
        out.push(...inlineToDoc(node.children, [...marks, { type: 'bold' }]))
        break
      case 'em':
        out.push(...inlineToDoc(node.children, [...marks, { type: 'italic' }]))
        break
    }
  }
  return out
}

function paragraphOf(inline: CardInline[]): CardDocNode {
  const content = inlineToDoc(inline)
  return content.length ? { type: 'paragraph', content } : { type: 'paragraph' }
}

function listToDoc(list: CardList): CardDocNode {
  return {
    type: list.ordered ? 'orderedList' : 'bulletList',
    ...(list.ordered && { attrs: { start: list.items[0]?.number ?? 1 } }),
    content: list.items.map((item) => ({
      type: 'listItem',
      content: [paragraphOf(item.inline), ...item.children.map(listToDoc)],
    })),
  }
}

/** The editor document for a body. */
export function markdownToDoc(body: string): CardDocNode {
  const content = parseCardMarkdown(body).map((block): CardDocNode => {
    if (block.kind === 'heading') {
      const inline = inlineToDoc(block.inline)
      return { type: 'heading', attrs: { level: 3 }, ...(inline.length && { content: inline }) }
    }
    if (block.kind === 'paragraph') return paragraphOf(block.inline)
    return listToDoc(block)
  })
  return { type: 'doc', content: content.length ? content : [{ type: 'paragraph' }] }
}

// Nesting order for marks that start and end together: the link outside,
// then bold, then italic, as the parser reads `***both***`.
const MARK_RANK: Record<string, number> = { link: 0, bold: 1, italic: 2 }

interface Leaf {
  node: CardInline
  marks: string[]
  hrefs: Map<string, string>
}

function leafOf(node: CardDocNode): Leaf | null {
  const marks: string[] = []
  const hrefs = new Map<string, string>()
  let code = false
  for (const mark of node.marks ?? []) {
    if (mark.type === 'code') code = true
    else if (mark.type === 'bold' || mark.type === 'italic') marks.push(mark.type)
    else if (mark.type === 'link' && typeof mark.attrs?.href === 'string') {
      const key = `link:${mark.attrs.href}`
      marks.push(key)
      hrefs.set(key, mark.attrs.href)
    }
  }
  let inline: CardInline | null = null
  if (node.type === 'text' && node.text) inline = code ? { kind: 'code', code: node.text } : { kind: 'text', text: node.text }
  else if (node.type === 'hardBreak') inline = { kind: 'break' }
  else if (node.type === 'mention') {
    inline = { kind: 'mention', userId: Number(node.attrs?.id), name: String(node.attrs?.label ?? '') }
  } else if (node.type === 'image' && node.attrs?.fileId !== null && node.attrs?.fileId !== undefined) {
    inline = { kind: 'image', fileId: Number(node.attrs.fileId), alt: String(node.attrs.alt ?? '') }
  }
  return inline ? { node: inline, marks: node.type === 'hardBreak' ? [] : marks, hrefs } : null
}

function rankOf(key: string): number {
  return MARK_RANK[key.startsWith('link:') ? 'link' : key] ?? 3
}

/**
 * Nests flat ProseMirror marks into the tree the serialiser reads: a mark
 * that runs over more of the following nodes wraps the others.
 */
function docToInline(nodes: CardDocNode[]): CardInline[] {
  const leaves = nodes.map(leafOf).filter((leaf): leaf is Leaf => leaf !== null)
  const root: CardInline[] = []
  const stack: { key: string; children: CardInline[] }[] = []
  const extent = (from: number, key: string): number => {
    let count = 0
    while (from + count < leaves.length && leaves[from + count]?.marks.includes(key)) count += 1
    return count
  }
  leaves.forEach((leaf, index) => {
    const open = stack.findIndex((entry) => !leaf.marks.includes(entry.key))
    if (open !== -1) stack.length = open
    const opening = leaf.marks
      .filter((key) => !stack.some((entry) => entry.key === key))
      .sort((a, b) => extent(index, b) - extent(index, a) || rankOf(a) - rankOf(b))
    for (const key of opening) {
      const children: CardInline[] = []
      const container: CardInline =
        key === 'bold'
          ? { kind: 'strong', children }
          : key === 'italic'
            ? { kind: 'em', children }
            : { kind: 'link', url: leaf.hrefs.get(key) ?? '', children }
      ;(stack.at(-1)?.children ?? root).push(container)
      stack.push({ key, children })
    }
    ;(stack.at(-1)?.children ?? root).push(leaf.node)
  })
  return root
}

function listItemOf(item: CardDocNode, number: number): CardListItem {
  const inline: CardInline[] = []
  const children: CardList[] = []
  for (const child of item.content ?? []) {
    if (child.type === 'bulletList' || child.type === 'orderedList') {
      children.push(docToList(child))
    } else if (child.content?.length) {
      // A second paragraph of an item continues it on a new line.
      if (inline.length) inline.push({ kind: 'break' })
      inline.push(...docToInline(child.content))
    }
  }
  return { inline, number, children }
}

function docToList(node: CardDocNode): CardList {
  const ordered = node.type === 'orderedList'
  const start = ordered ? Number(node.attrs?.start ?? 1) || 1 : 0
  return {
    kind: 'list',
    ordered,
    items: (node.content ?? []).map((item, index) => listItemOf(item, start + index)),
  }
}

/** The editor document written as a body in canonical form. */
export function docToMarkdown(doc: CardDocNode): string {
  const blocks: CardBlock[] = []
  for (const node of doc.content ?? []) {
    if (node.type === 'heading') blocks.push({ kind: 'heading', inline: docToInline(node.content ?? []) })
    else if (node.type === 'paragraph') blocks.push({ kind: 'paragraph', inline: docToInline(node.content ?? []) })
    else if (node.type === 'bulletList' || node.type === 'orderedList') blocks.push(docToList(node))
  }
  // Writing it once more through the parser settles what the editor allows
  // and the subset does not, such as a third list level or leading spaces,
  // exactly as the backend will.
  return normaliseCardMarkdown(renderCardBlocks(blocks))
}
