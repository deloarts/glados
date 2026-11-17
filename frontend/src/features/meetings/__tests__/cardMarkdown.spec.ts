import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { Editor } from '@tiptap/core'
import type { JSONContent } from '@tiptap/core'

import { docToMarkdown, markdownToDoc, normaliseCardMarkdown } from '../utils/cardMarkdown'
import { cardEditorExtensions } from '../utils/cardEditorExtensions'

// The cases the backend tests its normaliser against. Reading them from the
// backend's fixture, rather than a copy, keeps the two sides in step.
interface MarkdownCase {
  name: string
  input: string
  expected: string
}

const fixture = JSON.parse(
  readFileSync(resolve(process.cwd(), '../backend/tests/fixtures/meeting_markdown_cases.json'), 'utf8'),
) as { users: number[]; files: number[]; cases: MarkdownCase[] }

const refs = { users: new Set(fixture.users), files: new Set(fixture.files) }

let editor: Editor | null = null

afterEach(() => {
  editor?.destroy()
  editor = null
})

/** The body loaded into a real editor and read back out of it. */
function throughEditor(body: string): string {
  editor = new Editor({ extensions: cardEditorExtensions(), content: markdownToDoc(body) as JSONContent })
  return docToMarkdown(editor.getJSON())
}

describe('meeting card markdown', () => {
  it('reads the shared fixture', () => {
    expect(fixture.cases.length).toBeGreaterThan(20)
  })

  describe.each(fixture.cases)('$name', (testCase) => {
    it('normalises the input as the backend does', () => {
      expect(normaliseCardMarkdown(testCase.input, refs)).toBe(testCase.expected)
    })

    it('keeps the canonical form as it is', () => {
      expect(normaliseCardMarkdown(testCase.expected, refs)).toBe(testCase.expected)
    })

    it('round-trips the canonical form through the document', () => {
      expect(docToMarkdown(markdownToDoc(testCase.expected))).toBe(testCase.expected)
    })

    it('round-trips the canonical form through the editor', () => {
      expect(throughEditor(testCase.expected)).toBe(testCase.expected)
    })
  })

  it('nests marks by how far they run', () => {
    const doc = {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'a ', marks: [{ type: 'italic' }] },
            { type: 'text', text: 'b', marks: [{ type: 'bold' }, { type: 'italic' }] },
            { type: 'text', text: ' c', marks: [{ type: 'italic' }] },
          ],
        },
      ],
    }
    expect(docToMarkdown(doc)).toBe('*a **b** c*')
  })

  it('writes a mention with its label and an image with its file', () => {
    const doc = {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'mention', attrs: { id: '7', label: 'Anna Generic' } },
            { type: 'text', text: ' sends ' },
            { type: 'image', attrs: { fileId: 5, alt: 'rig' } },
          ],
        },
      ],
    }
    expect(docToMarkdown(doc)).toBe('@[Anna Generic](user:7) sends ![rig](file:5)')
  })

  it('folds a third list level into the second', () => {
    expect(normaliseCardMarkdown('- a\n  - b\n    - c')).toBe('- a\n  - b\n  - c')
  })

  it('turns an empty document into an empty body', () => {
    expect(docToMarkdown(markdownToDoc(''))).toBe('')
  })
})
