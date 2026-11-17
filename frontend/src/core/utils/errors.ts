import axios from 'axios'

// FastAPI's own shape for a 422 request-validation failure: `detail` is an
// array here instead of the string every other error response uses.
// `loc` is [location kind ('body'/'query'/'path'/'header'), ...field path],
// e.g. ["body", "items", 0, "quantity"].
interface FastApiValidationError {
  loc: (string | number)[]
  msg: string
}

function isValidationError(value: unknown): value is FastApiValidationError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'msg' in value &&
    typeof (value as { msg: unknown }).msg === 'string' &&
    Array.isArray((value as { loc?: unknown }).loc)
  )
}

/**
 * The field path alone, e.g. "items.0.quantity": the leading location kind
 * (body/query/...) is implementation detail, not something a user placed.
 */
function fieldPath(err: FastApiValidationError): string {
  return err.loc.slice(1).join('.')
}

export function extractApiError(e: unknown): string | null {
  if (!axios.isAxiosError(e)) return null
  const detail: unknown = e.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail) && detail.length > 0 && isValidationError(detail[0])) {
    const first = detail[0]
    const path = fieldPath(first)
    return path ? `${path}: ${first.msg}` : first.msg
  }

  return null
}

/**
 * The domain error class name the backend sends as `code` next to `detail`
 * (for example "TimeTrackingRateLimitedError"), so callers can show a
 * translated message instead of the English detail. Null for anything that
 * is not an API error with a string code.
 */
export function extractApiErrorCode(e: unknown): string | null {
  if (!axios.isAxiosError(e)) return null
  const code: unknown = e.response?.data?.code
  return typeof code === 'string' ? code : null
}

/**
 * The HTTP status of an API error response, null for anything that is not
 * an axios error carrying a response.
 */
export function apiErrorStatus(e: unknown): number | null {
  if (!axios.isAxiosError(e)) return null
  return e.response?.status ?? null
}
