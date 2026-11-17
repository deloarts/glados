import { webApi } from '@/core/api/webRequest'

import type {
  DisplayScheduleDefault,
  DisplayScheduleDefaultRequest,
  InfoscreenCreateRequest,
  InfoscreenResponse,
  InfoscreenLanguage,
  InfoscreenUpdateRequest,
  WeatherPlace,
} from '../types/infoscreenResponse'

export async function getInfoscreens(includeArchived: boolean): Promise<InfoscreenResponse[]> {
  return webApi.get('/infoscreens/', { query: { include_archived: includeArchived } })
}

export async function createInfoscreen(body: InfoscreenCreateRequest): Promise<InfoscreenResponse> {
  return webApi.post('/infoscreens/', { body })
}

export async function updateInfoscreen(
  infoscreenId: number,
  body: InfoscreenUpdateRequest,
): Promise<InfoscreenResponse> {
  return webApi.patch('/infoscreens/{infoscreen_id}', { path: { infoscreen_id: infoscreenId }, body })
}

export async function archiveInfoscreen(infoscreenId: number): Promise<InfoscreenResponse> {
  return webApi.post('/infoscreens/{infoscreen_id}/archive', { path: { infoscreen_id: infoscreenId } })
}

export async function restoreInfoscreen(infoscreenId: number): Promise<InfoscreenResponse> {
  return webApi.post('/infoscreens/{infoscreen_id}/restore', { path: { infoscreen_id: infoscreenId } })
}

/** The schedule every screen in the default mode follows. */
export async function getDisplayScheduleDefault(): Promise<DisplayScheduleDefault> {
  return webApi.get('/infoscreens/display-schedule-default')
}

export async function setDisplayScheduleDefault(
  body: DisplayScheduleDefaultRequest,
): Promise<DisplayScheduleDefault> {
  return webApi.put('/infoscreens/display-schedule-default', { body })
}

/** Towns named like `query` in the country, for the weather widget's location picker. */
export async function searchWeatherPlaces(
  query: string,
  country: string,
  language: InfoscreenLanguage,
): Promise<WeatherPlace[]> {
  return webApi.get('/infoscreens/weather-places', { query: { q: query, country, language } })
}
