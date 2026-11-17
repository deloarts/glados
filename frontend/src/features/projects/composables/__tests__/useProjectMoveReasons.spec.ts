import { describe, it, expect } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { useProjectMoveReasons } from '../useProjectMoveReasons'
import { projectStatusMove } from '../../utils/projectStatusMoves'
import type { ProjectResponse } from '../../types/projectResponse'

const NO_WORK = {
  lots: 0,
  production_orders: 0,
  order_lines: 0,
  bought_demands: 0,
  made_demands: 0,
  source_demands: 0,
  quote_requests: 0,
}

function project(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 1,
    public_id: 'p-1',
    project_number: 'P-001',
    customer_id: null,
    customer: null,
    product_id: null,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01T00:00:00+00:00',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 3,
    actions: ['hold', 'complete', 'archive', 'remove'],
    live_work: NO_WORK,
    ...overrides,
  }
}

function reasons(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  let result!: ReturnType<typeof useProjectMoveReasons>
  mountWithApp(
    defineComponent({
      setup() {
        result = useProjectMoveReasons()
        return () => h('div')
      },
    }),
    { pinia },
  )
  return result
}

describe('projectStatusMove', () => {
  it('names the intent of each move, and none when the status stays', () => {
    expect(projectStatusMove('active', 'on_hold')).toBe('hold')
    expect(projectStatusMove('on_hold', 'active')).toBe('resume')
    expect(projectStatusMove('completed', 'active')).toBe('reopen')
    expect(projectStatusMove('active', 'completed')).toBe('complete')
    expect(projectStatusMove('completed', 'archived')).toBe('archive')
    expect(projectStatusMove('active', 'active')).toBeNull()
  })
})

describe('useProjectMoveReasons', () => {
  it('offers every move the server offers, and the current status always', () => {
    const { statusMoveReason } = reasons([Permission.MANAGE_PROJECTS])
    expect(statusMoveReason(project(), 'active')).toBeNull()
    expect(statusMoveReason(project(), 'on_hold')).toBeNull()
    expect(statusMoveReason(project(), 'archived')).toBeNull()
  })

  it('names the live work that blocks completing, with its counts', () => {
    const { statusMoveReason, deleteBlockedReason } = reasons([Permission.MANAGE_PROJECTS])
    const busy = project({
      actions: ['hold'],
      live_work: { ...NO_WORK, lots: 2, order_lines: 1 },
    })
    expect(statusMoveReason(busy, 'completed')).toBe('Still open: 2 lots, 1 order line.')
    expect(deleteBlockedReason(busy)).toBe('The project still has open work: 2 lots, 1 order line.')
    expect(statusMoveReason(busy, 'on_hold')).toBeNull()
  })

  it('names the current status for a move it does not start', () => {
    const { statusMoveReason } = reasons([Permission.MANAGE_PROJECTS])
    const done = project({ status: 'completed', actions: ['archive', 'reopen', 'remove'] })
    expect(statusMoveReason(done, 'on_hold')).toBe('Not possible from the status Completed.')
  })

  it('names the missing permission before anything else', () => {
    const { statusMoveReason, deleteTooltip } = reasons([Permission.WRITE_PROJECTS])
    expect(statusMoveReason(project(), 'on_hold')).toContain('This needs the permission')
    expect(statusMoveReason(project(), 'active')).toBeNull()
    expect(deleteTooltip(project())).toContain('This needs the permission')
  })
})
