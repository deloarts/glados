import { describe, expect, it } from 'vitest'

import {
  buildRequiredFieldNames,
  validateKindVariableMatch,
  validateVariableMap,
  validateWritebackVariables,
} from '../itemFieldOwnership'

describe('validateVariableMap', () => {
  it('flags no error for an entirely unmapped map', () => {
    expect(validateVariableMap({})).toEqual({ duplicate: false, missingIdentity: false })
  })

  it('flags a duplicate variable name, blank entries excluded from the collision check', () => {
    const result = validateVariableMap({
      part_number: 'PDM.PartNumber',
      revision: 'PDM.PartNumber',
      article_name: '',
      mass: '',
    })
    expect(result.duplicate).toBe(true)
  })

  it('requires part_number and revision once any other field is mapped', () => {
    expect(validateVariableMap({ article_name: 'Glados.ArticleName' }).missingIdentity).toBe(true)
    expect(
      validateVariableMap({
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        article_name: 'Glados.ArticleName',
      }).missingIdentity,
    ).toBe(false)
  })

  // The backend defaults a stored map's missing `kind` entry to a non-empty
  // value on every read (_with_kind_default), so a fresh/unconfigured PDM
  // setup always has `kind` mapped. Its own _validate_variable_map
  // excludes `kind` from "any other field mapped" for this rule, mirrored
  // here, or every fresh map would permanently fail identity validation.
  it('does not count a mapped kind alone as triggering the part_number/revision requirement', () => {
    expect(validateVariableMap({ kind: 'Glados.Kind' }).missingIdentity).toBe(false)
    expect(
      validateVariableMap({ kind: 'Glados.Kind', article_name: 'Glados.ArticleName' }).missingIdentity,
    ).toBe(true)
  })
})

// Mirrors the backend's UpdatePdmSettings cross-map rule: whenever either
// map's `kind` entry is set, both must name the same, non-empty variable.
describe('validateKindVariableMatch', () => {
  it('passes when neither map has a kind entry set', () => {
    expect(validateKindVariableMatch({}, {})).toBe(false)
  })

  it('passes when both maps agree on a non-empty kind variable', () => {
    expect(
      validateKindVariableMatch({ kind: 'Glados.Kind' }, { kind: 'Glados.Kind' }),
    ).toBe(false)
  })

  it('blocks when only one map has kind set', () => {
    expect(validateKindVariableMatch({ kind: 'Glados.Kind' }, {})).toBe(true)
    expect(validateKindVariableMatch({}, { kind: 'Glados.Kind' })).toBe(true)
  })

  it('blocks when the two maps name different variables', () => {
    expect(
      validateKindVariableMatch({ kind: 'Glados.Kind' }, { kind: 'Glados.Art' }),
    ).toBe(true)
  })

  it('treats a blank/whitespace-only entry the same as unset', () => {
    expect(validateKindVariableMatch({ kind: '  ' }, { kind: '  ' })).toBe(false)
    expect(validateKindVariableMatch({ kind: 'Glados.Kind' }, { kind: '  ' })).toBe(true)
  })
})

function fullyMappedMaps(): [Record<string, string>, Record<string, string>] {
  const map = {
    glados_ids: 'Glados.Ids',
    newest_revision_sync_state: 'Glados.NewestRevisionSyncState',
    newest_revision_synced_at: 'Glados.NewestRevisionSyncedAt',
  }
  return [{ ...map }, { ...map }]
}

// Mirrors the backend's UpdatePdmSettings write-back rule: while
// `writeback_enabled` is on, the three write-back fields must be mapped,
// non-blank and identical in both maps.
describe('validateWritebackVariables', () => {
  it('passes when write-back is disabled, regardless of the maps', () => {
    expect(validateWritebackVariables({}, {}, false)).toBe(false)
  })

  it('passes when write-back is enabled and all three fields agree in both maps', () => {
    const [made, bought] = fullyMappedMaps()
    expect(validateWritebackVariables(made, bought, true)).toBe(false)
  })

  it('blocks when write-back is enabled and a field is missing from one map', () => {
    const [made, bought] = fullyMappedMaps()
    delete bought.newest_revision_synced_at
    expect(validateWritebackVariables(made, bought, true)).toBe(true)
  })

  it('blocks when write-back is enabled and the maps disagree on a variable name', () => {
    const [made, bought] = fullyMappedMaps()
    bought.glados_ids = 'Glados.IdsList'
    expect(validateWritebackVariables(made, bought, true)).toBe(true)
  })

  it('treats a blank/whitespace-only entry the same as unset', () => {
    const [made, bought] = fullyMappedMaps()
    made.glados_ids = '  '
    bought.glados_ids = '  '
    expect(validateWritebackVariables(made, bought, true)).toBe(true)
  })
})

describe('buildRequiredFieldNames', () => {
  it('returns an empty list for an empty map', () => {
    expect(buildRequiredFieldNames({})).toEqual([])
  })

  it('returns only the checked names, field names and pseudo-rule names alike', () => {
    expect(
      buildRequiredFieldNames({
        mass: true,
        source_item_id: false,
        fabrication_step: true,
      }),
    ).toEqual(['mass', 'fabrication_step'])
  })

  it('returns an empty list when nothing is checked', () => {
    expect(buildRequiredFieldNames({ mass: false, article_group_ids: false })).toEqual([])
  })
})
