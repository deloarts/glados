/**
 * Typed request helper for the web API surface, keyed by the generated
 * `paths` map. A call names the route by its schema path template
 * (`/bought-items-demands/{demand_id}`), and the compiler checks that the
 * route exists for that method, that every path parameter is supplied, and
 * that the query and JSON body match the backend's OpenAPI schema. A renamed
 * or removed backend route therefore fails `npm run type-check` instead of
 * failing at runtime.
 *
 * Requests still go through the shared axios instance, so the CSRF header,
 * credentials, query serializer and response interceptors (connectivity,
 * session expiry, maintenance lockout) all apply unchanged.
 *
 * The generated file is imported directly here, rather than through
 * `./generated/index.ts`, because only the component schemas are re-exported
 * there and this module is the one place that needs `paths`.
 */
import type { AxiosRequestConfig } from 'axios'

import api from './index'
import type { paths } from './generated/webSchema'

type WebPrefix = '/api/v1/web'
type HttpMethod = 'get' | 'post' | 'put' | 'patch' | 'delete'

type SchemaKey = Extract<keyof paths, `${WebPrefix}/${string}`>

type WithoutPrefix<K> = K extends `${WebPrefix}${infer Rest}` ? Rest : never

// FastAPI declares collection routes with a trailing slash, while most call
// sites send them without one; both spellings are accepted and the URL is
// sent exactly as written.
type WithoutTrailingSlash<P> = P extends `${infer Rest}/` ? (Rest extends '' ? P : Rest) : P

type IsNever<T> = [T] extends [never] ? true : false

/** Every web path, relative to the axios base URL, that supports method M. */
export type WebPath<M extends HttpMethod> = {
  [K in SchemaKey]: IsNever<NonNullable<paths[K][M]>> extends true
    ? never
    : WithoutPrefix<K> | WithoutTrailingSlash<WithoutPrefix<K>>
}[SchemaKey]

type SchemaKeyOf<P> = P extends string
  ? `${WebPrefix}${P}` extends SchemaKey
    ? `${WebPrefix}${P}`
    : `${WebPrefix}${P}/` extends SchemaKey
      ? `${WebPrefix}${P}/`
      : never
  : never

type Operation<P extends string, M extends HttpMethod> = NonNullable<paths[SchemaKeyOf<P>][M]>

type PathParamsOf<Op> = Op extends { parameters: { path: infer Params } } ? Params : never

type OperationQuery<Op> = Op extends { parameters: { query?: infer Query } }
  ? NonNullable<Query>
  : never

type HasRequiredQuery<Op> = Op extends { parameters: { query: object } } ? true : false

// The generator marks every pydantic field that has a default as required,
// so required-ness of body fields cannot be trusted. Field names and value
// types are still checked; only the "required" flag is relaxed, also on the
// nested objects and array elements a body carries (a made item's processes,
// whose `role` defaults on the backend, for one).
type LooseBody<T> = T extends readonly (infer Item)[]
  ? LooseBody<Item>[]
  : T extends object
    ? { [K in keyof T]?: LooseBody<T[K]> }
    : T

type BodyOf<Op> = Op extends { requestBody?: { content: infer Content } }
  ? Content extends { 'application/json': infer Json }
    ? LooseBody<Json>
    : Content extends { 'multipart/form-data': unknown }
      ? FormData
      : never
  : never

type JsonContent<C> = C extends { 'application/json': infer Json } ? Json : unknown

type ResponseOf<Op> = Op extends { responses: infer Responses }
  ? Responses extends { 200: { content: infer C } }
    ? JsonContent<C>
    : Responses extends { 201: { content: infer C } }
      ? JsonContent<C>
      : Responses extends { 202: { content: infer C } }
        ? JsonContent<C>
        : void
  : never

/** Extra axios options; url, method, query and body come from the typed fields. */
export type WebRequestConfig = Omit<AxiosRequestConfig, 'url' | 'method' | 'params' | 'data'>

type PathOption<Op> =
  IsNever<PathParamsOf<Op>> extends true ? { path?: never } : { path: PathParamsOf<Op> }

type QueryOption<Op> =
  IsNever<OperationQuery<Op>> extends true
    ? { query?: never }
    : HasRequiredQuery<Op> extends true
      ? { query: OperationQuery<Op> }
      : { query?: OperationQuery<Op> }

// A route without a request body still accepts an explicit `null`, which
// some call sites send on a bodiless PUT.
type BodyOption<Op> =
  IsNever<BodyOf<Op>> extends true ? { body?: null } : { body: BodyOf<Op> }

export type WebRequestOptions<P extends string, M extends HttpMethod> = PathOption<
  Operation<P, M>
> &
  QueryOption<Operation<P, M>> &
  BodyOption<Operation<P, M>> & { config?: WebRequestConfig }

export type WebResponse<P extends string, M extends HttpMethod> = ResponseOf<Operation<P, M>>

/**
 * The generated query parameters of a route, keyed like a `webApi` call
 * (`QueryOf<'/customers'>`, or `QueryOf<'/x', 'post'>` for another method).
 * List filter types alias this instead of restating the backend's query
 * model, so a renamed or removed parameter fails `npm run type-check`.
 */
export type QueryOf<P extends WebPath<M>, M extends HttpMethod = 'get'> = OperationQuery<
  Operation<P, M>
>

// Optional when the route takes no path params, required query or body, so
// a plain `webApi.get('/foo')` stays a one-liner.
export type OptionsArg<P extends string, M extends HttpMethod> =
  Record<string, never> extends WebRequestOptions<P, M>
    ? [options?: WebRequestOptions<P, M>]
    : [options: WebRequestOptions<P, M>]

/** Substitutes `{name}` placeholders in a schema path template. */
export function buildWebUrl(template: string, params?: Record<string, unknown>): string {
  return template.replace(/\{([^}]+)\}/g, (_match, name: string) => {
    const value = params?.[name]
    if (value === undefined || value === null) {
      throw new Error(`Missing path parameter "${name}" for ${template}`)
    }
    return encodeURIComponent(String(value))
  })
}

interface UntypedOptions {
  path?: Record<string, unknown>
  query?: unknown
  body?: unknown
  config?: WebRequestConfig
}

// Builds the axios config only when there is something to put in it, so the
// call reaches axios in the same shape a hand-written `api.get(url)` would.
function axiosConfig(options: UntypedOptions): AxiosRequestConfig | undefined {
  if (options.query === undefined && options.config === undefined) return undefined
  return { ...options.config, ...(options.query !== undefined && { params: options.query }) }
}

// axios takes no body argument on a DELETE, so a route that reads a JSON
// body there (disabling TOTP, for one) gets it as the config's `data`.
function deleteConfig(options: UntypedOptions): AxiosRequestConfig | undefined {
  const config = axiosConfig(options)
  if (options.body === undefined || options.body === null) return config
  return { ...config, data: options.body }
}

async function send(method: HttpMethod, template: string, options: UntypedOptions = {}) {
  const url = buildWebUrl(template, options.path)
  const config = method === 'delete' ? deleteConfig(options) : axiosConfig(options)
  const configArgs = config === undefined ? [] : [config]
  switch (method) {
    case 'get':
      return (await api.get(url, ...configArgs)).data
    case 'delete':
      return (await api.delete(url, ...configArgs)).data
    case 'post':
      return (await api.post(url, options.body, ...configArgs)).data
    case 'put':
      return (await api.put(url, options.body, ...configArgs)).data
    case 'patch':
      return (await api.patch(url, options.body, ...configArgs)).data
  }
}

function method<M extends HttpMethod>(m: M) {
  return <P extends WebPath<M>>(
    path: P,
    ...[options]: OptionsArg<P, M>
  ): Promise<WebResponse<P, M>> =>
    send(m, path, options as UntypedOptions) as Promise<WebResponse<P, M>>
}

/**
 * Schema-checked counterparts of `api.get/post/put/patch/delete`, resolving
 * to the response body instead of the axios response.
 */
export const webApi = {
  get: method('get'),
  post: method('post'),
  put: method('put'),
  patch: method('patch'),
  delete: method('delete'),
}
