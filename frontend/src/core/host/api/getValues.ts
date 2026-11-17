import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

/**
 * The closed value lists the settings forms offer. timezones holds the IANA
 * names of the server's tz database, a long list rather than an enum.
 */
export type HostValues = Schemas['ValuesResponse']

export async function getValues(): Promise<HostValues> {
  return webApi.get('/host/values')
}
