import { inject, type InjectionKey } from 'vue'

import type { Schemas } from '@/core/api/generated'

/** One print job as the backend reports it. A failed print is a job, not an exception. */
export type PrintJob = Schemas['PrintJobResponse']

/** A manual print of one or more classifiers for one root record. */
export type PrintRequest = Schemas['PrintRequestBody']

/**
 * The label and docket printing a screen starts its prints through. The app
 * shell installs the real one, the print templates, at the app level, so a
 * catalogue row, an order or a lot can print without importing the feature
 * that renders and sends the documents.
 */
export interface PrintProvider {
  /** Prints the listed classifiers; check each returned job's status. */
  print(request: PrintRequest): Promise<PrintJob[]>
  /** Prints the scrap tag of a lot's latest scrap record, resolved on the server. */
  printLotScrapTag(lotId: number): Promise<PrintJob>
  /** Renders what a print would send and saves it as a file, which needs no printer. */
  download(classifier: string, rootType: string, rootId: number): Promise<{ warnings: string[] }>
  /** Whether the classifier's template has a default printer, so a print would go out. */
  hasDefaultPrinter(classifier: string): Promise<boolean>
}

export const printProviderKey: InjectionKey<PrintProvider> = Symbol('printProvider')

function notInstalled(): Promise<never> {
  return Promise.reject(new Error('No print provider is installed'))
}

// Without an installed provider nothing can print, so every print fails the
// way a failed request does and the calling screen shows its error toast.
const NO_PRINT: PrintProvider = {
  print: notInstalled,
  printLotScrapTag: notInstalled,
  download: notInstalled,
  hasDefaultPrinter: () => Promise.resolve(false),
}

/** Reads the print provider the app shell installed. */
export function usePrint(): PrintProvider {
  return inject(printProviderKey, NO_PRINT)
}
