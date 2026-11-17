import { describe, it, expect } from 'vitest'
import {
  MAX_FEATURE_TREE_TEMPLATE_LENGTH,
  hasFeatureTreeTemplateError,
  propertyLink,
  renderFeatureTreePreview,
  validateFeatureTreeTemplate,
} from '../featureTreeTemplate'

describe('propertyLink', () => {
  it('builds a SolidWorks property link', () => {
    expect(propertyLink('Glados.ArticleName')).toBe('$PRP:"Glados.ArticleName"')
  })
})

describe('renderFeatureTreePreview', () => {
  const labels = { 'pdm.partnumber': '<Part number>', 'glados.articlename': '<Article name>' }

  it('replaces every known link with its label and keeps the literal text', () => {
    expect(
      renderFeatureTreePreview('$PRP:"PDM.PartNumber" ($PRP:"Glados.ArticleName")', labels),
    ).toBe('<Part number> (<Article name>)')
  })

  it('matches property names regardless of case', () => {
    expect(renderFeatureTreePreview('$prp:"pdm.PARTNUMBER"', labels)).toBe('<Part number>')
  })

  it('shows an unknown property by its own name', () => {
    expect(renderFeatureTreePreview('$PRP:"SW-File Name"', labels)).toBe('<SW-File Name>')
  })

  it('passes text without links through unchanged, braces included', () => {
    expect(renderFeatureTreePreview('{Static} text', labels)).toBe('{Static} text')
  })
})

describe('validateFeatureTreeTemplate', () => {
  const variableMap = {
    part_number: 'PDM.PartNumber',
    article_name: 'Glados.ArticleName',
    note: '',
    feature_tree_representation: 'Glados.FeatureTreeRepresentation',
  }
  const valid = { controlCharacter: false, tooLong: false, selfReference: false, unknownProperties: [] }

  it('accepts links to mapped properties', () => {
    expect(
      validateFeatureTreeTemplate('$PRP:"PDM.PartNumber" - $PRP:"glados.articlename"', variableMap),
    ).toEqual(valid)
  })

  it('lists each link to a property outside the mapping once, as a warning only', () => {
    const validation = validateFeatureTreeTemplate(
      '$PRP:"SW-File Name" $PRP:"Description" $PRP:"SW-File Name"',
      variableMap,
    )
    expect(validation.unknownProperties).toEqual(['SW-File Name', 'Description'])
    expect(hasFeatureTreeTemplateError(validation)).toBe(false)
  })

  it('reports a link to its own property regardless of case', () => {
    const validation = validateFeatureTreeTemplate(
      '$PRP:"glados.featuretreerepresentation"',
      variableMap,
    )
    expect(validation.selfReference).toBe(true)
    expect(validation.unknownProperties).toEqual([])
    expect(hasFeatureTreeTemplateError(validation)).toBe(true)
  })

  it('never reports a self-reference while the feature-tree field is unmapped', () => {
    const validation = validateFeatureTreeTemplate('$PRP:"Glados.FeatureTreeRepresentation"', {
      ...variableMap,
      feature_tree_representation: '',
    })
    expect(validation.selfReference).toBe(false)
    expect(validation.unknownProperties).toEqual(['Glados.FeatureTreeRepresentation'])
  })

  it('reports a tab or line break', () => {
    expect(validateFeatureTreeTemplate('a\tb', variableMap).controlCharacter).toBe(true)
    expect(validateFeatureTreeTemplate('a\nb', variableMap).controlCharacter).toBe(true)
  })

  it('reports a template over the length cap', () => {
    const atCap = 'x'.repeat(MAX_FEATURE_TREE_TEMPLATE_LENGTH)
    expect(validateFeatureTreeTemplate(atCap, variableMap).tooLong).toBe(false)
    expect(validateFeatureTreeTemplate(`${atCap}x`, variableMap).tooLong).toBe(true)
  })
})
