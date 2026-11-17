import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { Permission } from '@/core/auth/permissions'
import { mountWithApp } from '@/test-utils/mountWithApp'

const granted = new Set<string>()
const pictureMock = vi.fn<(partId: number) => Promise<Blob | null>>()

vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

vi.mock('../../api/boughtItemsEdpApi', () => ({
  getEdpPartPicture: (partId: number) => pictureMock(partId),
}))

import EdpPartPicture from '../EdpPartPicture.vue'

describe('EdpPartPicture', () => {
  beforeEach(() => {
    granted.clear()
    pictureMock.mockReset()
    pictureMock.mockResolvedValue(null)
  })

  it('fetches the picture with the Data Portal permission', async () => {
    granted.add(Permission.USE_DATA_PORTAL)

    mountWithApp(EdpPartPicture, { props: { partId: 7 } })
    await flushPromises()

    expect(pictureMock).toHaveBeenCalledWith(7)
  })

  it('requests nothing without the Data Portal permission', async () => {
    granted.add(Permission.WRITE_BOUGHT_ITEMS)

    mountWithApp(EdpPartPicture, { props: { partId: 7 } })
    await flushPromises()

    expect(pictureMock).not.toHaveBeenCalled()
  })
})
