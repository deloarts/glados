/**
 * Helpers for the feature-tree template, the text the SolidWorks add-in
 * writes verbatim into the custom property mapped to
 * `feature_tree_representation`. Each `$PRP:"name"` in it is SolidWorks'
 * own link to another custom property, which SolidWorks resolves itself,
 * so nothing here renders real values.
 *
 * `validateFeatureTreeTemplate` mirrors the backend's
 * `validate_feature_tree_template` (domain.services.feature_tree_template),
 * so the errors it reports are the ones the backend's PUT would reject,
 * shown before the request is even sent. It additionally lists links to
 * properties outside the field mapping, which the backend accepts because
 * they may be real SolidWorks properties; the settings page only warns
 * about them.
 */
export const MAX_FEATURE_TREE_TEMPLATE_LENGTH = 255

export const FEATURE_TREE_FIELD = 'feature_tree_representation'

// SolidWorks matches property names regardless of case, so every lookup
// here compares lower-cased names.
const PROPERTY_LINK = /\$PRP:"([^"]*)"/gi

export function propertyLink(propertyName: string): string {
  return `$PRP:"${propertyName}"`
}

function hasControlCharacter(template: string): boolean {
  for (const char of template) {
    const code = char.charCodeAt(0)
    if (code < 0x20 || code === 0x7f) return true
  }
  return false
}

/**
 * Replaces each `$PRP:"name"` link with `labels[name.toLowerCase()]`, or
 * with `<name>` for a property `labels` does not know, for the settings
 * page's preview.
 */
export function renderFeatureTreePreview(template: string, labels: Record<string, string>): string {
  return template.replace(
    PROPERTY_LINK,
    (_match, name: string) => labels[name.toLowerCase()] ?? `<${name}>`,
  )
}

export interface FeatureTreeTemplateValidation {
  controlCharacter: boolean
  tooLong: boolean
  selfReference: boolean
  // Linked properties outside the field mapping, a warning only.
  unknownProperties: string[]
}

/**
 * Validates `template` against one kind's field mapping, `variableMap`
 * (field to custom property name, '' for unmapped): a link to the
 * property mapped to `feature_tree_representation` is a self-reference,
 * and a link to a property no field is mapped to is unknown.
 */
export function validateFeatureTreeTemplate(
  template: string,
  variableMap: Readonly<Record<string, string>>,
): FeatureTreeTemplateValidation {
  const own = (variableMap[FEATURE_TREE_FIELD] ?? '').trim().toLowerCase()
  const knownProperties = new Set(
    Object.values(variableMap)
      .map((name) => name.trim().toLowerCase())
      .filter((name) => name !== ''),
  )
  const unknownProperties: string[] = []
  let selfReference = false
  for (const match of template.matchAll(PROPERTY_LINK)) {
    const name = match[1]!
    const key = name.toLowerCase()
    if (own && key === own) {
      selfReference = true
    } else if (!knownProperties.has(key) && !unknownProperties.includes(name)) {
      unknownProperties.push(name)
    }
  }
  return {
    controlCharacter: hasControlCharacter(template),
    tooLong: template.length > MAX_FEATURE_TREE_TEMPLATE_LENGTH,
    selfReference,
    unknownProperties,
  }
}

export function hasFeatureTreeTemplateError(validation: FeatureTreeTemplateValidation): boolean {
  return validation.controlCharacter || validation.tooLong || validation.selfReference
}
