import type {
  FabricationMadeItemProcess,
  InspectionMadeItemProcess,
  MadeItemProcessResponse,
} from '../types/madeItemsResponse'
import { localizeLabel } from '@/shared/utils/localizeLabel'

// A contiguous run of routing steps sharing one group_index. A group becomes
// one lot position when a lot is created from this routing.
export interface MadeItemProcessGroup {
  groupIndex: number
  processes: MadeItemProcessResponse[]
}

export function sortedProcesses(
  processes: MadeItemProcessResponse[] | undefined,
): MadeItemProcessResponse[] {
  return [...(processes ?? [])].sort((a, b) => a.position - b.position)
}

export function processGroups(
  processes: MadeItemProcessResponse[] | undefined,
): MadeItemProcessGroup[] {
  const groups: MadeItemProcessGroup[] = []
  for (const process of sortedProcesses(processes)) {
    const last = groups[groups.length - 1]
    if (last && last.groupIndex === process.group_index) {
      last.processes.push(process)
    } else {
      groups.push({ groupIndex: process.group_index, processes: [process] })
    }
  }
  return groups
}

// Maps the app locale code to a BCP-47 tag for Intl.
function bcp47LocaleTag(locale: string): string {
  return locale === 'deAT' ? 'de-AT' : 'en-GB'
}

// The process's method name, from the inspection method for an inspection
// process. Spelled out per variant because Pick does not distribute over the
// union.
type MethodNamedProcess =
  | Pick<
      FabricationMadeItemProcess,
      'role' | 'inspection_method_name' | 'fabrication_method_name'
    >
  | Pick<InspectionMadeItemProcess, 'role' | 'inspection_method_name' | 'fabrication_method_name'>

export function processMethodLabel(process: MethodNamedProcess): string {
  if (process.role === 'inspection') return localizeLabel(process.inspection_method_name)
  return localizeLabel(process.fabrication_method_name)
}

// Multi-step groups join their method labels with a localized conjunction.
export function groupMethodLabel(
  group: MadeItemProcessGroup,
  locale: string,
): string {
  if (group.processes.length === 1) return processMethodLabel(group.processes[0]!)
  return new Intl.ListFormat(bcp47LocaleTag(locale), { type: 'conjunction' }).format(
    group.processes.map((p) => processMethodLabel(p)),
  )
}

export function processRoutingLabel(
  processes: MadeItemProcessResponse[] | undefined,
  locale: string,
): string {
  return processGroups(processes)
    .map((group) => groupMethodLabel(group, locale))
    .join(' → ')
}
