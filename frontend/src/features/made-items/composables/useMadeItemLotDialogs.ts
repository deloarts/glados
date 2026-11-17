import { inject, type Component, type InjectionKey } from 'vue'

/**
 * The lot dialog the made-item catalogue opens from a row: the item's lot
 * history. Lots belong to Planning and fulfillment, so the page that hosts
 * the catalogue provides the dialog and this feature never imports the
 * production feature. The dialog opens through `v-model:visible` and takes
 * the made item as its `item` prop.
 */
export interface MadeItemLotDialogs {
  history: Component
}

export const madeItemLotDialogsKey: InjectionKey<MadeItemLotDialogs> = Symbol('madeItemLotDialogs')

/** The lot dialogs the hosting page provided, or null when it provided none. */
export function useMadeItemLotDialogs(): MadeItemLotDialogs | null {
  return inject(madeItemLotDialogsKey, null)
}
