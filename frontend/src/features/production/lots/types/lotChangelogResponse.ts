// The lot's own free-text changelog (GET /production-lots/{id}/changelog),
// same "timestamp, user, message" convention every other catalogue entity
// uses, so it reuses the shared parser.
export { parseChangelogEntry, type ChangelogEntry as LotChangelogEntry } from '@/shared/utils/changelog'
