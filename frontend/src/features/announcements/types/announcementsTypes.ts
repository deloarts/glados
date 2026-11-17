import type { Schemas } from '@/core/api/generated'

export type AnnouncementSeverity = Schemas['AnnouncementSeverity']

/**
 * null when disabled or blank. The client evaluates the show window, so
 * both bounds arrive raw.
 */
export type AnnouncementBanner = Schemas['MyAnnouncementsBannerResult']

/**
 * Oldest first, already filtered on the server to what this user still
 * has to confirm.
 */
export type PendingAcknowledgement = Schemas['PendingAcknowledgementResult']

export type MyAnnouncementsResponse = Schemas['MyAnnouncementsResult']
