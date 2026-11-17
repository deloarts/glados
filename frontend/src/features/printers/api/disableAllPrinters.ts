import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { getPrinters } from './getPrinters'
import { updatePrinter } from './updatePrinter'

/**
 * A panic button that disables every printer of any kind. Returns how many
 * changed, for the confirmation toast.
 */
export async function disableAllPrinters(): Promise<number> {
  const { items } = await getPrinters({ limit: API_MAX_PAGE_SIZE })
  const enabled = items.filter((p) => p.enabled)
  await Promise.all(enabled.map((p) => updatePrinter(p.id, { enabled: false })))
  return enabled.length
}
