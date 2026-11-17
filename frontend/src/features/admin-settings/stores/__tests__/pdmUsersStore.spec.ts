import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { LinkPdmUsersCommand, PdmUser } from '../../types/adminSettingsTypes'

const getPdmUsersMock = vi.fn<() => Promise<PdmUser[]>>()
const linkPdmUsersMock = vi.fn<(cmd: LinkPdmUsersCommand) => Promise<void>>()

vi.mock('../../api/getPdmUsers', () => ({
  getPdmUsers: () => getPdmUsersMock(),
}))
vi.mock('../../api/linkPdmUsers', () => ({
  linkPdmUsers: (cmd: LinkPdmUsersCommand) => linkPdmUsersMock(cmd),
}))

import { usePdmUsersStore } from '../pdmUsersStore'

function makeUser(overrides: Partial<PdmUser> = {}): PdmUser {
  return {
    pdm_user_id: 2,
    username: 'jdoe',
    full_name: 'Jane Doe',
    is_service_account: false,
    linked_user_id: null,
    proposed_user_id: null,
    ...overrides,
  }
}

describe('pdmUsersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPdmUsersMock.mockReset()
    linkPdmUsersMock.mockReset().mockResolvedValue(undefined)
  })

  it('refresh() populates items from getPdmUsers', async () => {
    getPdmUsersMock.mockResolvedValue([makeUser()])
    const store = usePdmUsersStore()

    await store.refresh()

    expect(store.items).toEqual([makeUser()])
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('refresh() sets error and leaves items alone on failure, never throwing', async () => {
    getPdmUsersMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 500, data: { detail: 'boom' } },
    })
    const store = usePdmUsersStore()

    await expect(store.refresh()).resolves.toBeUndefined()

    expect(store.items).toEqual([])
    expect(store.error).toBe('boom')
  })

  it('save() posts the batch then reloads the list', async () => {
    getPdmUsersMock.mockResolvedValue([makeUser({ linked_user_id: 5 })])
    const store = usePdmUsersStore()

    await store.save([{ pdm_user_id: 2, user_id: 5 }])

    expect(linkPdmUsersMock).toHaveBeenCalledWith({ links: [{ pdm_user_id: 2, user_id: 5 }] })
    expect(getPdmUsersMock).toHaveBeenCalledTimes(1)
    expect(store.items).toEqual([makeUser({ linked_user_id: 5 })])
  })

  it('save() propagates a link failure without reloading', async () => {
    linkPdmUsersMock.mockRejectedValue(new Error('link failed'))
    const store = usePdmUsersStore()

    await expect(store.save([{ pdm_user_id: 2, user_id: null }])).rejects.toThrow('link failed')
    expect(getPdmUsersMock).not.toHaveBeenCalled()
  })
})
