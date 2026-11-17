// Public barrel of the announcements feature. Other code imports through
// here (enforced by eslint).

export { useAnnouncementsStore } from './stores/announcementsStore'
export { toMessageSeverity, toSeverityIcon } from './utils/severity'

export type { AnnouncementBanner, AnnouncementSeverity } from './types/announcementsTypes'

export { default as AcknowledgementDialog } from './components/AcknowledgementDialog.vue'
export { default as AnnouncementsHandler } from './components/AnnouncementsHandler.vue'
