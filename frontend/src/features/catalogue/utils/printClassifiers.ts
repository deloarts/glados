import type { CatalogueItemKind } from '../types/itemDetail'

/** The root_type a catalogue item kind prints under. */
export const PRINT_ROOT_TYPE: Record<CatalogueItemKind, 'bought_item' | 'made_item' | 'source_item'> = {
  bought: 'bought_item',
  made: 'made_item',
  source: 'source_item',
}

/**
 * The manual print classifier for a kind's label or docket, matching the
 * backend registry.
 */
export function printClassifier(kind: CatalogueItemKind, which: 'label' | 'docket'): string {
  return `${PRINT_ROOT_TYPE[kind]}_${which}`
}
