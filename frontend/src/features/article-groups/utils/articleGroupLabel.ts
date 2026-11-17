import { localizeLabel } from '@/shared/utils/localizeLabel'
import type { LocalizedText } from '@/shared/utils/localizedText'

/** An article group's name in the current UI language, also usable as a Select option label. */
export function articleGroupLabel(entity: { name: LocalizedText | string }): string {
  return localizeLabel(entity.name)
}
