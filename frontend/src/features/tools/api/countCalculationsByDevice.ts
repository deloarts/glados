import { getCalculations } from './getCalculations'

/**
 * How many calculations of a product refer to each of its devices, by device
 * id. A device without one is left out of the map.
 */
export async function countCalculationsByDevice(productId: number): Promise<Map<number, number>> {
  const page = await getCalculations({ related_product_id: productId, limit: 500 })
  const counts = new Map<number, number>()
  for (const c of page.items) {
    if (c.product_device_id !== null) counts.set(c.product_device_id, (counts.get(c.product_device_id) ?? 0) + 1)
  }
  return counts
}
