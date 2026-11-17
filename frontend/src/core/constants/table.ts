export const TABLE_DEFAULT_ROWS = 25
export const TABLE_ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100]
export const TABLE_DEBOUNCE_MS = 400
export const SEARCH_DEBOUNCE_MS = 300

/**
 * The largest `limit` any list endpoint accepts. Mirrors MAX_PAGE_SIZE in
 * the backend's src/modules/platform/const.py, which rejects anything higher with a 422.
 * For views that render a whole list with no paginator, this is the most
 * they can ask for.
 */
export const API_MAX_PAGE_SIZE = 500

export const TABLE_COL_WIDTH_ID = '7rem'
export const TABLE_COL_WIDTH_STATUS = '9rem'
export const TABLE_COL_WIDTH_REVISION = '6rem'
