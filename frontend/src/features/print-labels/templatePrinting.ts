import type { Plugin } from 'vue'

import { printProviderKey, type PrintProvider } from '@/shared/print'

import { downloadPrintTemplate } from './api/downloadPrintTemplate'
import { printDocuments } from './api/printDocuments'
import { printLotScrapTag } from './api/printLotScrapTag'
import { usePrintTemplatesStore } from './stores/printTemplatesStore'

/**
 * Installs the print templates as the app's print provider, so every screen
 * that prints a label or a docket goes through them. The app shell installs
 * it once with `app.use(templatePrinting)`, which keeps the screens of lower
 * contexts free of imports into this feature.
 */
export const templatePrinting: Plugin = {
  install(app) {
    const provider: PrintProvider = {
      print: (request) => printDocuments(request),
      printLotScrapTag: (lotId) => printLotScrapTag(lotId),
      download: (classifier, rootType, rootId) => downloadPrintTemplate(classifier, rootType, rootId),
      // Reads the templates through their store, so the print templates page
      // and this check share one fetched list. The store is resolved in the
      // app's context, so it is the Pinia instance this app was given.
      async hasDefaultPrinter(classifier) {
        const store = app.runWithContext(() => usePrintTemplatesStore())
        await store.refresh()
        return Boolean(store.items.find((template) => template.classifier === classifier)?.printer_id)
      },
    }
    app.provide(printProviderKey, provider)
  },
}
