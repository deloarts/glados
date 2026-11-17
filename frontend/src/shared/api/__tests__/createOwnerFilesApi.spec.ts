import { describe, it, expect, vi, beforeEach } from 'vitest'

const calls: { method: string; args: unknown[] }[] = []

function record(method: string) {
  return (...args: unknown[]) => {
    calls.push({ method, args })
    return Promise.resolve({ data: [] })
  }
}

vi.mock('@/core/api', () => ({
  default: { get: record('get'), post: record('post'), delete: record('delete') },
}))

import { createFilesApi, createOwnerFilesApi, type FileOwnerKind } from '../createFilesApi'

type Types = { file: unknown; category: string }

const OWNER_PREFIXES: [FileOwnerKind, string][] = [
  ['order', '/orders'],
  ['productionOrder', '/production-orders'],
  ['product', '/products'],
]

describe('createOwnerFilesApi', () => {
  beforeEach(() => {
    calls.length = 0
  })

  it.each(OWNER_PREFIXES)('sends the %s file routes under %s', async (kind, prefix) => {
    const api = createOwnerFilesApi<Types>(kind)
    const file = new File(['x'], 'a.pdf')

    await api.list(3)
    await api.upload(3, file, 'document')
    await api.remove(3, 9)
    await api.getBlob(3, 9)

    expect(calls.map((c) => [c.method, c.args[0]])).toEqual([
      ['get', `${prefix}/3/files`],
      ['post', `${prefix}/3/files`],
      ['delete', `${prefix}/3/files/9`],
      ['get', `${prefix}/3/files/9`],
    ])
    expect(calls[0]!.args).toHaveLength(1)
    const [, formData, config] = calls[1]!.args as [string, FormData, unknown]
    expect(formData.get('file')).toBe(file)
    expect(formData.get('category')).toBe('document')
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
    expect(calls[2]!.args).toHaveLength(1)
    expect(calls[3]!.args[1]).toEqual({ responseType: 'blob' })
  })

  it('sends the product batch request to the slashed products-files route', async () => {
    const api = createFilesApi<Types>('product')

    await expect(api.listForItems([])).resolves.toEqual([])
    await api.listForItems([1, 2])

    expect(calls).toEqual([
      { method: 'get', args: ['/products-files/', { params: { item_ids: [1, 2] } }] },
    ])
  })
})
