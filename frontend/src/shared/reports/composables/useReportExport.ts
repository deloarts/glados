import { ref, shallowRef } from 'vue'

import type { ReportSpec } from '../types'

/**
 * State of a page's report export dialog: `open(spec)` shows it for that
 * report. The page renders `<ReportExportDialog v-model:visible="visible"
 * :report="report" />` once.
 */
export function useReportExport() {
  const visible = ref(false)
  const report = shallowRef<ReportSpec | null>(null)

  function open(spec: ReportSpec): void {
    report.value = spec
    visible.value = true
  }

  return { visible, report, open }
}
