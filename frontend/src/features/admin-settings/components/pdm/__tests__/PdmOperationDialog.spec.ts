import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import PdmOperationDialog from '../PdmOperationDialog.vue'
import type { PdmInvokeResult, PdmOperation } from '../../../types/adminSettingsTypes'

const postMock = vi.fn<(url: string, body: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    post: (url: string, body: unknown) => postMock(url, body),
  },
}))

const SEARCH_OPERATION: PdmOperation = {
  id: 'post_api_vaultname_searchvariables',
  method: 'POST',
  path: 'api/{vaultName}/searchvariables',
  group: 'Search',
  description: 'Searches for files/folders matching the given criteria.',
  params: [
    { name: 'vaultName', location: 'path', type: 'string', required: true, description: 'Vault name' },
    {
      name: 'folderId',
      location: 'query',
      type: 'integer',
      required: true,
      description: 'Folder id to search under',
    },
    {
      name: 'recursive',
      location: 'query',
      type: 'boolean',
      required: false,
      description: 'Include subfolders',
    },
    { name: 'Name', location: 'body', type: 'string', required: false, description: '(Body) name filter' },
  ],
  has_body: true,
  body_example: '{\n  "Name": "sample string 1"\n}',
  mutating: false,
}

const VERSION_OPERATION: PdmOperation = {
  id: 'get_api_version_webapi',
  method: 'GET',
  path: 'api/version/webapi',
  group: 'Version',
  description: 'Returns the Web API product/version info.',
  params: [],
  has_body: false,
  body_example: null,
  mutating: false,
}

function invokeResult(overrides: Partial<PdmInvokeResult> = {}): PdmInvokeResult {
  return {
    method: 'GET',
    url: 'http://pdm.example.com:65453/api/version/webapi',
    status_code: 200,
    elapsed_ms: 42,
    content_type: 'application/json',
    response_json: { ProdName: 'PDM Professional' },
    response_text: null,
    ...overrides,
  }
}

async function mountDialog(operation: PdmOperation | null, criticalMode = false) {
  const wrapper = mountWithApp(PdmOperationDialog, {
    props: { operation, criticalMode, visible: false },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

async function openDialog(wrapper: ReturnType<typeof mountWithApp>) {
  await wrapper.setProps({ visible: true })
  await flushPromises()
}

// OpenVue's Dialog teleports its content to document.body, outside the
// mounted wrapper's own DOM subtree, so wrapper.text()/wrapper.find()
// can't see it (component-tree lookups like findComponent() still can,
// Teleport only moves DOM placement). Read straight from the document for
// anything that needs the rendered text/markup.
function bodyText(): string {
  return document.body.textContent ?? ''
}

describe('PdmOperationDialog', () => {
  beforeEach(() => {
    postMock.mockReset()
  })

  it('generates one field per path/query param, skipping vaultName and body-location params', async () => {
    const wrapper = await mountDialog(SEARCH_OPERATION)
    await openDialog(wrapper)

    // The header legitimately shows the raw path with its "{vaultName}"
    // placeholder: what must NOT exist is a rendered form field for it.
    expect(document.body.querySelector('#pdm-op-param-vaultName')).toBeNull()
    expect(bodyText()).toContain('folderId')
    expect(bodyText()).toContain('recursive')
    // "Name" is a body-location param (documents one field of the JSON
    // body); it gets no field of its own either, only the body Textarea.
    expect(document.body.querySelector('#pdm-op-param-Name')).toBeNull()

    expect(wrapper.findComponent({ name: 'InputNumber' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ToggleSwitch' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('marks required params and prefills the body Textarea with body_example', async () => {
    const wrapper = await mountDialog(SEARCH_OPERATION)
    await openDialog(wrapper)

    expect(bodyText()).toContain('folderId *')
    expect(bodyText()).not.toContain('recursive *')

    const textarea = wrapper.findComponent({ name: 'Textarea' })
    expect(textarea.props('modelValue')).toBe(SEARCH_OPERATION.body_example)

    wrapper.unmount()
  })

  it('does not invoke and shows a required-field error when a required param is left empty', async () => {
    const wrapper = await mountDialog(SEARCH_OPERATION)
    await openDialog(wrapper)

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(postMock).not.toHaveBeenCalled()
    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.operation.fieldRequiredError'),
    )

    wrapper.unmount()
  })

  it('rejects invalid JSON in the body Textarea and does not invoke', async () => {
    const wrapper = await mountDialog(SEARCH_OPERATION)
    await openDialog(wrapper)

    await wrapper.findComponent({ name: 'InputNumber' }).vm.$emit('update:modelValue', 3)
    const textarea = wrapper.findComponent({ name: 'Textarea' })
    await textarea.vm.$emit('update:modelValue', '{not valid json')
    await flushPromises()

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(postMock).not.toHaveBeenCalled()
    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.operation.jsonInvalid'),
    )

    wrapper.unmount()
  })

  it('accepts a bare JSON string as a valid body', async () => {
    postMock.mockResolvedValue({ data: invokeResult() })
    const wrapper = await mountDialog(SEARCH_OPERATION)
    await openDialog(wrapper)

    await wrapper.findComponent({ name: 'InputNumber' }).vm.$emit('update:modelValue', 3)
    const textarea = wrapper.findComponent({ name: 'Textarea' })
    await textarea.vm.$emit('update:modelValue', '"sample string 1"')
    await flushPromises()

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [, payload] = postMock.mock.calls[0]!
    expect((payload as { body: unknown }).body).toBe('sample string 1')

    wrapper.unmount()
  })

  it('sends path_params/query built from the filled fields plus allow_mutating from criticalMode', async () => {
    postMock.mockResolvedValue({ data: invokeResult() })
    const wrapper = await mountDialog(SEARCH_OPERATION, true)
    await openDialog(wrapper)

    await wrapper.findComponent({ name: 'InputNumber' }).vm.$emit('update:modelValue', 12)
    await wrapper.findComponent({ name: 'ToggleSwitch' }).vm.$emit('update:modelValue', true)
    await flushPromises()

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith(
      '/admin/settings/pdm/operations/post_api_vaultname_searchvariables/invoke',
      {
        path_params: {},
        query: { folderId: 12, recursive: true },
        body: { Name: 'sample string 1' },
        allow_mutating: true,
      },
    )

    wrapper.unmount()
  })

  it('renders the result section with a success status tag and pretty-printed JSON', async () => {
    postMock.mockResolvedValue({ data: invokeResult({ status_code: 200 }) })
    const wrapper = await mountDialog(VERSION_OPERATION)
    await openDialog(wrapper)

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'Tag' }).props('value')).toBe('200')
    expect(bodyText()).toContain('http://pdm.example.com:65453/api/version/webapi')
    expect(bodyText()).toContain('42 ms')
    expect(document.body.querySelector('pre')?.textContent).toContain('ProdName')

    wrapper.unmount()
  })

  it('shows the backend {detail, code} error inline when the call fails', async () => {
    postMock.mockRejectedValue({
      isAxiosError: true,
      response: { status: 503, data: { detail: 'Vault unreachable', code: 'PdmUnavailableError' } },
    })
    const wrapper = await mountDialog(VERSION_OPERATION)
    await openDialog(wrapper)

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    const message = wrapper.findComponent({ name: 'Message' })
    expect(message.text()).toContain('Vault unreachable')
    expect(message.text()).toContain('PdmUnavailableError')

    wrapper.unmount()
  })

  it('keeps the last result visible until the dialog is closed and reopened for a new operation', async () => {
    postMock.mockResolvedValue({ data: invokeResult() })
    const wrapper = await mountDialog(VERSION_OPERATION)
    await openDialog(wrapper)

    const executeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.operation.execute') as string))!
    await executeButton.trigger('click')
    await flushPromises()

    expect(document.body.querySelector('pre')).not.toBeNull()

    // Close, then reopen for a different operation: the stale result must
    // not still be showing.
    await wrapper.setProps({ visible: false })
    await flushPromises()
    await wrapper.setProps({ operation: SEARCH_OPERATION, visible: true })
    await flushPromises()

    expect(document.body.querySelector('pre')).toBeNull()

    wrapper.unmount()
  })
})
