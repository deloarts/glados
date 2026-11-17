/**
 * Describes an entity's file categories to the shared FilesSection.
 *
 * Every entity that carries attachments (bought items, made items, source
 * items, products, orders) renders the same chrome: a titled slot per
 * single-file category plus one list for the category that accumulates. Only
 * the category set, their labels and what an occupied slot looks like differ,
 * so those are data rather than five copies of the component.
 */

/** How an occupied slot renders its file. */
export type SlotRender =
  /** Inline <img> preview. */
  | 'image'
  /** Inline 3D viewer. */
  | 'mesh'
  /** Name + size row. */
  | 'file'

/**
 * Header accent. Kept to a fixed set so the colours live in the shared
 * stylesheet rather than being injected per call site.
 */
export type SlotAccent =
  | 'purple'
  | 'blue'
  | 'teal'
  | 'orange'
  | 'red'
  | 'green'
  | 'indigo'
  | 'grey'

export interface SingletonCategorySpec<TCategory extends string = string> {
  key: TCategory
  /** i18n key for the slot header. */
  labelKey: string
  accent: SlotAccent
  /** `accept` for the file input. Omit to accept anything. */
  accept?: string
  render: SlotRender
  /** Downscale before upload, for slots that hold a small preview image. */
  downscaleTo?: number
}

/** The one category per entity that holds many files rather than replacing. */
export interface MultiCategorySpec<TCategory extends string = string> {
  key: TCategory
  labelKey: string
  accent: SlotAccent
  accept?: string
  /** mdi class for the row icon. */
  icon: string
}

/** What FilesSection reads off a file, whichever entity kind it belongs to. */
// eslint-disable-next-line no-restricted-syntax -- a structural constraint every item kind's file response must satisfy
export interface SectionFile {
  id: number
  file_name: string
  mime_type: string
  size_bytes: number
  category: string
  /** True for a file PDM ingested rather than a web upload. */
  from_pdm?: boolean
}
