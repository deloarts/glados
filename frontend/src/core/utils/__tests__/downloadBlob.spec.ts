import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { downloadBlob } from '../downloadBlob'

describe('downloadBlob', () => {
  const createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:mock-0')
  const revokeObjectURL = vi.fn<(url: string) => void>()

  beforeEach(() => {
    vi.useFakeTimers()
    createObjectURL.mockClear()
    revokeObjectURL.mockClear()
    Object.assign(URL, { createObjectURL, revokeObjectURL })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('clicks an attached anchor that downloads the blob under the file name', () => {
    const clicked: { href: string; download: string; attached: boolean }[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push({ href: this.href, download: this.download, attached: document.body.contains(this) })
    })
    const blob = new Blob(['x'])

    downloadBlob(blob, 'report.pdf')

    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(clicked).toEqual([{ href: 'blob:mock-0', download: 'report.pdf', attached: true }])
    expect(document.querySelector('a[download]')).toBeNull()
  })

  it('revokes the object URL only after a delay', () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadBlob(new Blob(['x']), 'backup.tar.gz')

    expect(revokeObjectURL).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1000)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-0')
  })
})
