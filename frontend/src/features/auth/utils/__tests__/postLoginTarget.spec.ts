import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { UserResponse } from '@/core/types/userResponse'

import { postLoginTarget, resolveStartPageRoute, START_PAGE_ROUTES } from '../postLoginTarget'

describe('postLoginTarget', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sends the system user to settings regardless of a redirect query', () => {
    useCurrentUserStore().user = { is_systemuser: true } as unknown as UserResponse

    expect(postLoginTarget('/production/lots')).toBe('/settings')
  })

  it('sends the system user to settings when there is no redirect query', () => {
    useCurrentUserStore().user = { is_systemuser: true } as unknown as UserResponse

    expect(postLoginTarget(undefined)).toBe('/settings')
  })

  it('sends an ordinary user to an ordinary internal redirect, ahead of their start page', () => {
    useCurrentUserStore().user = {
      is_systemuser: false,
      start_page: 'workspace',
    } as unknown as UserResponse

    expect(postLoginTarget('/production/lots')).toBe('/production/lots')
  })

  it("falls back to the user's start-page route for an ordinary user with no redirect", () => {
    useCurrentUserStore().user = {
      is_systemuser: false,
      start_page: 'todo',
    } as unknown as UserResponse

    expect(postLoginTarget(undefined)).toBe('/todo')
  })

  it("falls back to the user's start-page route for an ordinary user with an unsafe redirect", () => {
    useCurrentUserStore().user = {
      is_systemuser: false,
      start_page: 'todo',
    } as unknown as UserResponse

    expect(postLoginTarget('//evil.example')).toBe('/todo')
  })

  it('falls back to the dashboard when no redirect and no start-page preference is set', () => {
    useCurrentUserStore().user = { is_systemuser: false } as unknown as UserResponse

    expect(postLoginTarget(undefined)).toBe('/dashboard')
  })
})

describe('resolveStartPageRoute', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('maps every closed-vocabulary value to its sidebar route', () => {
    for (const [startPage, route] of Object.entries(START_PAGE_ROUTES)) {
      useCurrentUserStore().user = { start_page: startPage } as unknown as UserResponse
      expect(resolveStartPageRoute()).toBe(route)
    }
  })

  it('falls back to the dashboard for an unrecognised value', () => {
    useCurrentUserStore().user = { start_page: 'something-a-newer-build-added' } as unknown as UserResponse

    expect(resolveStartPageRoute()).toBe('/dashboard')
  })

  it('falls back to the dashboard when no user is signed in', () => {
    expect(resolveStartPageRoute()).toBe('/dashboard')
  })

  it('falls back to the dashboard for "production" when production planning is disabled', () => {
    useCurrentUserStore().user = { start_page: 'production' } as unknown as UserResponse
    useHostStore().productionPlanningEnabled = false

    expect(resolveStartPageRoute()).toBe('/dashboard')
  })

  it('honors "production" when production planning is enabled', () => {
    useCurrentUserStore().user = { start_page: 'production' } as unknown as UserResponse
    useHostStore().productionPlanningEnabled = true

    expect(resolveStartPageRoute()).toBe('/production/lots')
  })
})
