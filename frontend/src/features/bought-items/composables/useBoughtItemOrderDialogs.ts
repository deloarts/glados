import { inject, type Component, type InjectionKey } from 'vue'

/**
 * The order dialogs the bought-item catalogue opens from a row: adding the
 * item to an order and listing its order history. Orders belong to Planning
 * and fulfillment, so the page that hosts the catalogue provides the dialogs
 * and this feature never imports the orders feature. Each dialog opens
 * through `v-model:visible` and takes the bought item as its `item` prop.
 */
export interface BoughtItemOrderDialogs {
  addToOrder: Component
  orderHistory: Component
}

export const boughtItemOrderDialogsKey: InjectionKey<BoughtItemOrderDialogs> = Symbol('boughtItemOrderDialogs')

/** The order dialogs the hosting page provided, or null when it provided none. */
export function useBoughtItemOrderDialogs(): BoughtItemOrderDialogs | null {
  return inject(boughtItemOrderDialogsKey, null)
}
