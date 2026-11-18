/**
 * Fails on a high or critical advisory in the production dependencies, unless
 * audit-allowlist.json accepts it.
 *
 * npm audit cannot accept a single advisory, and an advisory can have no fixed
 * release at all, which would block every pull request until one ships. An
 * entry names the advisory by its GHSA id, says why it cannot be exploited
 * here and carries a date by which it is looked at again. After that date the
 * entry no longer counts, so an accepted advisory is not forgotten. An entry
 * whose advisory npm no longer reports is listed for removal.
 *
 * Run: npm run check:audit
 */
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

interface AllowlistEntry {
  package: string
  reason: string
  reviewBy: string
}

interface Advisory {
  name: string
  title: string
  severity: string
  url: string
}

interface AuditReport {
  message?: string
  error?: { summary?: string }
  vulnerabilities?: Record<string, { via: (string | Advisory)[] }>
}

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const BLOCKING = new Set(['high', 'critical'])
const DATE = /^\d{4}-\d{2}-\d{2}$/

const allowlist = JSON.parse(
  readFileSync(new URL('../audit-allowlist.json', import.meta.url), 'utf8'),
) as Record<string, AllowlistEntry>

const malformed = Object.entries(allowlist).filter(
  ([, entry]) => !entry.reason?.trim() || !DATE.test(entry.reviewBy ?? ''),
)
if (malformed.length > 0) {
  console.error('audit-allowlist.json entries need a reason and a reviewBy date (YYYY-MM-DD):')
  for (const [id] of malformed) console.error(`  ${id}`)
  process.exit(1)
}

// npm audit exits non-zero whenever it finds anything, so the report is read
// from its output and only an unreadable report or an npm error fails here.
const audit = spawnSync('npm', ['audit', '--omit=dev', '--json'], { cwd: ROOT, encoding: 'utf8' })
let report: AuditReport
try {
  report = JSON.parse(audit.stdout) as AuditReport
} catch {
  console.error('npm audit returned no readable report:')
  console.error(audit.stderr)
  process.exit(1)
}
if (report.error) {
  const reason = report.message || report.error.summary || JSON.stringify(report.error)
  console.error(`npm audit failed: ${reason}`)
  process.exit(1)
}

// The same advisory is reported once per package that depends on it, so it
// is collected by its GHSA id.
const advisories = new Map<string, Advisory>()
for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
  for (const via of vulnerability.via) {
    if (typeof via === 'string') continue
    advisories.set(via.url.split('/').pop()!, via)
  }
}

const today = new Date().toISOString().slice(0, 10)
const accepted: string[] = []
const failing: string[] = []

for (const [id, advisory] of advisories) {
  if (!BLOCKING.has(advisory.severity)) continue
  const line = `${id} (${advisory.severity}) in ${advisory.name}: ${advisory.title}, ${advisory.url}`
  const entry = allowlist[id]
  if (!entry) failing.push(line)
  else if (entry.reviewBy < today) failing.push(`${line}\n    accepted until ${entry.reviewBy}, review it again`)
  else accepted.push(`${line}\n    accepted until ${entry.reviewBy}: ${entry.reason}`)
}

const stale = Object.keys(allowlist).filter((id) => !advisories.has(id))

if (accepted.length > 0) {
  console.log('Accepted by audit-allowlist.json:')
  for (const line of accepted) console.log(`  ${line}`)
}
if (stale.length > 0) {
  console.log('audit-allowlist.json entries npm no longer reports; remove them:')
  for (const id of stale) console.log(`  ${id}`)
}
if (failing.length > 0) {
  console.error('High or critical advisories in the production dependencies:')
  for (const line of failing) console.error(`  ${line}`)
  process.exit(1)
}

console.log(`Production audit OK: ${accepted.length} accepted, none failing.`)
