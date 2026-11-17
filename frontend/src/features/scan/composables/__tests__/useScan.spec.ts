import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

// The camera watch is a module singleton, so every test loads a fresh copy
// of the composable after installing its own mediaDevices stand-in.
async function loadUseScan() {
  vi.resetModules()
  const { useScan } = await import('../useScan')
  return useScan
}

function stubMediaDevices(kinds: MediaDeviceKind[]) {
  const listeners: Array<() => void> = []
  const mediaDevices = {
    enumerateDevices: vi.fn<() => Promise<MediaDeviceInfo[]>>(() =>
      Promise.resolve(kinds.map((kind) => ({ kind }) as MediaDeviceInfo)),
    ),
    addEventListener: vi.fn<(type: string, listener: () => void) => number>((_type, listener) =>
      listeners.push(listener),
    ),
  }
  vi.stubGlobal('navigator', { ...navigator, mediaDevices })
  return { mediaDevices, kinds, fireDeviceChange: () => listeners.forEach((l) => l()) }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useScan, camera detection', () => {
  it('reports a camera once a video input is enumerated', async () => {
    stubMediaDevices(['audioinput', 'videoinput'])
    const useScan = await loadUseScan()

    const { cameraAvailable } = useScan()
    await flushPromises()

    expect(cameraAvailable.value).toBe(true)
  })

  it('reports no camera when only other devices exist', async () => {
    stubMediaDevices(['audioinput', 'audiooutput'])
    const useScan = await loadUseScan()

    const { cameraAvailable } = useScan()
    await flushPromises()

    expect(cameraAvailable.value).toBe(false)
  })

  it('reports no camera when the browser has no mediaDevices', async () => {
    vi.stubGlobal('navigator', { ...navigator, mediaDevices: undefined })
    const useScan = await loadUseScan()

    const { cameraAvailable } = useScan()
    await flushPromises()

    expect(cameraAvailable.value).toBe(false)
  })

  it('picks up a camera plugged in later', async () => {
    const stub = stubMediaDevices([])
    const useScan = await loadUseScan()
    const { cameraAvailable } = useScan()
    await flushPromises()
    expect(cameraAvailable.value).toBe(false)

    stub.kinds.push('videoinput')
    stub.fireDeviceChange()
    await flushPromises()

    expect(cameraAvailable.value).toBe(true)
  })

  it('enumerates once however many components use it', async () => {
    const { mediaDevices } = stubMediaDevices(['videoinput'])
    const useScan = await loadUseScan()

    useScan()
    useScan()
    await flushPromises()

    expect(mediaDevices.enumerateDevices).toHaveBeenCalledTimes(1)
  })
})
