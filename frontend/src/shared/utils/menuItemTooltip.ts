import type { MenuItem } from 'openvue/menuitem'

/**
 * The `pt` of a ContextMenu whose disabled entries say why they are
 * disabled. OpenVue's ContextMenu has no per-item tooltip, so a disabled
 * item that carries a `title` gets it as a native title attribute on its
 * link, and every other item's markup stays untouched. The title holds the
 * same reason the matching row or dialog button shows in its tooltip.
 */
export const disabledItemTooltipPt = {
  itemLink: ({ context }: { context: { item: MenuItem } }) =>
    context.item.disabled && context.item.title ? { title: context.item.title } : {},
}
