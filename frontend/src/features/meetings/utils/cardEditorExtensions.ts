import { mergeAttributes } from '@tiptap/core'
import type { AnyExtension } from '@tiptap/core'
import Bold from '@tiptap/extension-bold'
import Code from '@tiptap/extension-code'
import Document from '@tiptap/extension-document'
import HardBreak from '@tiptap/extension-hard-break'
import Heading from '@tiptap/extension-heading'
import Image from '@tiptap/extension-image'
import Italic from '@tiptap/extension-italic'
import Link from '@tiptap/extension-link'
import { BulletList, ListItem, ListKeymap, OrderedList } from '@tiptap/extension-list'
import Mention from '@tiptap/extension-mention'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import { Placeholder, UndoRedo } from '@tiptap/extensions'
import type { SuggestionOptions } from '@tiptap/suggestion'

/**
 * The Tiptap extensions of the card editor: exactly the Markdown subset of
 * meeting cards and nothing more, so the editor cannot produce what the
 * subset would turn into text. Pasted HTML is read through the same schema,
 * which keeps only what these nodes and marks describe.
 */
export interface CardEditorOptions {
  placeholder?: string
  /** The current name of a user, shown on a mention instead of the stored one. */
  userName?: (id: number) => string | undefined
  /** The object URL of a loaded meeting file, for an image in the text. */
  imageUrl?: (fileId: number) => string | undefined
  /** The suggestion popup of `@` mentions; without it mentions only render. */
  mentionSuggestion?: Omit<SuggestionOptions, 'editor'>
}

export const LINK_PATTERN = /^(https?:\/\/|mailto:)\S+$/i

/** An inline image that shows a meeting file, written `![alt](file:<id>)`. */
const CardImage = Image.extend({
  addAttributes() {
    return {
      fileId: {
        default: null,
        parseHTML: (element: HTMLElement) => Number(element.getAttribute('data-file-id')) || null,
        renderHTML: (attributes: Record<string, unknown>) => ({ 'data-file-id': attributes.fileId }),
      },
      alt: { default: '' },
    }
  },
  parseHTML() {
    // Only images of this meeting; a picture pasted from a web page has no
    // meeting file behind it.
    return [{ tag: 'img[data-file-id]' }]
  },
})

export function cardEditorExtensions(options: CardEditorOptions = {}): AnyExtension[] {
  const mentionName = (id: unknown, label: unknown): string =>
    options.userName?.(Number(id)) ?? String(label ?? '')
  return [
    Document,
    Paragraph,
    Text,
    HardBreak,
    Heading.configure({ levels: [3] }),
    Bold,
    Italic,
    // Code that is bold or italic is part of the subset, so the code mark
    // takes the others along instead of excluding them.
    Code.extend({ excludes: '' }),
    BulletList,
    OrderedList,
    ListItem,
    ListKeymap,
    Link.configure({
      openOnClick: false,
      autolink: false,
      linkOnPaste: true,
      isAllowedUri: (url: string) => LINK_PATTERN.test(url),
    }),
    CardImage.configure({ inline: true, HTMLAttributes: { class: 'card-image' } }).extend({
      renderHTML({ HTMLAttributes, node }) {
        const src = options.imageUrl?.(Number(node.attrs.fileId)) ?? ''
        return ['img', mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, { src, alt: node.attrs.alt })]
      },
    }),
    Mention.configure({
      HTMLAttributes: { class: 'card-mention' },
      renderText: ({ node }) => `@${mentionName(node.attrs.id, node.attrs.label)}`,
      renderHTML: ({ node, options: mentionOptions }) => [
        'span',
        mergeAttributes(mentionOptions.HTMLAttributes, {
          'data-type': 'mention',
          'data-id': node.attrs.id,
          'data-label': node.attrs.label,
        }),
        `@${mentionName(node.attrs.id, node.attrs.label)}`,
      ],
      ...(options.mentionSuggestion && { suggestion: options.mentionSuggestion }),
    }),
    UndoRedo,
    Placeholder.configure({ placeholder: options.placeholder ?? '' }),
  ]
}
