/**
 * Incremental parser for the `text/event-stream` wire format. TCP splits
 * chunks arbitrarily, so frames (blank-line-terminated) and even single
 * lines can straddle two `push()` calls; everything is buffered until a
 * full frame is available.
 */
export interface SseFrame {
  event: string
  data: string
}

export interface SseParser {
  /**
   * Feed a decoded chunk. Emits zero or more complete frames via the
   * callback passed to `createSseParser`.
   */
  push: (chunk: string) => void
}

export function createSseParser(onFrame: (frame: SseFrame) => void): SseParser {
  let buffer = ''

  return {
    push(chunk: string): void {
      // The backend pins sep="\n" (see live.py), but normalize CRLF -> LF
      // defensively, because the SSE spec allows either as a line terminator.
      buffer += chunk.replace(/\r\n/g, '\n')

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)

        const frame = parseFrame(rawFrame)
        if (frame) onFrame(frame)

        boundary = buffer.indexOf('\n\n')
      }
    },
  }
}

function parseFrame(raw: string): SseFrame | null {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of raw.split('\n')) {
    if (line === '' || line.startsWith(':')) continue // comment / keepalive ping

    const colonIndex = line.indexOf(':')
    const field = colonIndex === -1 ? line : line.slice(0, colonIndex)
    let value = colonIndex === -1 ? '' : line.slice(colonIndex + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }

  if (dataLines.length === 0) return null // pure comment frame (ping)
  return { event, data: dataLines.join('\n') }
}
