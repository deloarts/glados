/**
 * OpenVue's Button with one change: a button that is loading is always
 * disabled. OpenVue folds `loading` into the disabled state it renders, but an
 * explicit `disabled` attribute falls through onto the native button after
 * that and wins, so `:loading="saving" :disabled="!valid"` left a saving
 * button clickable and a double click sent its request twice. The component
 * resolver in vite.config.ts hands this component out wherever a template
 * writes `<Button>`, so every button gets the guard without its own binding.
 */
import { defineComponent, h } from 'vue'
import OpenVueButton from 'openvue/button'

/** OpenVue treats a bare `disabled` attribute (the empty string) as set. */
function isDisabledAttr(value: unknown): boolean {
  return value === '' || Boolean(value)
}

const GladosButton = defineComponent({
  name: 'GladosButton',
  inheritAttrs: false,
  props: {
    loading: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    return () =>
      h(
        OpenVueButton,
        { ...attrs, loading: props.loading, disabled: props.loading || isDisabledAttr(attrs.disabled) },
        slots,
      )
  },
})

// Typed as OpenVue's Button so templates keep its full prop checking; the
// wrapper passes every prop and listener through unchanged.
export default GladosButton as unknown as typeof OpenVueButton
