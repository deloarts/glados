import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { TreeNode } from 'openvue/treenode'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import PdmFolderPickerDialog from '../PdmFolderPickerDialog.vue'
import type { PdmFolder } from '../../../types/adminSettingsTypes'

const getMock = vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
  },
}))

const ROOT_FOLDERS: PdmFolder[] = [
  { id: 2, name: 'Made-Parts', path: '\\Made-Parts' },
  { id: 3, name: 'Bought-Parts', path: '\\Bought-Parts' },
]

const MADE_PARTS_SUBFOLDERS: PdmFolder[] = [
  { id: 4, name: 'Sheet-Metal', path: '\\Made-Parts\\Sheet-Metal' },
]

// OpenVue's Dialog teleports its content to document.body, outside the
// mounted wrapper's own DOM subtree, so wrapper.text()/wrapper.find()
// can't see it (component-tree lookups like findComponent() still can,
// Teleport only moves DOM placement). Read/query straight off `document`
// for anything native.
function bodyText(): string {
  return document.body.textContent ?? ''
}

async function mountDialog(props: Partial<{ watchedPaths: string[]; allowWatched: boolean }> = {}) {
  const wrapper = mountWithApp(PdmFolderPickerDialog, {
    props: { visible: false, ...props },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

async function openDialog(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  await wrapper.setProps({ visible: true })
  await flushPromises()
}

function tree(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper.findComponent({ name: 'Tree' })
}

function nodes(wrapper: Awaited<ReturnType<typeof mountDialog>>): TreeNode[] {
  return tree(wrapper).props('value') as TreeNode[]
}

function applyButton(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  const applyLabel = i18n.global.t('adminSettings.solidworksPdm.pdm.sync.folderPicker.apply') as string
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === applyLabel)!
}

describe('PdmFolderPickerDialog', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation((url, config) => {
      const parentId = config?.params?.parent_id
      if (parentId === 4) return Promise.resolve({ data: [] })
      if (parentId === 2) return Promise.resolve({ data: MADE_PARTS_SUBFOLDERS })
      return Promise.resolve({ data: ROOT_FOLDERS })
    })
  })

  it('loads the vault root every time it is opened', async () => {
    const wrapper = await mountDialog()
    expect(getMock).not.toHaveBeenCalled()

    await openDialog(wrapper)

    expect(getMock).toHaveBeenCalledWith('/admin/settings/pdm/folders', { params: { parent_id: 1 } })
    expect(bodyText()).toContain('Made-Parts')
    expect(bodyText()).toContain('Bought-Parts')
    expect(nodes(wrapper)).toHaveLength(2)

    wrapper.unmount()
  })

  it("lazily loads a node's children on expand, and caches them on a second expand", async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)
    const madeParts = nodes(wrapper)[0]!

    await tree(wrapper).vm.$emit('node-expand', madeParts)
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/admin/settings/pdm/folders', { params: { parent_id: 2 } })
    expect(madeParts.children).toHaveLength(1)
    expect(madeParts.children![0]!.label).toBe('Sheet-Metal')
    expect(madeParts.loading).toBe(false)

    getMock.mockClear()
    await tree(wrapper).vm.$emit('node-expand', madeParts)
    await flushPromises()

    expect(getMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('marks a node with no children as a leaf after loading an empty folder', async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)
    const madeParts = nodes(wrapper)[0]!
    await tree(wrapper).vm.$emit('node-expand', madeParts)
    await flushPromises()
    const sheetMetal = madeParts.children![0]!
    expect(sheetMetal.leaf).toBe(false)

    await tree(wrapper).vm.$emit('node-expand', sheetMetal)
    await flushPromises()

    expect(sheetMetal.leaf).toBe(true)
    expect(sheetMetal.children).toEqual([])

    wrapper.unmount()
  })

  it('shows an error and lets the user retry when a node fails to load', async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)
    const madeParts = nodes(wrapper)[0]!
    getMock.mockImplementationOnce(() => Promise.reject(new Error('network error')))

    await tree(wrapper).vm.$emit('node-expand', madeParts)
    await flushPromises()

    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.folderPicker.loadFailed'),
    )
    expect(madeParts.children).toBeUndefined()

    const reloadLabel = i18n.global.t('common.reload') as string
    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === reloadLabel)!
      .trigger('click')
    await flushPromises()

    expect(madeParts.children).toHaveLength(1)

    wrapper.unmount()
  })

  it('marks an already-watched folder muted and unselectable when allowWatched is false (the default)', async () => {
    const wrapper = await mountDialog({ watchedPaths: ['\\Made-Parts'] })
    await openDialog(wrapper)

    const [madeParts, boughtParts] = nodes(wrapper)
    expect(madeParts!.selectable).toBe(false)
    expect(boughtParts!.selectable).toBe(true)
    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.folderPicker.alreadyWatched'),
    )

    wrapper.unmount()
  })

  it('still allows selecting an already-watched folder when allowWatched is true', async () => {
    const wrapper = await mountDialog({ watchedPaths: ['\\Made-Parts'], allowWatched: true })
    await openDialog(wrapper)

    expect(nodes(wrapper)[0]!.selectable).toBe(true)

    wrapper.unmount()
  })

  it('disables Apply until a node is selected, and applying emits its path and id and closes', async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)

    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(true)

    const madeParts = nodes(wrapper)[0]!
    await tree(wrapper).vm.$emit('node-select', madeParts)

    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(false)
    await applyButton(wrapper).trigger('click')

    expect(wrapper.emitted('apply')).toEqual([['\\Made-Parts', 2]])
    expect(wrapper.emitted('update:visible')).toEqual([[false]])

    wrapper.unmount()
  })

  it('unselecting a node disables Apply again', async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)
    const madeParts = nodes(wrapper)[0]!
    await tree(wrapper).vm.$emit('node-select', madeParts)
    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(false)

    await tree(wrapper).vm.$emit('node-unselect', madeParts)

    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })

  it('resets the selection and reloads from the vault root every time it is reopened', async () => {
    const wrapper = await mountDialog()
    await openDialog(wrapper)
    await tree(wrapper).vm.$emit('node-select', nodes(wrapper)[0]!)
    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(false)

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(applyButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(getMock).toHaveBeenLastCalledWith('/admin/settings/pdm/folders', { params: { parent_id: 1 } })

    wrapper.unmount()
  })

  it('shows the load-failed Message and lets the user reload', async () => {
    getMock.mockReset()
    getMock.mockRejectedValue(new Error('network error'))

    const wrapper = await mountDialog()
    await openDialog(wrapper)

    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.folderPicker.loadFailed'),
    )

    getMock.mockResolvedValue({ data: ROOT_FOLDERS })
    const reloadLabel = i18n.global.t('common.reload') as string
    await wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === reloadLabel)!
      .trigger('click')
    await flushPromises()

    expect(bodyText()).toContain('Made-Parts')

    wrapper.unmount()
  })

  it('shows an empty-vault Message when the root has no subfolders', async () => {
    getMock.mockReset()
    getMock.mockResolvedValue({ data: [] })

    const wrapper = await mountDialog()
    await openDialog(wrapper)

    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.folderPicker.empty'),
    )

    wrapper.unmount()
  })
})
