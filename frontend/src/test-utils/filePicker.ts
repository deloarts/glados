import { vi } from 'vitest'

/**
 * Makes the next file picker the code opens answer with `files`, as if the
 * user had picked them. Covers pickers opened through a throwaway input, as
 * pickFiles in useTemplateFileTransfer does. Returns the spy so a test can
 * restore it.
 */
export function stubFilePicker(files: File[]) {
  return vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function (this: HTMLInputElement) {
    if (this.type !== 'file') return
    Object.defineProperty(this, 'files', { value: files, configurable: true })
    this.dispatchEvent(new Event('change'))
  })
}

/** A picked text file, as the browser hands it over. */
export function textFile(name: string, text: string): File {
  return new File([text], name, { type: 'text/plain' })
}
