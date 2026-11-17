import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDocketTemplate, makeLabelTemplate } from './fixtures'

import type { PrinterResponse } from '@/features/printers'
import type { PrintTemplateKind } from '../../utils/printTemplateKinds'
import type { PrintTemplateUpdateRequest } from '../../types/printTemplateRequest'
import type {
  FieldSourceResponse,
  PreviewResponse,
  PrintTemplateResponse,
} from '../../types/printTemplateResponse'

const getPrintersMock = vi.fn<(params: { kind?: string }) => Promise<{ items: PrinterResponse[] }>>()
vi.mock('@/features/printers', () => ({
  getPrinters: (params: { kind?: string }) => getPrintersMock(params),
}))

const getFieldSourcesMock = vi.fn<() => Promise<FieldSourceResponse[]>>()
vi.mock('../../api/getFieldSources', () => ({
  getFieldSources: () => getFieldSourcesMock(),
}))

const previewTextMock = vi.fn<() => Promise<PreviewResponse>>()
const previewImageMock = vi.fn<() => Promise<{ url: string; warnings: string[] }>>()
vi.mock('../../api/previewPrintTemplate', () => ({
  previewPrintTemplate: () => previewTextMock(),
  previewPrintTemplateImageUrl: () => previewImageMock(),
}))

const downloadMock = vi.fn<() => Promise<{ warnings: string[] }>>()
vi.mock('../../api/downloadPrintTemplate', () => ({
  downloadPrintTemplate: () => downloadMock(),
}))

const updateMock =
  vi.fn<(classifier: string, payload: PrintTemplateUpdateRequest) => Promise<PrintTemplateResponse>>()
vi.mock('../../api/updatePrintTemplate', () => ({
  updatePrintTemplate: (classifier: string, payload: PrintTemplateUpdateRequest) =>
    updateMock(classifier, payload),
}))

import PrintTemplateEditorDialog from '../PrintTemplateEditorDialog.vue'

const TEMPLATES = { label: makeLabelTemplate(), docket: makeDocketTemplate() }

async function openEditor(kind: PrintTemplateKind, template = TEMPLATES[kind]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(PrintTemplateEditorDialog, {
    pinia,
    attachTo: document.body,
    props: { kind, template, visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byId(id: string): HTMLElement | null {
  return document.getElementById(id)
}

function submitForm(): void {
  document.body.querySelector('form')!.dispatchEvent(new Event('submit'))
}

function hasButton(wrapper: Awaited<ReturnType<typeof openEditor>>, icon: string): boolean {
  return wrapper.findAllComponents({ name: 'Button' }).some((b) => b.props('icon') === icon)
}

describe('PrintTemplateEditorDialog', () => {
  beforeEach(() => {
    getPrintersMock.mockReset().mockResolvedValue({ items: [] })
    getFieldSourcesMock.mockReset().mockResolvedValue([])
    previewTextMock.mockReset()
    previewImageMock.mockReset()
    downloadMock.mockReset()
    updateMock.mockReset().mockImplementation(async () => TEMPLATES.label)
    // jsdom implements no object URLs; the preview mocks hand out fake ones.
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('edits a label with ZPL printers, brace tokens and no paper or download', async () => {
    const wrapper = await openEditor('label')

    expect(getPrintersMock).toHaveBeenCalledWith(expect.objectContaining({ kind: 'zpl_label' }))
    expect(byId('pl-trigger')).not.toBeNull()
    expect(byId('pl-paper')).toBeNull()
    expect(document.body.textContent).toContain('ZPL Source')
    expect(document.body.querySelector('.placeholder-name')?.textContent).toBe('{order_number}')
    expect(document.body.querySelector('input[type="file"]')?.getAttribute('accept')).toBe(
      '.zpl,.txt',
    )
    expect(hasButton(wrapper, 'mdi mdi-download-outline')).toBe(false)

    wrapper.unmount()
  })

  it('edits a docket with document printers, bare field names, paper and download', async () => {
    const wrapper = await openEditor('docket')

    expect(getPrintersMock).toHaveBeenCalledWith(expect.objectContaining({ kind: 'ipp_document' }))
    expect(byId('pd-trigger')).not.toBeNull()
    expect(byId('pd-paper')).not.toBeNull()
    expect(document.body.textContent).toContain('Block Spec (JSON)')
    expect(document.body.querySelector('.placeholder-name')?.textContent).toBe('lot_number')
    expect(document.body.querySelector('input[type="file"]')?.getAttribute('accept')).toBe(
      '.json,.txt',
    )
    expect(hasButton(wrapper, 'mdi mdi-download-outline')).toBe(true)

    wrapper.unmount()
  })

  it.each([
    ['label', undefined],
    ['docket', 'a4'],
  ] as const)('sends the paper size on save only for the %s kind when it has one', async (kind, paper) => {
    const wrapper = await openEditor(kind)

    submitForm()
    await flushPromises()

    expect(updateMock).toHaveBeenCalledTimes(1)
    const [classifier, payload] = updateMock.mock.calls[0]!
    expect(classifier).toBe(TEMPLATES[kind].classifier)
    expect('paper' in payload).toBe(paper !== undefined)
    expect(payload.paper).toBe(paper)
    expect(wrapper.emitted('saved')).toHaveLength(1)

    wrapper.unmount()
  })

  it('blocks saving a docket whose source is not valid JSON', async () => {
    const wrapper = await openEditor('docket', makeDocketTemplate({ source: '{"blocks": [' }))

    submitForm()
    await flushPromises()

    expect(updateMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()

    wrapper.unmount()
  })

  it.each([
    ['label', 1],
    ['docket', 0],
  ] as const)('previews the %s kind, with the rendered ZPL text only for labels', async (kind, textCalls) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    previewTextMock.mockResolvedValue({ rendered_zpl: '^XA^XZ', warnings: [] } as PreviewResponse)
    previewImageMock.mockResolvedValue({ url: 'blob:preview', warnings: [] })
    const wrapper = await openEditor(kind)

    const idElement = byId(`${kind === 'label' ? 'pl' : 'pd'}-preview-id`)!
    const previewInput = wrapper
      .findAllComponents({ name: 'InputNumber' })
      .find((c) => (c.element as HTMLElement).contains(idElement))!
    previewInput.vm.$emit('update:modelValue', 7)
    await flushPromises()
    vi.advanceTimersByTime(500)
    await flushPromises()

    expect(previewImageMock).toHaveBeenCalledTimes(1)
    expect(previewTextMock).toHaveBeenCalledTimes(textCalls)
    expect(Boolean(document.body.querySelector('.preview-zpl'))).toBe(textCalls === 1)

    wrapper.unmount()
  })
})
