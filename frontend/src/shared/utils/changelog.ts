/**
 * One line of an entity's free-text changelog. Every aggregate with a
 * changelog stores its lines as "timestamp, username, message", and the
 * message itself may contain further commas.
 */
export interface ChangelogEntry {
  timestamp: string
  username: string
  message: string
}

export function parseChangelogEntry(raw: string): ChangelogEntry {
  const parts = raw.split(', ')
  return {
    timestamp: parts[0] ?? '',
    username: parts[1] ?? '',
    message: parts.slice(2).join(', '),
  }
}
