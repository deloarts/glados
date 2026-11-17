import axios from 'axios'

import type { OpenApiSpec } from '../types/openApiTypes'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

/**
 * Tag-filtered OpenAPI schema for the API-key surface. The backend serves it
 * to a signed-in session only, and, unlike its `/docs/key` Swagger UI page,
 * it sits under `/api/` so nginx proxies it in production too.
 */
export const API_KEY_OPENAPI_URL = `${API_ROOT}/api/v1/key/openapi.json`

/** Origin the documented endpoints are called against, same origin in production. */
export const API_KEY_BASE_URL = API_ROOT || window.location.origin

export async function getApiKeyOpenApiSpec(): Promise<OpenApiSpec> {
  // The session cookie must travel along when VITE_API_URL points at
  // another origin in development.
  const { data } = await axios.get<OpenApiSpec>(API_KEY_OPENAPI_URL, { withCredentials: true })
  return data
}
