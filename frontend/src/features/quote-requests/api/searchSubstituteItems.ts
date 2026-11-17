import { webApi } from '@/core/api/webRequest'
import { localizeLabel } from '@/shared/utils/localizeLabel'

/** A catalogue item a quote request line can take instead of its own. */
export interface SubstituteItemOption {
  id: number
  name: string
  code: string
}

const SEARCH_LIMIT = 50

/**
 * Searches the catalogue a substitute for a line comes from: bought items
 * for a bought line, source items for a source line. Archived items are
 * left out, since new work cannot name them.
 */
export async function searchSubstituteItems(
  kind: 'BOUGHT' | 'SOURCE',
  query: string,
): Promise<SubstituteItemOption[]> {
  const search = query.trim() || undefined
  if (kind === 'BOUGHT') {
    const page = await webApi.get('/bought-items/', { query: { limit: SEARCH_LIMIT, search } })
    return page.items.map((item) => ({
      id: item.id,
      name: item.article_name,
      code: [item.order_code_1, item.manufacturer_name].filter(Boolean).join(' · '),
    }))
  }
  const page = await webApi.get('/source-items', { query: { limit: SEARCH_LIMIT, search } })
  return page.items.map((item) => ({
    id: item.id,
    name: item.dimension || `#${item.id}`,
    code: item.order_code_1 || [item.material, localizeLabel(item.type_name)].filter(Boolean).join(' | '),
  }))
}
