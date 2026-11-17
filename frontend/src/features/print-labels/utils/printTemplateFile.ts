import {
  TemplateFileError,
  optionalNumber,
  optionalString,
  requireNumber,
  requireString,
  requireStringMap,
  unknownKeys,
} from '@/shared/utils/templateFile'
import type { PrintTemplateResponse } from '../types/printTemplateResponse'

/**
 * The settings file of a print template: the classifier it belongs to and
 * every setting that travels between installs. The printer, auto print,
 * enabled and the note are left out, since they belong to the install. The
 * source travels as a file of its own.
 */

const SETTINGS_KEYS = [
  'classifier',
  'trigger',
  'paper',
  'design_dpi',
  'label_width_mm',
  'label_height_mm',
  'copies_rule',
  'copies_fixed',
  'max_copies',
  'field_map',
]

/** The editor's form values a settings file sets, named as the form names them. */
export interface PrintTemplateFileSettings {
  trigger: PrintTemplateResponse['trigger']
  paper: string
  designDpi: number | null
  labelWidthMm: number | null
  labelHeightMm: number | null
  copiesRule: string
  copiesFixed: number
  maxCopies: number
  fieldMap: Record<string, string>
}

/**
 * The form values a settings file sets for `template`, and the keys it
 * ignored. A file for another classifier is refused. A trigger, paper or
 * copies rule the template does not offer is ignored rather than refused,
 * so the rest of the file still applies.
 */
export function printTemplateSettingsPatch(
  template: PrintTemplateResponse,
  content: Record<string, unknown>,
  hasPaper: boolean,
): { patch: Partial<PrintTemplateFileSettings>; ignored: string[] } {
  const classifier = requireString(content, 'classifier')
  if (classifier !== template.classifier) throw new TemplateFileError('wrongTarget', classifier)
  const patch: Partial<PrintTemplateFileSettings> = {}
  const ignored = unknownKeys(content, SETTINGS_KEYS)
  if ('trigger' in content) {
    const trigger = optionalString(content, 'trigger')
    if (trigger === null || (template.available_triggers as string[]).includes(trigger)) {
      patch.trigger = trigger as PrintTemplateFileSettings['trigger']
    } else {
      ignored.push('trigger')
    }
  }
  if ('paper' in content) {
    const paper = optionalString(content, 'paper')
    if (hasPaper && paper) patch.paper = paper
    else if (paper) ignored.push('paper')
  }
  if ('design_dpi' in content) patch.designDpi = optionalNumber(content, 'design_dpi')
  if ('label_width_mm' in content) patch.labelWidthMm = optionalNumber(content, 'label_width_mm')
  if ('label_height_mm' in content) patch.labelHeightMm = optionalNumber(content, 'label_height_mm')
  if ('copies_rule' in content) {
    const rule = requireString(content, 'copies_rule')
    if (template.copies_rules.includes(rule)) patch.copiesRule = rule
    else ignored.push('copies_rule')
  }
  if ('copies_fixed' in content) patch.copiesFixed = requireNumber(content, 'copies_fixed')
  if ('max_copies' in content) patch.maxCopies = requireNumber(content, 'max_copies')
  if ('field_map' in content) patch.fieldMap = { ...requireStringMap(content, 'field_map') }
  return { patch, ignored }
}

/** The content of a settings file for `classifier`, leaving out unset values. */
export function printTemplateSettingsContent(
  classifier: string,
  settings: PrintTemplateFileSettings,
  hasPaper: boolean,
): Record<string, unknown> {
  const content: Record<string, unknown> = {
    classifier,
    trigger: settings.trigger,
    ...(hasPaper ? { paper: settings.paper } : {}),
    design_dpi: settings.designDpi,
    label_width_mm: settings.labelWidthMm,
    label_height_mm: settings.labelHeightMm,
    copies_rule: settings.copiesRule,
    copies_fixed: settings.copiesFixed,
    max_copies: settings.maxCopies,
    field_map: settings.fieldMap,
  }
  return Object.fromEntries(Object.entries(content).filter(([, value]) => value !== null))
}
