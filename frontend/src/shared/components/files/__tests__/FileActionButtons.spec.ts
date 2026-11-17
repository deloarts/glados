import { describe, it, expect } from 'vitest'
import Tooltip from 'openvue/tooltip'


import FileActionButtons from '../FileActionButtons.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

// FilesSection.vue renders the same Preview/Download/[Replace]/Delete
// buttons through this component in both the singleton grid and the
// multi-row list.

function mountButtons(props: {
  previewable?: boolean
  canEdit?: boolean
  deleting?: boolean
  showReplace?: boolean
  locked?: boolean
  lockedTooltip?: string
  missingHint?: string
}) {
  return mountWithApp(FileActionButtons, {
    props: { previewable: false, canEdit: true, deleting: false, ...props },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
}

function buttonIcons(wrapper: ReturnType<typeof mountButtons>): string[] {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .map((b) => b.props('icon'))
    .filter((icon): icon is string => typeof icon === 'string')
}

describe('FileActionButtons', () => {
  it('always renders Download, hides Preview when not previewable', () => {
    const wrapper = mountButtons({ previewable: false, canEdit: false })
    const icons = buttonIcons(wrapper)

    expect(icons).toContain('mdi mdi-download-outline')
    expect(icons).not.toContain('mdi mdi-eye-outline')
  })

  it('renders Preview when previewable', () => {
    const wrapper = mountButtons({ previewable: true, canEdit: false })

    expect(buttonIcons(wrapper)).toContain('mdi mdi-eye-outline')
  })

  it('hides Replace and Delete when canEdit is false, even with showReplace', () => {
    const wrapper = mountButtons({ canEdit: false, showReplace: true })
    const icons = buttonIcons(wrapper)

    expect(icons).not.toContain('mdi mdi-upload-outline')
    expect(icons).not.toContain('mdi mdi-delete-outline')
  })

  it('shows Replace and Delete disabled with the missing permission when only the permission is lacking', () => {
    const hint = 'This needs the permission Write Orders.'
    const wrapper = mountButtons({ canEdit: false, showReplace: true, missingHint: hint })

    for (const testId of ['file-replace', 'file-delete']) {
      const button = wrapper.get(`[data-testid="${testId}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      const span = button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
      expect(span?.$_ptooltipValue).toBe(hint)
    }
  })

  it('shows Replace only when both canEdit and showReplace are set', () => {
    const wrapper = mountButtons({ canEdit: true, showReplace: true })

    expect(buttonIcons(wrapper)).toContain('mdi mdi-upload-outline')
  })

  it('defaults showReplace to false, so canEdit alone does not show Replace', () => {
    const wrapper = mountButtons({ canEdit: true })
    const icons = buttonIcons(wrapper)

    expect(icons).not.toContain('mdi mdi-upload-outline')
    expect(icons).toContain('mdi mdi-delete-outline')
  })

  it('passes deleting through to the delete Button loading state', () => {
    const wrapper = mountButtons({ canEdit: true, deleting: true })
    const deleteBtn = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-delete-outline')

    expect(deleteBtn?.props('loading')).toBe(true)
  })

  it('emits preview, download, replace and delete', async () => {
    const wrapper = mountButtons({ previewable: true, canEdit: true, showReplace: true })
    const buttons = wrapper.findAllComponents({ name: 'Button' })
    const byIcon = (icon: string) => buttons.find((b) => b.props('icon') === icon)!

    await byIcon('mdi mdi-eye-outline').trigger('click')
    await byIcon('mdi mdi-download-outline').trigger('click')
    await byIcon('mdi mdi-upload-outline').trigger('click')
    await byIcon('mdi mdi-delete-outline').trigger('click')

    expect(wrapper.emitted('preview')).toHaveLength(1)
    expect(wrapper.emitted('download')).toHaveLength(1)
    expect(wrapper.emitted('replace')).toHaveLength(1)
    expect(wrapper.emitted('delete')).toHaveLength(1)
  })

  // PDM-owned files (from_pdm): the server would still allow the edit, but
  // the next sync would just restore the file, so these two stay visible
  // but disabled instead of hidden. Preview/download are unaffected.
  it('disables replace and delete, but not preview/download, when locked', () => {
    const wrapper = mountButtons({
      previewable: true,
      canEdit: true,
      showReplace: true,
      locked: true,
      lockedTooltip: 'Comes from PDM',
    })
    const byIcon = (icon: string) =>
      wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('icon') === icon)!

    // Button forwards `disabled` through $attrs onto the native <button>
    // rather than declaring it as its own prop (same note as
    // PdmFilesDialog.spec.ts's own retry/dismiss disabled check), so it
    // shows up on `attributes()`, not `props()`.
    expect(byIcon('mdi mdi-upload-outline').attributes('disabled')).toBeDefined()
    expect(byIcon('mdi mdi-delete-outline').attributes('disabled')).toBeDefined()
    expect(byIcon('mdi mdi-eye-outline').attributes('disabled')).toBeUndefined()
    expect(byIcon('mdi mdi-download-outline').attributes('disabled')).toBeUndefined()
    expect(byIcon('mdi mdi-upload-outline').attributes('aria-label')).toBe('Comes from PDM')
    expect(byIcon('mdi mdi-delete-outline').attributes('aria-label')).toBe('Comes from PDM')
  })

  it('leaves replace and delete enabled when locked is false', () => {
    const wrapper = mountButtons({ canEdit: true, showReplace: true, locked: false })
    const byIcon = (icon: string) =>
      wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('icon') === icon)!

    expect(byIcon('mdi mdi-upload-outline').attributes('disabled')).toBeUndefined()
    expect(byIcon('mdi mdi-delete-outline').attributes('disabled')).toBeUndefined()
  })
})
