/**
 * Reads an aggregate's changelog. Every changelog route returns its lines as
 * plain "timestamp, username, message" strings, which are parsed into entries
 * here so the per-feature modules only name their route.
 */
import { webApi, type OptionsArg, type WebPath } from '@/core/api/webRequest'
import { parseChangelogEntry, type ChangelogEntry } from '@/shared/utils/changelog'

type UntypedGet = (path: string, ...options: unknown[]) => Promise<unknown>

export async function getChangelog<P extends WebPath<'get'> & `${string}/changelog`>(
  path: P,
  ...options: OptionsArg<P, 'get'>
): Promise<ChangelogEntry[]> {
  // Forwarding the generic options straight into `webApi.get` is too large a
  // union for the compiler, so the call goes through the untyped signature;
  // the caller's path and options were checked above.
  const lines = (await (webApi.get as UntypedGet)(path, ...options)) as string[]
  return lines.map(parseChangelogEntry)
}
