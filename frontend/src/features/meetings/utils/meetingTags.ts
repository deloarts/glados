/**
 * The rules of a meeting's free-text tags as the browser applies them while
 * they are typed: the backend's normaliser does the same on save and refuses
 * a tag over TAG_MAX characters or more than TAGS_MAX tags.
 */

export const TAG_MAX = 40
export const TAGS_MAX = 10

/** The tag with case and spacing taken out, for comparing. */
export function tagKey(tag: string): string {
  return tag.split(/\s+/).filter(Boolean).join(' ').toLocaleLowerCase()
}

/**
 * The tags in the order given, each trimmed with its inner whitespace
 * collapsed, without empty ones and without repeats in another case, the
 * first spelling kept.
 */
export function normaliseTags(values: readonly string[]): string[] {
  const seen = new Set<string>()
  const tags: string[] = []
  for (const value of values) {
    const tag = value.split(/\s+/).filter(Boolean).join(' ')
    const key = tag.toLocaleLowerCase()
    if (!tag || seen.has(key)) continue
    seen.add(key)
    tags.push(tag)
  }
  return tags
}

/**
 * What the tag input offers for the typed text: the typed text itself first,
 * so Enter takes it as a new tag, unless a tag in use spells it already, then
 * the tags in use that contain it. Tags the meeting carries are left out.
 */
export function tagOptions(known: readonly string[], typed: string, selected: readonly string[]): string[] {
  const text = typed.split(/\s+/).filter(Boolean).join(' ')
  const query = tagKey(text)
  const taken = new Set(selected.map(tagKey))
  const matching = known.filter((tag) => !taken.has(tagKey(tag)) && tagKey(tag).includes(query))
  const exact = matching.find((tag) => tagKey(tag) === query)
  const rest = matching.filter((tag) => tag !== exact)
  if (!text || taken.has(query)) return rest
  return [exact ?? text, ...rest]
}
