import { ref } from 'vue'

export interface TypewriterOptions {
  /** The line typed over and over, one row at a time. */
  phrase: string
  /** Stop once this many rows have been completed. Defaults to never stopping. */
  maxRows?: number
  /**
   * Retain only this many completed rows, dropping the oldest. Without it a
   * run that never ends would grow the array forever.
   */
  keepRows?: number
  /** Base delay between characters. */
  charDelayMs?: number
  /** Pause after a row completes, before the next one starts. */
  rowDelayMs?: number
  /**
   * Fraction of `charDelayMs` to vary each keystroke by, which is what stops
   * the typing reading as a machine playing back a string. Tests pass 0 to
   * make the schedule deterministic.
   */
  jitterRatio?: number
}

/**
 * Types `phrase` into row after row, character by character.
 *
 * Deliberately hand-rolled rather than pulling in typed.js: the terminal only
 * ever types forward, so none of that library's backspacing, string cycling or
 * smart-backspace applies, and its 3.x line is GPL-3.0.
 *
 * Everything runs off a single `setTimeout` handle rather than one timer per
 * character, so `stop()` cancels the whole run and there is nothing left to
 * leak if the caller unmounts mid-row.
 */
export function useTypewriter(options: TypewriterOptions) {
  const {
    phrase,
    maxRows = Number.POSITIVE_INFINITY,
    keepRows = Number.POSITIVE_INFINITY,
    charDelayMs = 35,
    rowDelayMs = 90,
    jitterRatio = 0.4,
  } = options

  /** Rows that have finished typing, oldest first. */
  const rows = ref<string[]>([])
  /** The row currently being typed, as far as it has got. */
  const current = ref('')
  const isDone = ref(false)

  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false
  /** Counted separately from `rows.length`, which `keepRows` trims. */
  let completedRows = 0

  function nextCharDelay(): number {
    if (jitterRatio <= 0) return charDelayMs
    return charDelayMs * (1 + (Math.random() * 2 - 1) * jitterRatio)
  }

  function schedule(delay: number): void {
    timer = setTimeout(tick, delay)
  }

  function tick(): void {
    timer = null
    if (!running) return

    if (current.value.length < phrase.length) {
      current.value = phrase.slice(0, current.value.length + 1)
      schedule(nextCharDelay())
      return
    }

    const completed = [...rows.value, current.value]
    rows.value = completed.length > keepRows ? completed.slice(-keepRows) : completed
    completedRows++
    current.value = ''

    if (completedRows >= maxRows) {
      running = false
      isDone.value = true
      return
    }

    schedule(rowDelayMs)
  }

  /** Restarts from an empty screen; safe to call while already running. */
  function start(): void {
    stop()
    rows.value = []
    current.value = ''
    completedRows = 0
    isDone.value = false
    running = true
    schedule(nextCharDelay())
  }

  function stop(): void {
    running = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  return { rows, current, isDone, start, stop }
}
