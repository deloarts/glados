/**
 * The handbook's top-level sections, matching the app's main navigation. A
 * doc's section is the directory it sits in. Labels and icons reuse the
 * sidebar's keys, so a nav rename carries over.
 */
export interface HandbookSectionMeta {
  key: string
  icon: string
  labelKey: string
}

export const HANDBOOK_SECTIONS: HandbookSectionMeta[] = [
  { key: 'todo', icon: 'mdi-checkbox-marked-outline', labelKey: 'main.sidebar.todo.label' },
  { key: 'workspace', icon: 'mdi-folder', labelKey: 'main.sidebar.workspace.label' },
  {
    key: 'catalogue',
    icon: 'mdi-book-open-page-variant',
    labelKey: 'main.sidebar.catalogue.label',
  },
  { key: 'procurement', icon: 'mdi-cart', labelKey: 'main.sidebar.procurement.label' },
  { key: 'production', icon: 'mdi-factory', labelKey: 'main.sidebar.production.label' },
  { key: 'resources', icon: 'mdi-bookshelf', labelKey: 'main.sidebar.resources.label' },
  {
    key: 'account',
    icon: 'mdi-account-circle-outline',
    labelKey: 'main.sidebar.account.label',
  },
]
