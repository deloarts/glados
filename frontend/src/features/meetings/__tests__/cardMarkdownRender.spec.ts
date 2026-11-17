import { describe, expect, it } from 'vitest'

import { cardImageFileIds, renderCardMarkdown } from '../utils/cardMarkdownRender'

describe('renderCardMarkdown', () => {
  it('renders the subset', () => {
    const html = renderCardMarkdown('### Decisions\n\n- **Bold** and *italic*\n- `code`\n\n1. one')

    expect(html).toContain('<h3>Decisions</h3>')
    expect(html).toContain('<strong>Bold</strong>')
    expect(html).toContain('<em>italic</em>')
    expect(html).toContain('<code>code</code>')
    expect(html).toContain('<ol>')
  })

  it('keeps a single line break inside a paragraph', () => {
    expect(renderCardMarkdown('one\ntwo')).toBe('<p>one<br>\ntwo</p>\n')
  })

  it('shows a mention with the current name of the user', () => {
    const html = renderCardMarkdown('Ask @[Anna](user:2) today', { userName: (id) => (id === 2 ? 'Anna Generic' : undefined) })

    const mention = new DOMParser().parseFromString(html, 'text/html').querySelector('.card-mention')
    expect(mention?.textContent).toBe('@Anna Generic')
    expect(mention?.getAttribute('data-user-id')).toBe('2')
    expect(html).toContain('Ask ')
    expect(html).not.toContain('user:2')
  })

  it('keeps the stored name of a user it does not know', () => {
    expect(renderCardMarkdown('@[Former Colleague](user:9)')).toContain('@Former Colleague</span>')
  })

  it('shows an image of the meeting once its file has loaded', () => {
    expect(renderCardMarkdown('![rig](file:5)', { imageUrl: () => 'blob:http://localhost/abc' })).toContain(
      'src="blob:http://localhost/abc"',
    )
    expect(renderCardMarkdown('![rig](file:5)')).toContain('data-file-id="5"')
  })

  it('opens web links in a new tab and keeps raw HTML as text', () => {
    const html = renderCardMarkdown('[Glados](https://glados.example) <b>no</b>')

    expect(html).toContain('href="https://glados.example"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('&lt;b&gt;no&lt;/b&gt;')
  })

  it('keeps a script link as text and drops a mention link without its @', () => {
    expect(renderCardMarkdown('[x](javascript:alert(1))')).not.toContain('<a')
    expect(renderCardMarkdown('[x](user:2)')).not.toContain('href')
  })

  it('lists the files a body shows', () => {
    expect(cardImageFileIds('![a](file:5) text ![b](file:7)')).toEqual([5, 7])
  })
})
