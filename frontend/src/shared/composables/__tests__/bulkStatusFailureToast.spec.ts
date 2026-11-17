import { describe, it, expect, vi } from 'vitest'

import { bulkStatusFailureToast } from '../useDemandRowActions'

describe('bulkStatusFailureToast', () => {
  it('shows one error toast with the feature wording and the counts', () => {
    const error = vi.fn<(summary: string, detail?: string) => void>()
    const t = vi.fn<(key: string, params?: Record<string, unknown>) => string>(
      (key, params) => (params ? `${key} ${JSON.stringify(params)}` : key),
    )

    bulkStatusFailureToast({ error }, t, 'boughtItems.demands')(2, 5)

    expect(error).toHaveBeenCalledTimes(1)
    expect(error).toHaveBeenCalledWith(
      'boughtItems.demands.contextMenu.setStatus',
      'boughtItems.demands.contextMenu.bulkActionPartialError {"count":2,"total":5}',
    )
  })
})
