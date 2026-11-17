import { beforeEach, describe, expect, it } from 'vitest'

import {
  findRememberedUser,
  forgetPasskey,
  forgetRememberedUser,
  initials,
  listRememberedUsers,
  rememberUser,
  updateRememberedUser,
} from '../rememberedUsers'

const STORAGE_KEY = 'glados.rememberedUsers'

describe('rememberedUsers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('remembers a user and lists the most recent sign-in first', async () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    await new Promise((resolve) => setTimeout(resolve, 2))
    rememberUser({ username: 'bob', fullName: 'Bob Jones' })

    expect(listRememberedUsers().map((u) => u.username)).toEqual(['bob', 'alice'])
  })

  it('keeps what the device knew about a user on the next sign-in', () => {
    rememberUser({
      username: 'alice',
      fullName: 'Alice Smith',
      credentialId: 'abc',
      passkeyPublicId: 'p-1',
    })
    rememberUser({ username: 'alice', fullName: 'Alice S.', avatar: 'data:image/jpeg;base64,x' })

    expect(findRememberedUser('alice')).toMatchObject({
      fullName: 'Alice S.',
      credentialId: 'abc',
      passkeyPublicId: 'p-1',
      avatar: 'data:image/jpeg;base64,x',
    })
  })

  it('keeps at most five users', () => {
    for (let i = 0; i < 7; i++) rememberUser({ username: `user${i}`, fullName: `User ${i}` })

    expect(listRememberedUsers()).toHaveLength(5)
    expect(findRememberedUser('user6')).not.toBeNull()
    expect(findRememberedUser('user0')).toBeNull()
  })

  it('forgets a user', () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    forgetRememberedUser('alice')

    expect(listRememberedUsers()).toEqual([])
  })

  it('drops the credential of a removed passkey but keeps the user', () => {
    rememberUser({
      username: 'alice',
      fullName: 'Alice Smith',
      credentialId: 'abc',
      passkeyPublicId: 'p-1',
    })
    forgetPasskey('p-1')

    expect(findRememberedUser('alice')).toMatchObject({ credentialId: null, passkeyPublicId: null })
  })

  it('updates a single field', () => {
    rememberUser({ username: 'alice', fullName: 'Alice Smith' })
    updateRememberedUser('alice', { passkeyDeclined: true })

    expect(findRememberedUser('alice')?.passkeyDeclined).toBe(true)
  })

  it('ignores malformed and unreadable storage', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ username: 42 }, null, 'x']))
    expect(listRememberedUsers()).toEqual([])

    localStorage.setItem(STORAGE_KEY, '{not json')
    expect(listRememberedUsers()).toEqual([])
  })

  it('builds up to two initials', () => {
    expect(initials('Alice Mary Smith')).toBe('AM')
    expect(initials('bob')).toBe('B')
  })
})
