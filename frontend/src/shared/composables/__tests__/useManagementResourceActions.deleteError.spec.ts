import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

// A refused delete shows the reason the server gives, as a restore does,
// for example the live work that keeps a project from being deleted.

interface Entity {
  id: number
  public_id: string
  name: string
}

interface CapturedConfirmOptions {
  accept: () => Promise<void>
}

const confirmRequireMock = vi.fn<(options: CapturedConfirmOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

const toastAddMock = vi.fn<(message: unknown) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import {
  useManagementResourceActions,
  type UseManagementResourceActionsResult,
} from '../useManagementResourceActions'

const I18N_PREFIX = 'settings.articleGroups'

function mountComposable(remove: (id: number) => Promise<void>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  let result!: UseManagementResourceActionsResult<Entity>
  mountWithApp(
    defineComponent({
      setup() {
        result = useManagementResourceActions<Entity>(
          { remove },
          {
            i18nPrefix: I18N_PREFIX,
            entityLabel: (entity) => entity.name,
            deletePermission: 'delete:widgets',
          },
        )
        return () => h('div')
      },
    }),
    { pinia },
  )
  return result
}

const entity: Entity = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  name: 'P-0815',
}

describe('useManagementResourceActions delete errors', () => {
  beforeEach(() => {
    confirmRequireMock.mockReset()
    toastAddMock.mockReset()
  })

  it('shows the reason the server gives for a refused delete', async () => {
    const detail =
      "Project 'P-0815' still has live work: 2 lots. Finish or cancel it before deleting the project."
    const remove = vi.fn<(id: number) => Promise<void>>().mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { detail, code: 'ProjectDeleteBlockedError' } },
    })
    const result = mountComposable(remove)

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: 'P-0815',
      detail,
      life: 5000,
    })
  })

  it('falls back to the unknown-error toast when the server gives no reason', async () => {
    const remove = vi.fn<(id: number) => Promise<void>>().mockRejectedValue(new Error('offline'))
    const result = mountComposable(remove)

    result.onDelete(entity)
    await confirmRequireMock.mock.calls[0]![0].accept()

    expect(toastAddMock).toHaveBeenCalledWith({
      severity: 'error',
      summary: i18n.global.t(`${I18N_PREFIX}.errors.unknown`),
      life: 5000,
    })
  })
})
