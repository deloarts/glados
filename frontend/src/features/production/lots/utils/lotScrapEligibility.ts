type LotScrapFields = {
  positions?: { kind: string }[]
}

// Scrap needs an internal or mixed position to book against.
export function hasInternalPosition(lot: LotScrapFields): boolean {
  return (lot.positions ?? []).some((p) => p.kind === 'internal' || p.kind === 'mixed')
}
