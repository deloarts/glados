import { detectDocketFields, detectZplPlaceholders } from './templateFields'

/**
 * Labels (ZPL) and dockets (PDF) share one template table and one set of
 * management components. Everything that differs between the two pages is
 * listed here, so the shared components take a single kind prop.
 */
export type PrintTemplateKind = 'label' | 'docket'

export interface PrintTemplateKindConfig {
  /** Locale namespace that holds the page's copy. */
  i18nPrefix: 'printLabels' | 'printDockets'
  /** Prefix of element ids, so labels stay tied to the right inputs. */
  idPrefix: 'pl' | 'pd'
  /** Store getter with the templates of this kind. */
  templatesKey: 'labelTemplates' | 'docketTemplates'
  /** Printer kind the editor offers. */
  printerKind: 'zpl_label' | 'ipp_document'
  /** File types the source upload accepts. */
  sourceAccept: string
  /** The source is a JSON block spec whose syntax the editor checks. */
  jsonSource: boolean
  /** The template has a paper size, shown as a column and edited as a select. */
  paper: boolean
  /** The rendered output can be downloaded as a file. */
  download: boolean
  /** The editor preview also shows the rendered ZPL text. */
  renderedText: boolean
  /** Width of the standalone preview dialog. */
  previewDialogWidth: string
  detectFields: (source: string) => string[]
  /** How a detected field is shown in the field map. */
  fieldToken: (name: string) => string
}

export const PRINT_TEMPLATE_KINDS: Record<PrintTemplateKind, PrintTemplateKindConfig> = {
  label: {
    i18nPrefix: 'printLabels',
    idPrefix: 'pl',
    templatesKey: 'labelTemplates',
    printerKind: 'zpl_label',
    sourceAccept: '.zpl,.txt',
    jsonSource: false,
    paper: false,
    download: false,
    renderedText: true,
    previewDialogWidth: 'var(--dialog-width-sm)',
    detectFields: detectZplPlaceholders,
    fieldToken: (name) => `{${name}}`,
  },
  docket: {
    i18nPrefix: 'printDockets',
    idPrefix: 'pd',
    templatesKey: 'docketTemplates',
    printerKind: 'ipp_document',
    sourceAccept: '.json,.txt',
    jsonSource: true,
    paper: true,
    download: true,
    renderedText: false,
    previewDialogWidth: 'var(--dialog-width-md)',
    detectFields: detectDocketFields,
    fieldToken: (name) => name,
  },
}
