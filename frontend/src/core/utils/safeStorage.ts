/**
 * localStorage access that never throws. A private window, blocked site data,
 * a full quota or a runtime without storage makes the browser API throw, and
 * every caller treats that the same way: a read finds nothing and a write is
 * lost. Reads return null and writes return false instead, so a caller only
 * decides what nothing means for it.
 */

export const safeStorage = {
  /** The stored value, or null when there is none or storage is unavailable. */
  get(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },

  /** Whether the value was stored. */
  set(key: string, value: string): boolean {
    try {
      localStorage.setItem(key, value)
      return true
    } catch {
      return false
    }
  },

  /** Whether the key could be removed; a key that was never stored counts as removed. */
  remove(key: string): boolean {
    try {
      localStorage.removeItem(key)
      return true
    } catch {
      return false
    }
  },

  /** Every stored key, or none when storage is unavailable. */
  keys(): string[] {
    try {
      const keys: string[] = []
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i)
        if (key !== null) keys.push(key)
      }
      return keys
    } catch {
      return []
    }
  },
}
