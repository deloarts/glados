import { describe, it, expect } from 'vitest'

import { normalizePdmPath, validatePdmSync } from '../pdmSync'
import type { PdmWatchedFolder } from '../../types/adminSettingsTypes'

// Exercises validatePdmSync directly, beyond PdmSyncSection.spec.ts's
// validation-hint assertions, including the missingFilenamePattern rule of
// the "documents" watched-folder kind.

function makeFolder(overrides: Partial<PdmWatchedFolder> = {}): PdmWatchedFolder {
  return {
    path: '\\Made-Parts',
    kind: 'made',
    recursive: true,
    enabled: true,
    match_by: null,
    filename_pattern: null,
    folder_id: null,
    ...overrides,
  }
}

describe('normalizePdmPath', () => {
  it('collapses forward slashes and repeated separators to a single leading backslash', () => {
    expect(normalizePdmPath('/Made-Parts//Sub')).toBe('\\Made-Parts\\Sub')
  })

  it('adds a leading backslash when missing and strips a trailing one', () => {
    expect(normalizePdmPath('Made-Parts\\')).toBe('\\Made-Parts')
  })

  it('trims surrounding whitespace', () => {
    expect(normalizePdmPath('  \\Made-Parts  ')).toBe('\\Made-Parts')
  })
})

describe('validatePdmSync', () => {
  it('reports no errors for a valid, disabled configuration', () => {
    const result = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder()],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })

    expect(result).toEqual({
      emptyPath: false,
      duplicatePath: false,
      missingEnabledFolder: false,
      missingReleasedState: false,
      missingFilenamePattern: false,
      hasError: false,
    })
  })

  it('flags an empty path', () => {
    const result = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ path: '   ' })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })

    expect(result.emptyPath).toBe(true)
    expect(result.hasError).toBe(true)
  })

  it('flags duplicate paths once normalised', () => {
    const result = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ path: '\\Made-Parts' }), makeFolder({ path: 'Made-Parts\\' })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })

    expect(result.duplicatePath).toBe(true)
  })

  it('requires an enabled folder and a released state only while the integration is enabled', () => {
    const disabled = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ enabled: false })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    expect(disabled.missingEnabledFolder).toBe(false)
    expect(disabled.missingReleasedState).toBe(false)

    const enabled = validatePdmSync({
      enabled: true,
      watchedFolders: [makeFolder({ enabled: false })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    expect(enabled.missingEnabledFolder).toBe(true)
    expect(enabled.missingReleasedState).toBe(true)
    expect(enabled.hasError).toBe(true)
  })

  it('a released state configured for either kind alone satisfies the requirement', () => {
    const madeOnly = validatePdmSync({
      enabled: true,
      watchedFolders: [makeFolder()],
      madeReleasedStateIds: [10],
      boughtReleasedStateIds: [],
    })
    expect(madeOnly.missingReleasedState).toBe(false)

    const boughtOnly = validatePdmSync({
      enabled: true,
      watchedFolders: [makeFolder()],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [10],
    })
    expect(boughtOnly.missingReleasedState).toBe(false)
  })

  it('requires a filename pattern only for a "documents" row matched by filename', () => {
    const byDatacard = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ kind: 'documents', match_by: 'datacard', filename_pattern: null })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    expect(byDatacard.missingFilenamePattern).toBe(false)

    const byFilenameBlank = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ kind: 'documents', match_by: 'filename', filename_pattern: '  ' })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    expect(byFilenameBlank.missingFilenamePattern).toBe(true)
    expect(byFilenameBlank.hasError).toBe(true)

    const byFilenameSet = validatePdmSync({
      enabled: false,
      watchedFolders: [
        makeFolder({ kind: 'documents', match_by: 'filename', filename_pattern: '^(?P<part_number>.+)$' }),
      ],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    expect(byFilenameSet.missingFilenamePattern).toBe(false)
  })

  it('never flags a missing filename pattern for a non-"documents" row, whatever match_by holds', () => {
    const result = validatePdmSync({
      enabled: false,
      watchedFolders: [makeFolder({ kind: 'made', match_by: null, filename_pattern: '' })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })

    expect(result.missingFilenamePattern).toBe(false)
  })
})
