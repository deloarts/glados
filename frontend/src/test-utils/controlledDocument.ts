/**
 * The document control fields every calculation and checklist response
 * carries, as a first revision that is a draft nobody is editing. Spread
 * them first into a fixture, so the fields a spec cares about override
 * them.
 */
export function controlledDocumentFields() {
  return {
    document_number: 'CAL-26-0001',
    lineage: '00000000-0000-4000-8000-0000000000aa',
    revision: 'A',
    revision_reason: null,
    is_latest: true,
    superseded_at: null,
    read_only: false,
    changed_by_id: null,
    changed_by_full_name: null,
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    invalid_at: null,
    invalid_by_id: null,
    invalid_by_full_name: null,
    invalid_reason: null,
    locked_by_id: null,
    locked_by_full_name: null,
    locked_at: null,
    lock_expires_at: null,
  }
}
