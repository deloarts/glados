import { describe, it, expect } from 'vitest'
import { createSseParser } from '../sseParser'
import type { SseFrame } from '../sseParser'

function makeParser() {
  const frames: SseFrame[] = []
  const parser = createSseParser((frame) => frames.push(frame))
  return { parser, frames }
}

describe('createSseParser', () => {
  it('parses a single-chunk event/data frame', () => {
    const { parser, frames } = makeParser()
    parser.push('event: signal\ndata: {"resource":"orders","id":1}\n\n')

    expect(frames).toEqual([{ event: 'signal', data: '{"resource":"orders","id":1}' }])
  })

  it('buffers a frame split arbitrarily across two chunks', () => {
    const { parser, frames } = makeParser()
    parser.push('event: sig')
    parser.push('nal\ndata: {"id":1}\n\n')

    expect(frames).toEqual([{ event: 'signal', data: '{"id":1}' }])
  })

  it('buffers a frame split in the middle of the blank-line terminator', () => {
    const { parser, frames } = makeParser()
    parser.push('event: signal\ndata: {"id":1}\n')
    parser.push('\n')

    expect(frames).toEqual([{ event: 'signal', data: '{"id":1}' }])
  })

  it('normalizes CRLF line endings to LF', () => {
    const { parser, frames } = makeParser()
    parser.push('event: signal\r\ndata: {"id":1}\r\n\r\n')

    expect(frames).toEqual([{ event: 'signal', data: '{"id":1}' }])
  })

  it('ignores comment/keepalive-ping lines and emits no frame for a pure comment', () => {
    const { parser, frames } = makeParser()
    parser.push(': ping - 1690000000.0\n\n')

    expect(frames).toEqual([])
  })

  it('ignores a leading comment line within an otherwise-real frame', () => {
    const { parser, frames } = makeParser()
    parser.push(': ping\nevent: signal\ndata: {"id":1}\n\n')

    expect(frames).toEqual([{ event: 'signal', data: '{"id":1}' }])
  })

  it('joins multiple data: lines with a newline, per the SSE spec', () => {
    const { parser, frames } = makeParser()
    parser.push('event: signal\ndata: line one\ndata: line two\n\n')

    expect(frames).toEqual([{ event: 'signal', data: 'line one\nline two' }])
  })

  it('defaults to event "message" when no event: field is present', () => {
    const { parser, frames } = makeParser()
    parser.push('data: {"id":1}\n\n')

    expect(frames).toEqual([{ event: 'message', data: '{"id":1}' }])
  })

  it('strips exactly one leading space after the field colon', () => {
    const { parser, frames } = makeParser()
    parser.push('data:  two spaces in\n\n')

    expect(frames).toEqual([{ event: 'message', data: ' two spaces in' }])
  })

  it('parses multiple frames delivered in one chunk, in order', () => {
    const { parser, frames } = makeParser()
    parser.push('data: first\n\ndata: second\n\n')

    expect(frames).toEqual([
      { event: 'message', data: 'first' },
      { event: 'message', data: 'second' },
    ])
  })
})
