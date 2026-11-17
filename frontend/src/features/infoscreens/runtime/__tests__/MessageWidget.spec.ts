import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import MessageWidget from '../components/widgets/MessageWidget.vue'
import type { WidgetConfigOf } from '../types/infoscreenFeed'
import { renderMessageMarkdown } from '../utils/messageMarkdown'

type MessageConfig = WidgetConfigOf<'message'>

// Built through a cast, so a test can pass a config without the alignment,
// as one stored before it existed, or with values the type does not allow.
function messageConfig(overrides: Record<string, unknown> = {}): MessageConfig {
  return {
    type: 'message',
    title: null,
    text: 'Welcome',
    severity: 'info',
    ...overrides,
  } as MessageConfig
}

function mountMessage(overrides: Record<string, unknown> = {}) {
  return mountWithApp(MessageWidget, { props: { config: messageConfig(overrides), data: null } })
}

describe('renderMessageMarkdown', () => {
  it('renders emphasis, headings and lists', () => {
    const html = renderMessageMarkdown('# Shift\n\n**Safety** first, *always*\n\n- one\n- two')

    expect(html).toContain('<h1>Shift</h1>')
    expect(html).toContain('<strong>Safety</strong>')
    expect(html).toContain('<em>always</em>')
    expect(html).toContain('<ul>\n<li>one</li>\n<li>two</li>\n</ul>')
  })

  it('keeps raw HTML as text instead of rendering it', () => {
    const html = renderMessageMarkdown('<script>alert(1)</script> <img src=x onerror="alert(2)">')

    expect(html).not.toContain('<script')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;script&gt;')
  })

  it('drops Markdown images, so a display fetches nothing remote', () => {
    const html = renderMessageMarkdown('Look ![logo](https://example.com/logo.png) here')

    expect(html).not.toContain('<img')
    expect(html).not.toContain('example.com')
  })

  it('shows a link as its text only', () => {
    const html = renderMessageMarkdown('See [the plan](https://example.com/plan) and <https://example.com>')

    expect(html).not.toContain('<a')
    expect(html).not.toContain('href')
    expect(html).toContain('the plan')
  })

  it('turns single line breaks into breaks', () => {
    expect(renderMessageMarkdown('first\nsecond')).toContain('first<br>')
  })
})

describe('MessageWidget', () => {
  it('renders the message as Markdown', () => {
    const wrapper = mountMessage({ text: 'Hall **closed** today' })

    const widget = wrapper.get('[data-testid="message-widget"]')
    expect(widget.find('strong').text()).toBe('closed')
    expect(widget.text()).toBe('Hall closed today')
  })

  it('shows the severity none without an accent', () => {
    const wrapper = mountMessage({ severity: 'none' })

    expect(wrapper.get('[data-testid="message-widget"]').classes()).toContain('message-widget--none')
  })

  it('aligns left and in the middle when the screen sets no alignment', () => {
    const classes = mountMessage().get('[data-testid="message-widget"]').classes()

    expect(classes).toContain('message-widget--text-left')
    expect(classes).toContain('message-widget--vertical-middle')
  })

  it('follows the alignment the screen sets', () => {
    const classes = mountMessage({ text_align: 'right', vertical_align: 'top' })
      .get('[data-testid="message-widget"]')
      .classes()

    expect(classes).toContain('message-widget--text-right')
    expect(classes).toContain('message-widget--vertical-top')
  })

  it('falls back to the defaults for an unknown alignment', () => {
    const classes = mountMessage({ text_align: 'justify', vertical_align: 'sideways' })
      .get('[data-testid="message-widget"]')
      .classes()

    expect(classes).toContain('message-widget--text-left')
    expect(classes).toContain('message-widget--vertical-middle')
  })
})
