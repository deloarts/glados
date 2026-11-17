import { webApi } from '@/core/api/webRequest'
import type { MyAnnouncementsResponse } from '../types/announcementsTypes'

export async function getMyAnnouncements(): Promise<MyAnnouncementsResponse> {
  return webApi.get('/announcements/me')
}
