import { mount } from '@vue/test-utils'
import type { ComponentMountingOptions } from '@vue/test-utils'
import { createPinia } from 'pinia'
import type { Pinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Aura from '@openvue/themes/aura'
import type { Component } from 'vue'

import { i18n } from '@/core/i18n'
import { settleConfirmationsOnce } from '@/core/confirm/settleConfirmationsOnce'
import { handbookHelp } from '@/features/handbook'
// Imported from its module rather than the barrel, so a spec does not load
// the print template pages it never mounts.
import { templatePrinting } from '@/features/print-labels/templatePrinting'
import { edpSettingsTab } from '@/features/bought-items/edpSettingsTab'
import { productionSettingsTab } from '@/features/production/productionSettingsTab'
import { planningSettingsTab } from '@/features/production/planningSettingsTab'
import { timeTrackingSections } from '@/features/time-tracking/timeTrackingSections'
import { agentSections } from '@/features/agents/agentSections'

export type MountWithAppOptions<T extends Component> = ComponentMountingOptions<T> & {
  /**
   * Pass an existing Pinia instance when the spec needs to seed store state
   * (via `setActivePinia(pinia)` + `useXStore()`) before mounting. Defaults
   * to a fresh `createPinia()` when omitted.
   */
  pinia?: Pinia
}

/**
 * `mount()` pre-wired with the plugin set almost every component spec needs:
 * Pinia, OpenVue (Aura preset), OpenVue's ToastService and
 * ConfirmationService (with the once-only guard), the app's i18n
 * instance, the handbook as the help provider, the print templates as the
 * print provider, and the tabs and sections features register on the account
 * page and the admin settings, the way main.ts installs them, so a help
 * button, a print action or a registered tab in a mounted view behaves as it
 * does in the app.
 * This was hand-assembled the same way at the top of ~90 spec files.
 * Centralising it means a spec only has to state what makes it different
 * from the norm.
 *
 * Caller-supplied `global` options are merged, not replaced: any extra
 * `plugins` (a router, say) are appended after the standard ones, and
 * `stubs`/`mocks`/`directives`/`components`/`provide`/`config` pass straight
 * through untouched.
 */
export function mountWithApp<T extends Component>(
  component: T,
  options: MountWithAppOptions<T> = {},
) {
  const { pinia = createPinia(), global: globalOptions, ...rest } = options
  const { plugins: extraPlugins = [], ...restGlobal } = globalOptions ?? {}

  return mount(component, {
    ...rest,
    global: {
      ...restGlobal,
      plugins: [
        pinia,
        [OpenVue, { theme: { preset: Aura } }],
        ToastService,
        ConfirmationService,
        settleConfirmationsOnce,
        i18n,
        handbookHelp,
        templatePrinting,
        timeTrackingSections,
        productionSettingsTab,
        planningSettingsTab,
        edpSettingsTab,
        agentSections,
        // A spec that still lists ConfirmationService itself would apply it
        // twice, which Vue warns about.
        ...extraPlugins.filter((plugin) => plugin !== ConfirmationService),
      ],
    },
  } as ComponentMountingOptions<T>)
}
