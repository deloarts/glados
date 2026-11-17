import { describe, it, expect, vi, beforeEach } from 'vitest'

const postMock =
  vi.fn<(url: string, payload?: unknown, config?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    post: (url: string, payload?: unknown, config?: unknown) => postMock(url, payload, config),
  },
}))

import { postFile } from '../postFile'

describe('postFile', () => {
  beforeEach(() => {
    postMock.mockReset()
    postMock.mockResolvedValue({ data: { id: 1 } })
  })

  it('posts the file as multipart form data and returns the response body', async () => {
    const file = new File(['png'], 'logo.png')

    const result = await postFile('/admin/settings/branding/logo', file)

    const [url, formData, config] = postMock.mock.calls[0]!
    expect(url).toBe('/admin/settings/branding/logo')
    expect([...(formData as FormData).keys()]).toEqual(['file'])
    expect((formData as FormData).get('file')).toBe(file)
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
    expect(result).toEqual({ id: 1 })
  })

  it('fills the path parameters and appends the extra fields after the file', async () => {
    const file = new File(['x'], 'a.pdf')

    await postFile('/orders/{order_id}/files', file, {
      path: { order_id: 5 },
      fields: { category: 'invoice' },
    })

    const [url, formData] = postMock.mock.calls[0]!
    expect(url).toBe('/orders/5/files')
    expect([...(formData as FormData).entries()]).toEqual([
      ['file', file],
      ['category', 'invoice'],
    ])
  })
})
