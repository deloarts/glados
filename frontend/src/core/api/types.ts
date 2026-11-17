// eslint-disable-next-line no-restricted-syntax -- the generic page envelope, which every generated PageResponse_X_ satisfies
export interface PageResponse<T> {
  items: T[]
  total: number
  limit: number | null
  skip: number
}
