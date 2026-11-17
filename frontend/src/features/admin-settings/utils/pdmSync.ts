import type { PdmWatchedFolder } from '../types/adminSettingsTypes'

export interface PdmSyncValidation {
  emptyPath: boolean
  duplicatePath: boolean
  missingEnabledFolder: boolean
  missingReleasedState: boolean
  missingFilenamePattern: boolean
  hasError: boolean
}

/**
 * Light client-side mirror of the backend's watched-folder path
 * normalisation (stored with a single leading backslash, no trailing
 * separator), only precise enough for duplicate detection here, the
 * backend stays the real normaliser. Exported for PdmFolderPickerDialog,
 * which uses it the same way to flag a folder already on the watched
 * list.
 */
export function normalizePdmPath(path: string): string {
  const collapsed = path.trim().replace(/\//g, '\\').replace(/\\+/g, '\\')
  const withLeading = collapsed.startsWith('\\') ? collapsed : `\\${collapsed}`
  return withLeading.length > 1 ? withLeading.replace(/\\+$/, '') : withLeading
}

/**
 * Mirrors the backend's UpdatePdmSettings rules so the SolidWorks PDM
 * section's PdmSyncSection can block Save the same way the tab already
 * blocks on a variable-map error, instead of only discovering the problem
 * from a 400 after the click. Shared by PdmSyncSection (inline hints) and
 * the tab (Save gating) so they can never drift apart.
 */
export function validatePdmSync(input: {
  enabled: boolean
  watchedFolders: PdmWatchedFolder[]
  // Enabling needs at least one released state for made or bought items, as
  // the backend requires.
  madeReleasedStateIds: number[]
  boughtReleasedStateIds: number[]
}): PdmSyncValidation {
  const trimmedPaths = input.watchedFolders.map((f) => f.path.trim())
  const emptyPath = trimmedPaths.some((p) => p === '')
  const normalizedNonEmpty = trimmedPaths.filter((p) => p !== '').map(normalizePdmPath)
  const duplicatePath = new Set(normalizedNonEmpty).size !== normalizedNonEmpty.length
  const missingEnabledFolder = input.enabled && !input.watchedFolders.some((f) => f.enabled)
  const missingReleasedState =
    input.enabled &&
    input.madeReleasedStateIds.length === 0 &&
    input.boughtReleasedStateIds.length === 0
  // Regex semantics are the backend's job (422/400 on save); this only
  // checks a pattern was typed at all once "By filename" is picked.
  const missingFilenamePattern = input.watchedFolders.some(
    (f) => f.kind === 'documents' && f.match_by === 'filename' && (f.filename_pattern ?? '').trim() === '',
  )

  return {
    emptyPath,
    duplicatePath,
    missingEnabledFolder,
    missingReleasedState,
    missingFilenamePattern,
    hasError:
      emptyPath ||
      duplicatePath ||
      missingEnabledFolder ||
      missingReleasedState ||
      missingFilenamePattern,
  }
}

/** Trims, drops a leading dot and lower-cases a file extension, the way the
 * backend normalises the extension lists and the document category keys. */
export function normalizeExtension(raw: string): string {
  return raw.trim().replace(/^\./, '').toLowerCase()
}
