import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import type Token from 'markdown-it/lib/token.mjs'

/**
 * The reading view of a card body, as sanitised HTML for v-html. It follows
 * the approach of the infoscreen messages (`messageMarkdown.ts`): markdown-it
 * with raw HTML off, then DOMPurify with an allow-list of the tags the subset
 * produces. Mentions `@[Name](user:<id>)` show as a chip with the user's
 * current name, and images `![alt](file:<id>)` take the object URL of the
 * meeting file once it has loaded, since storage hands out no browser URL.
 */
export interface CardRenderContext {
  /** The current name of a user, or undefined to keep the name in the text. */
  userName?: (id: number) => string | undefined
  /** The object URL of a loaded meeting file, or undefined while it loads. */
  imageUrl?: (fileId: number) => string | undefined
}

const USER_HREF = /^user:(\d+)$/
const FILE_SRC = /^file:(\d+)$/

const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true, typographer: false })
// The subset has no quotes, code blocks, rules, tables or strike-through;
// the backend escapes their syntax, and these rules stay off so text that
// slipped through still reads as text.
markdown.disable(['blockquote', 'code', 'fence', 'hr', 'table', 'lheading', 'strikethrough', 'reference'])
// markdown-it refuses `file:` targets; the subset allows web and mail links,
// mentions and meeting files only.
markdown.validateLink = (url) => /^(https?:\/\/|mailto:)/i.test(url) || USER_HREF.test(url) || FILE_SRC.test(url)

function context(env: unknown): CardRenderContext {
  return (env ?? {}) as CardRenderContext
}

// A mention is the text "@" followed by a link to user:<id>; it becomes one
// chip whose text is the user's current name.
markdown.core.ruler.push('card_mentions', (state) => {
  for (const block of state.tokens) {
    if (block.type !== 'inline' || !block.children) continue
    const children = block.children
    for (let i = 0; i < children.length; i += 1) {
      const open = children[i] as Token
      const match = open.type === 'link_open' ? USER_HREF.exec(open.attrGet('href') ?? '') : null
      const before = children[i - 1]
      if (!match || before?.type !== 'text' || !before.content.endsWith('@')) continue
      const close = children.findIndex((token, index) => index > i && token.type === 'link_close')
      if (close === -1) continue
      before.content = before.content.slice(0, -1)
      const name = children
        .slice(i + 1, close)
        .map((token) => token.content)
        .join('')
      const mention = new state.Token('card_mention', 'span', 0)
      mention.meta = { userId: Number(match[1]), name }
      children.splice(i, close - i + 1, mention)
    }
  }
})

markdown.renderer.rules.card_mention = (tokens, idx, _options, env) => {
  const { userId, name } = (tokens[idx] as Token).meta as { userId: number; name: string }
  const shown = context(env).userName?.(userId) ?? name
  return `<span class="card-mention" data-user-id="${userId}">@${markdown.utils.escapeHtml(shown)}</span>`
}

markdown.renderer.rules.image = (tokens, idx, _options, env) => {
  const token = tokens[idx] as Token
  const alt = markdown.utils.escapeHtml(token.content)
  const match = FILE_SRC.exec(token.attrGet('src') ?? '')
  if (!match) return alt
  const fileId = Number(match[1])
  const url = context(env).imageUrl?.(fileId)
  const src = url ? ` src="${markdown.utils.escapeHtml(url)}"` : ''
  return `<img class="card-image" data-file-id="${fileId}" alt="${alt}"${src}>`
}

const defaultLinkOpen =
  markdown.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx] as Token
  token.attrSet('target', '_blank')
  token.attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

const ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h3', 'code', 'a', 'span', 'img']
const ALLOWED_ATTR = ['href', 'target', 'rel', 'class', 'src', 'alt', 'start', 'data-user-id', 'data-file-id']
// DOMPurify's own default with the object URLs of loaded images added: web
// and mail links, and values without a scheme, such as a link's target, but
// no other scheme.
const ALLOWED_URI_REGEXP = /^(?:(?:https?|mailto|blob):|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i

/** The card body as sanitised HTML, ready for v-html. */
export function renderCardMarkdown(body: string, ctx: CardRenderContext = {}): string {
  return DOMPurify.sanitize(markdown.render(body, { ...ctx } as Record<string, unknown>), { ALLOWED_TAGS, ALLOWED_ATTR, ALLOWED_URI_REGEXP })
}

/** The file ids of the images a body shows, to load them before it renders. */
export function cardImageFileIds(body: string): number[] {
  return [...body.matchAll(/!\[[^[\]\n]*\]\(file:(\d+)\)/g)].map((match) => Number(match[1]))
}
