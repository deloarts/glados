import type { MultiCategorySpec } from '@/shared/components/files/fileCategorySpec'

// Evidence is usually a photo of a gauge reading or a CMM report, so the one
// category takes both.
export const EVIDENCE_ACCEPT = 'application/pdf,image/*'

export const EVIDENCE_FILES: MultiCategorySpec[] = [
  {
    key: 'measurement_report',
    labelKey: 'productionQueue.completion.files.measurement_report',
    accent: 'teal',
    icon: 'mdi mdi-file-chart-outline',
    accept: EVIDENCE_ACCEPT,
  },
]
