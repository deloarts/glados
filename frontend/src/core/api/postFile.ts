/**
 * Single-file multipart upload through the typed web client. The file goes
 * into the `file` form field, which every upload route of the backend reads,
 * and optional string fields (a file category, for example) are appended
 * after it. The path and its path parameters are checked against the
 * generated schema like any other `webApi.post` call.
 */
import { webApi, type WebPath, type WebRequestOptions, type WebResponse } from './webRequest'

const MULTIPART_CONFIG = { headers: { 'Content-Type': 'multipart/form-data' } }

type UploadOptions<P extends WebPath<'post'>> = Omit<
  WebRequestOptions<P, 'post'>,
  'body' | 'config'
> & { fields?: Record<string, string> }

// Optional when the route takes no path parameters or query, so such an
// upload stays a two-argument call. A route without a multipart body accepts
// no arguments at all, which turns a wrong path into a compile error.
type UploadArgs<P extends WebPath<'post'>> =
  WebRequestOptions<P, 'post'> extends { body: FormData }
    ? Record<string, never> extends UploadOptions<P>
      ? [options?: UploadOptions<P>]
      : [options: UploadOptions<P>]
    : never

type UntypedPost = (path: string, options: object) => Promise<unknown>

export async function postFile<P extends WebPath<'post'>>(
  path: P,
  file: File,
  ...[options]: UploadArgs<P>
): Promise<WebResponse<P, 'post'>> {
  const { fields, ...request } = options ?? {}
  const formData = new FormData()
  formData.append('file', file)
  for (const [name, value] of Object.entries(fields ?? {})) formData.append(name, value)
  // The route's option type is still generic here, so the call goes through
  // the untyped signature; the caller's arguments were checked above.
  return (await (webApi.post as UntypedPost)(path, {
    ...request,
    body: formData,
    config: MULTIPART_CONFIG,
  })) as WebResponse<P, 'post'>
}
