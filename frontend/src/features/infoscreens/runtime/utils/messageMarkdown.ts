import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

// The text of a message widget is Markdown an admin wrote, shown on wall
// displays and in the preview through v-html. Raw HTML is off, so markup in
// the text stays text. Images are dropped, since a display must not fetch
// remote content, and a link shows as its text, since nobody can click a
// wall display. DOMPurify then keeps only the tags the Markdown below can
// produce, without any attribute, as a second line of defence.
const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true, typographer: false })

markdown.renderer.rules.image = () => ''
markdown.renderer.rules.link_open = () => ''
markdown.renderer.rules.link_close = () => ''

const ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'em',
  's',
  'ul',
  'ol',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'blockquote',
  'code',
  'pre',
  'hr',
]

/** The message as sanitised HTML, ready for v-html. */
export function renderMessageMarkdown(text: string): string {
  return DOMPurify.sanitize(markdown.render(text), { ALLOWED_TAGS, ALLOWED_ATTR: [] })
}
