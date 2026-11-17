import { describe, it, expect, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { createTokenStore } from '../../../stores/createTokenStore'
import { i18n } from '@/core/i18n'

import TokenManagementControls from '../TokenManagementControls.vue'
import TokenFormDialog from '../TokenFormDialog.vue'
import type { TokenApi, UsageLogParams } from '../../../api/createTokenApi'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
  TokenUsageLogEntry,
} from '../../../types/tokenTypes'
import type { PageResponse } from '@/core/api/types'

function makeApi(): TokenApi {
  return {
    list: vi.fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>(),
    create: vi.fn<(cmd: CreateTokenCommand) => Promise<CreatedToken>>(),
    revoke: vi.fn<(id: number) => Promise<TokenSummary>>(),
    revokeAll: vi.fn<() => Promise<RevokeAllTokensResult>>(),
    getUsageLog:
      vi.fn<
        (id: number, params?: UsageLogParams) => Promise<PageResponse<TokenUsageLogEntry>>
      >(),
  }
}

function mountControls(
  props: {
    canManage?: boolean
    canCreate?: boolean
    showCreateAddin?: boolean
    showCreatePdmAddin?: boolean
    createBlocked?: string
    manageBlocked?: string
    // The PDM shortcut only exists on the API-key tab, whose labels live
    // under a different prefix; everything else defaults to the PAT page.
    i18nPrefix?: string
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = createTokenStore(`testTokenControls-${Math.random()}`, makeApi())()

  return mountWithApp(TokenManagementControls, {
    pinia,
    props: {
      store,
      canManage: props.canManage ?? true,
      canCreate: props.canCreate,
      showCreateAddin: props.showCreateAddin,
      showCreatePdmAddin: props.showCreatePdmAddin,
      createBlocked: props.createBlocked,
      manageBlocked: props.manageBlocked,
      i18nPrefix: props.i18nPrefix ?? 'account.pat',
    },
    global: { plugins: [ConfirmationService] },
  })
}

function createButton(wrapper: ReturnType<typeof mountControls>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('account.pat.createButton'))!
}

function createPdmAddinButton(wrapper: ReturnType<typeof mountControls>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('account.pat.createPdmAddinButton'))
}

function createAddinButton(wrapper: ReturnType<typeof mountControls>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('account.pat.createAddinButton'))
}

describe('TokenManagementControls, add-in token button', () => {
  it('does not render the add-in button when showCreateAddin is unset (e.g. the API-key tab)', () => {
    const wrapper = mountControls()

    expect(createAddinButton(wrapper)).toBeUndefined()

    wrapper.unmount()
  })

  it('renders the add-in button on the personal access token page', () => {
    const wrapper = mountControls({ showCreateAddin: true })

    expect(createAddinButton(wrapper)).toBeDefined()

    wrapper.unmount()
  })

  // An absent optional boolean prop is cast to `false` by Vue, so
  // `canCreate ?? canManage` would resolve to `false` instead of falling
  // through and disable the API-key tab's create button for everyone, system
  // users included. TokenManagementControls therefore defaults canCreate to
  // undefined.
  it('falls back to canManage when canCreate is omitted, as the API-key tab does', () => {
    const wrapper = mountControls({ canManage: true })

    expect(createButton(wrapper).attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('still disables the create button when canCreate is omitted and canManage is false', () => {
    const wrapper = mountControls({ canManage: false })

    expect(createButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('disables the add-in button the same way as the plain create button', () => {
    const wrapper = mountControls({ showCreateAddin: true, canCreate: false })

    // OpenVue's Button forwards `disabled` through $attrs onto the native
    // <button> rather than declaring it as its own prop.
    expect(createAddinButton(wrapper)!.attributes('disabled')).toBeDefined()
    expect(createButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  // The PDM shortcut sits next to the SolidWorks one on the personal access
  // token page; callers hide both add-in buttons when PDM is switched off,
  // so the default must render neither.
  it('does not render the PDM add-in button unless showCreatePdmAddin is set', () => {
    const wrapper = mountControls({ showCreateAddin: true })

    expect(createPdmAddinButton(wrapper)).toBeUndefined()

    wrapper.unmount()
  })

  it('renders the PDM add-in button and opens the dialog in PDM mode', async () => {
    const wrapper = mountControls({ showCreatePdmAddin: true })
    const dialog = () => wrapper.findComponent(TokenFormDialog)

    expect(createPdmAddinButton(wrapper)).toBeDefined()

    await createPdmAddinButton(wrapper)!.trigger('click')

    expect(dialog().props('pdmAddin')).toBe(true)
    expect(dialog().props('addin')).toBe(false)

    wrapper.unmount()
  })

  it('opens in plain mode from the Create button even when the PDM shortcut is shown', async () => {
    const wrapper = mountControls({ showCreatePdmAddin: true })
    const dialog = () => wrapper.findComponent(TokenFormDialog)

    await createButton(wrapper).trigger('click')

    expect(dialog().props('pdmAddin')).toBe(false)
    expect(dialog().props('addin')).toBe(false)

    wrapper.unmount()
  })

  it('opens the shared TokenFormDialog in add-in mode when clicked, and in plain mode from the Create Token button', async () => {
    const wrapper = mountControls({ showCreateAddin: true })
    const dialog = () => wrapper.findComponent(TokenFormDialog)

    expect(dialog().props('visible')).toBe(false)

    await createAddinButton(wrapper)!.trigger('click')

    expect(dialog().props('visible')).toBe(true)
    expect(dialog().props('addin')).toBe(true)

    await dialog().vm.$emit('update:visible', false)
    await createButton(wrapper).trigger('click')

    expect(dialog().props('visible')).toBe(true)
    expect(dialog().props('addin')).toBe(false)

    wrapper.unmount()
  })
})

describe('TokenManagementControls, permission tooltips', () => {
  it('names the missing permission on the disabled create and Revoke All buttons', () => {
    const wrapper = mountControls({
      canManage: false,
      canCreate: false,
      showCreateAddin: true,
      createBlocked: 'This needs the permission Write Access Token.',
      manageBlocked: 'This needs the permission Manage API Keys.',
    })

    expect(tooltipOf(createButton(wrapper))).toBe('This needs the permission Write Access Token.')
    expect(tooltipOf(createAddinButton(wrapper)!)).toBe(
      'This needs the permission Write Access Token.',
    )
    expect(tooltipOf(wrapper.get('[data-testid="token-revoke-all"]'))).toBe(
      'This needs the permission Manage API Keys.',
    )

    wrapper.unmount()
  })

  it('shows no tooltip while the user may create', () => {
    const wrapper = mountControls({ canCreate: true })

    expect(tooltipOf(createButton(wrapper))).toBeUndefined()

    wrapper.unmount()
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
