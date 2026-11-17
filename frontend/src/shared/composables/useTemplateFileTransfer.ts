import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { downloadBlob } from '@/core/utils/downloadBlob'
import { TemplateFileError, serializeTemplateFile, type TemplateFileKind } from '@/shared/utils/templateFile'

/** A picked file with its text. */
export interface PickedTextFile {
  name: string
  text: string
}

/**
 * Opens the browser's file picker and resolves with the picked files. A
 * cancelled picker resolves with none where the browser reports the cancel;
 * where it does not, the promise simply never settles.
 */
export function pickFiles(accept: string, multiple = false): Promise<File[]> {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = accept
    input.multiple = multiple
    input.addEventListener('change', () => resolve(Array.from(input.files ?? [])), { once: true })
    input.addEventListener('cancel', () => resolve([]), { once: true })
    input.click()
  })
}

/**
 * Import and export of template files for the settings editors. An import
 * only fills the editor's form: nothing is stored until the admin saves, so
 * the editor's own validation and save path apply unchanged.
 */
export function useTemplateFileTransfer() {
  const { t } = useI18n()
  const toast = useAppToast()

  function errorMessage(error: unknown, fileName: string): string {
    if (error instanceof TemplateFileError) {
      return t(`templateFiles.errors.${error.reason}`, { file: fileName, detail: error.detail })
    }
    return t('templateFiles.errors.readFailed', { file: fileName })
  }

  function reportImported(fileNames: string[], ignored: string[]): void {
    toast.success(
      t('templateFiles.imported', { files: fileNames.join(', ') }),
      ignored.length
        ? t('templateFiles.importedIgnored', { keys: ignored.join(', ') })
        : t('templateFiles.importedReview'),
    )
  }

  /**
   * Lets the admin pick files, reads them and hands them to `apply`, which
   * fills the form and returns the keys it ignored. Returns whether the
   * import went through; a failure leaves the form as `apply` left it and
   * toasts the reason.
   */
  async function importFiles(
    accept: string,
    apply: (files: PickedTextFile[]) => string[],
    multiple = false,
  ): Promise<boolean> {
    const files = await pickFiles(accept, multiple)
    if (files.length === 0) return false
    let current = files[0]!.name
    try {
      const picked: PickedTextFile[] = []
      for (const file of files) {
        current = file.name
        picked.push({ name: file.name, text: await file.text() })
      }
      current = files.map((f) => f.name).join(', ')
      reportImported(
        files.map((f) => f.name),
        apply(picked),
      )
      return true
    } catch (error) {
      toast.error(t('templateFiles.importFailed'), errorMessage(error, current))
      return false
    }
  }

  function exportFile(kind: TemplateFileKind, content: Record<string, unknown>, fileName: string): void {
    downloadBlob(new Blob([serializeTemplateFile(kind, content)], { type: 'application/json' }), fileName)
  }

  function exportText(text: string, fileName: string, type: string): void {
    downloadBlob(new Blob([text], { type }), fileName)
  }

  return { importFiles, exportFile, exportText, errorMessage, reportImported }
}
