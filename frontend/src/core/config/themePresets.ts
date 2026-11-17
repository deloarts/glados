import { definePreset } from '@openvue/themes'
import type { Preset } from '@openvue/themes/types'
import Aura from '@openvue/themes/aura'
import Lara from '@openvue/themes/lara'
import Material from '@openvue/themes/material'
import Nora from '@openvue/themes/nora'

/**
 * The Glados changes to OpenVue's component tokens, laid over whichever
 * preset the user picked. A spacing or colour that OpenVue exposes as a
 * token is changed here rather than by a CSS rule on its internal classes.
 */
const gladosTokens = {
  components: {
    // Tab panels sit on the page's own card, so they take no background of
    // their own and a tight padding instead of the preset's 1rem or more.
    tabs: {
      tabpanel: {
        background: 'transparent',
        padding: 'var(--space-2)',
      },
    },
    // Button labels use the body weight. The presets set 500, which Inter and
    // the variable Segoe UI render noticeably heavier than the text around them.
    button: {
      root: {
        label: {
          fontWeight: '400',
        },
      },
    },
    toolbar: {
      root: {
        padding: 'var(--space-2)',
      },
    },
    // The presets give a dialog's footer no top padding, so content scrolled
    // to its end ran right up to the buttons.
    dialog: {
      footer: {
        padding: 'var(--space-3) {overlay.modal.padding} {overlay.modal.padding}',
      },
    },
  },
}

function withGladosTokens(preset: Preset): Preset {
  return definePreset(preset as Record<string, unknown>, gladosTokens) as Preset
}

/** The presets a user can pick, each with the Glados tokens applied. */
export const themePresets: Record<string, Preset> = {
  Aura: withGladosTokens(Aura),
  Lara: withGladosTokens(Lara),
  Material: withGladosTokens(Material),
  Nora: withGladosTokens(Nora),
}

/** The preset the app boots with. */
export const defaultThemePreset = themePresets.Aura
