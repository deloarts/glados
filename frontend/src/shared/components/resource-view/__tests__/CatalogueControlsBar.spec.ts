import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import CatalogueControlsBar from '../CatalogueControlsBar.vue'

function mountBar(props: {
  i18nPrefix?: string
  canWrite?: boolean
  editMode?: boolean
  writeBlocked?: string
  showCreate?: boolean
}) {
  return mountWithApp(CatalogueControlsBar, {
    props: {
      i18nPrefix: 'boughtItems.catalogue.controls',
      canWrite: true,
      editMode: false,
      ...props,
    },
  })
}

function button(bar: ReturnType<typeof mountBar>, label: string) {
  return bar.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('CatalogueControlsBar', () => {
  it('resolves button labels from the given i18n prefix', () => {
    const bar = mountBar({ i18nPrefix: 'madeItems.catalogue.controls' })

    expect(button(bar, i18n.global.t('madeItems.catalogue.controls.new'))).toBeDefined()
    expect(button(bar, i18n.global.t('madeItems.catalogue.controls.edit'))).toBeDefined()

    bar.unmount()
  })

  it('disables New and Edit when canWrite is false', () => {
    const bar = mountBar({ canWrite: false })

    // OpenVue's Button reads `disabled` off $attrs rather than declaring it
    // as its own prop, so it must be asserted as a rendered attribute.
    expect(
      button(bar, i18n.global.t('boughtItems.catalogue.controls.new'))!.attributes('disabled'),
    ).toBeDefined()
    expect(
      button(bar, i18n.global.t('boughtItems.catalogue.controls.edit'))!.attributes('disabled'),
    ).toBeDefined()

    bar.unmount()
  })

  it('emits create when New is clicked', async () => {
    const bar = mountBar({})

    await button(bar, i18n.global.t('boughtItems.catalogue.controls.new'))!.trigger('click')

    expect(bar.emitted('create')).toHaveLength(1)

    bar.unmount()
  })

  it('emits toggle-edit when Edit is clicked, and switches Edit to solid style while active', async () => {
    const inactive = mountBar({ editMode: false })
    expect(button(inactive, i18n.global.t('boughtItems.catalogue.controls.edit'))!.props('text')).toBe(
      true,
    )

    await button(inactive, i18n.global.t('boughtItems.catalogue.controls.edit'))!.trigger('click')
    expect(inactive.emitted('toggle-edit')).toHaveLength(1)
    inactive.unmount()

    const active = mountBar({ editMode: true })
    expect(button(active, i18n.global.t('boughtItems.catalogue.controls.edit'))!.props('text')).toBe(
      false,
    )
    active.unmount()
  })

  it('shows the New button by default, and hides it entirely when showCreate is false', () => {
    const shown = mountBar({})
    expect(button(shown, i18n.global.t('boughtItems.catalogue.controls.new'))).toBeDefined()
    shown.unmount()

    const hidden = mountBar({ showCreate: false })
    expect(button(hidden, i18n.global.t('boughtItems.catalogue.controls.new'))).toBeUndefined()
    // Edit stays available; showCreate only ever hides New.
    expect(button(hidden, i18n.global.t('boughtItems.catalogue.controls.edit'))).toBeDefined()
    hidden.unmount()
  })

  it('offers no Export button, since no catalogue export exists', () => {
    const bar = mountBar({})
    const icons = bar.findAllComponents({ name: 'Button' }).map((b) => b.props('icon'))
    expect(icons).not.toContain('mdi mdi-export')
    bar.unmount()
  })

  it('names the reason on New and Edit while writing is blocked', () => {
    const blocked = 'This needs the permission Write Bought Items.'
    const bar = mountBar({ canWrite: false, writeBlocked: blocked })
    for (const label of ['new', 'edit']) {
      const b = button(bar, i18n.global.t(`boughtItems.catalogue.controls.${label}`))!
      expect(b.attributes('disabled')).toBeDefined()
      const span = b.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
      expect(span?.$_ptooltipValue).toBe(blocked)
    }
    bar.unmount()
  })
})
