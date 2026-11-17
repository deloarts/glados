import type {
  ChecklistOwner,
  ChecklistStatus,
  ChecklistSummaryResponse,
} from '../types/checklist'

export function ownerOf(checklist: ChecklistSummaryResponse): ChecklistOwner {
  if (checklist.project_id !== null) {
    return { kind: 'project', id: checklist.project_id, label: checklist.project_number ?? '' }
  }
  if (checklist.product_id !== null) {
    return { kind: 'product', id: checklist.product_id, label: checklist.product_number ?? '' }
  }
  return { kind: 'personal' }
}

export function ownerIds(owner: ChecklistOwner): { project_id: number | null; product_id: number | null } {
  return {
    project_id: owner.kind === 'project' ? owner.id : null,
    product_id: owner.kind === 'product' ? owner.id : null,
  }
}

/** The page of the project or product a checklist belongs to, null for a personal one. */
export function ownerLink(owner: ChecklistOwner): string | null {
  if (owner.kind === 'project') return `/workspace/projects/${owner.id}`
  if (owner.kind === 'product') return `/workspace/products/${owner.id}`
  return null
}

export function checklistStatus(checklist: ChecklistSummaryResponse): ChecklistStatus {
  if (checklist.superseded_at !== null) return 'superseded'
  if (checklist.released_at !== null) return 'released'
  if (checklist.finished) return 'done'
  return 'draft'
}

export const STATUS_SEVERITY: Record<ChecklistStatus, 'secondary' | 'success' | 'info' | 'warn'> = {
  draft: 'secondary',
  done: 'info',
  released: 'success',
  superseded: 'warn',
}

export const VERDICT_SEVERITY = {
  open: 'secondary',
  passed: 'success',
  failed: 'danger',
} as const

/** Whole percent of answered items, rounded down so 100 means complete. */
export function completionOf(checklist: Pick<ChecklistSummaryResponse, 'answered_count' | 'item_count'>): number {
  return checklist.item_count === 0 ? 100 : Math.floor((checklist.answered_count / checklist.item_count) * 100)
}
