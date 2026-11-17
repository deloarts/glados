import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDocketTemplate, makeLabelTemplate } from './fixtures'

import type { PrintTemplateKind } from '../../utils/printTemplateKinds'

const previewImageMock =
  vi.fn<(classifier: string, rootType: string, rootId: number) => Promise<{ url: string; warnings: string[] }>>()
vi.mock('../../api/previewPrintTemplate', () => ({
  previewPrintTemplateImageUrl: (classifier: string, rootType: string, rootId: number) =>
    previewImageMock(classifier, rootType, rootId),
}))

const downloadMock =
  vi.fn<(classifier: string, rootType: string, rootId: number) => Promise<{ warnings: string[] }>>()
vi.mock('../../api/downloadPrintTemplate', () => ({
  downloadPrintTemplate: (classifier: string, rootType: string, rootId: number) =>
    downloadMock(classifier, rootType, rootId),
}))

import PrintTemplatePreviewDialog from '../PrintTemplatePreviewDialog.vue'

const TEMPLATES = { label: makeLabelTemplate(), docket: makeDocketTemplate() }

async function openPreview(kind: PrintTemplateKind) {
  const wrapper = mountWithApp(PrintTemplatePreviewDialog, {
    attachTo: document.body,
    props: { kind, template: TEMPLATES[kind], visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  wrapper.findComponent({ name: 'InputNumber' }).vm.$emit('update:modelValue', 7)
  await flushPromises()
  return wrapper
}

function findButton(wrapper: Awaited<ReturnType<typeof openPreview>>, icon: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('icon') === icon)
}

describe('PrintTemplatePreviewDialog', () => {
  beforeEach(() => {
    previewImageMock.mockReset().mockResolvedValue({ url: 'blob:preview', warnings: ['Missing lot'] })
    downloadMock.mockReset().mockResolvedValue({ warnings: [] })
    // jsdom implements no object URLs; the preview mocks hand out fake ones.
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
  })

  it.each([
    ['label', 'pld-id'],
    ['docket', 'pdd-id'],
  ] as const)('renders the %s preview for the entered record', async (kind, inputId) => {
    const wrapper = await openPreview(kind)

    expect(document.getElementById(inputId)).not.toBeNull()
    await findButton(wrapper, 'mdi mdi-eye-outline')!.trigger('click')
    await flushPromises()

    const template = TEMPLATES[kind]
    expect(previewImageMock).toHaveBeenCalledWith(template.classifier, template.root_type, 7)
    expect(document.body.querySelector('img')?.getAttribute('src')).toBe('blob:preview')
    expect(document.body.textContent).toContain('Missing lot')

    wrapper.unmount()
  })

  it('offers no download for labels', async () => {
    const wrapper = await openPreview('label')

    expect(findButton(wrapper, 'mdi mdi-download-outline')).toBeUndefined()

    wrapper.unmount()
  })

  it('downloads the rendered docket for the entered record', async () => {
    const wrapper = await openPreview('docket')

    await findButton(wrapper, 'mdi mdi-download-outline')!.trigger('click')
    await flushPromises()

    expect(downloadMock).toHaveBeenCalledWith('lot_docket', 'production_lot', 7)

    wrapper.unmount()
  })
})
