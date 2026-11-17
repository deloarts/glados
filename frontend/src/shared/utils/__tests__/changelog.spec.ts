import { describe, expect, it } from 'vitest'

import { parseChangelogEntry } from '../changelog'

describe('parseChangelogEntry', () => {
  it('splits timestamp, user and message, keeping commas in the message', () => {
    expect(parseChangelogEntry('2026-10-09 10:00, alice, Changed name, then unit')).toEqual({
      timestamp: '2026-10-09 10:00',
      username: 'alice',
      message: 'Changed name, then unit',
    })
  })

  it('leaves missing parts empty', () => {
    expect(parseChangelogEntry('2026-10-09 10:00')).toEqual({
      timestamp: '2026-10-09 10:00',
      username: '',
      message: '',
    })
  })
})
