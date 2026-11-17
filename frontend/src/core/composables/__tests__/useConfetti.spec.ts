import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const confettiMock = vi.fn<(options?: unknown) => void>()
const resetMock = vi.fn<() => void>()

vi.mock('canvas-confetti', () => ({
  default: Object.assign(confettiMock, { reset: resetMock }),
}))

// useConfetti keeps the last pointer position in module state, so a test
// that moves the pointer would otherwise decide where the next test's burst
// starts. Each test imports a fresh copy of the module instead.
let useConfetti: typeof import('../useConfetti').useConfetti

/**
 * jsdom has no real 2D canvas context by default (useConfetti's own canRender
 * guard exists for that reason). Stub it so tests can exercise the path that
 * actually fires confetti.
 */
function stubCanvasContext(): void {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    {} as unknown as CanvasRenderingContext2D,
  )
}

describe('useConfetti', () => {
  beforeEach(async () => {
    confettiMock.mockClear()
    resetMock.mockClear()
    vi.resetModules()
    ;({ useConfetti } = await import('../useConfetti'))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not import canvas-confetti when the environment cannot render it', async () => {
    const { celebrate } = useConfetti()

    await celebrate()

    expect(confettiMock).not.toHaveBeenCalled()
  })

  it('fires two overlapping bursts centred on the screen with no known pointer', async () => {
    stubCanvasContext()
    const { celebrate } = useConfetti()

    await celebrate()

    expect(confettiMock).toHaveBeenCalledTimes(2)
    expect(confettiMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        origin: { x: 0.5, y: 0.5 },
        spread: 360,
        disableForReducedMotion: true,
        particleCount: 70,
      }),
    )
    expect(confettiMock).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ particleCount: 45, startVelocity: 50 }),
    )
  })

  it('bursts from an explicit origin, given in viewport pixels', async () => {
    stubCanvasContext()
    Object.defineProperty(window, 'innerWidth', { value: 800, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 400, configurable: true })
    const { celebrate } = useConfetti()

    await celebrate({ x: 200, y: 100 })

    expect(confettiMock).toHaveBeenCalledWith(
      expect.objectContaining({ origin: { x: 0.25, y: 0.25 } }),
    )
  })

  it('bursts from the last known pointer position when no origin is given', async () => {
    stubCanvasContext()
    Object.defineProperty(window, 'innerWidth', { value: 1000, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 500, configurable: true })
    useConfetti()
    window.dispatchEvent(
      new PointerEvent('pointermove', { clientX: 500, clientY: 250 }),
    )
    const { celebrate } = useConfetti()

    await celebrate()

    expect(confettiMock).toHaveBeenCalledWith(
      expect.objectContaining({ origin: { x: 0.5, y: 0.5 } }),
    )
  })

  it('swallows an error thrown while firing, a decorative animation must not break its caller', async () => {
    stubCanvasContext()
    confettiMock.mockImplementationOnce(() => {
      throw new Error('canvas unavailable')
    })
    const { celebrate } = useConfetti()

    await expect(celebrate()).resolves.toBeUndefined()
  })

  it('stop() resets the canvas-confetti animation', async () => {
    const { stop } = useConfetti()

    await stop()

    expect(resetMock).toHaveBeenCalledTimes(1)
  })
})
