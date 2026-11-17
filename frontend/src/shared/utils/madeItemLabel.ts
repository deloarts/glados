// A made item is identified by part number and revision, and the combined
// label is what every render site shows. The catalogue's separate revision
// column is the deliberate exception.
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useHostStore } from '@/core/host/stores/hostStore'

/**
 * The label shown for a made item. A missing part number falls back to the
 * empty placeholder, and an empty revision returns the part number alone.
 */
export function formatMadeItemNumber(
  partNumber: string | null | undefined,
  revision: string | null | undefined,
  separator: string,
): string {
  const pn = partNumber ?? getEmptyPlaceholder()
  if (!revision) return pn
  return `${pn}${separator}${revision}`
}

/** formatMadeItemNumber bound to the configured revision separator. */
export function useMadeItemLabel() {
  const hostStore = useHostStore()

  function format(partNumber: string | null | undefined, revision: string | null | undefined): string {
    return formatMadeItemNumber(partNumber, revision, hostStore.madeItemPartNumbers.revision.separator)
  }

  return { format }
}
