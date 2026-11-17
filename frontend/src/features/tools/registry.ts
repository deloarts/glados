import type { Component } from 'vue'

import type { ReportOption } from '@/shared/reports'
import { asyncTab } from '@/shared/utils/asyncTab'
import type { ToolReportBuilder } from './utils/toolReport'
import { summarizeFit, summarizeGeneralTolerances, summarizeThreads } from './utils/toolSummaries'
import type { Summarizer } from './utils/toolSummaries'
import {
  DRIVE_SIZING_ENGINE_VERSION,
  DRIVE_SIZING_INPUT_VERSION,
  summarizeDriveSizing,
} from './utils/driveSizing'
import {
  SAFETY_DISTANCE_ENGINE_VERSION,
  SAFETY_DISTANCE_INPUT_VERSION,
  summarizeSafetyDistance,
} from './utils/safetyDistance'

/**
 * A tab of /tools or /tables. `key` is what a saved calculation stores as its
 * tool, `tab` the route segment. Raise `engineVersion` when a change alters
 * what the tool calculates for the same inputs, and `inputVersion` when the
 * shape of its saved inputs changes, so saved calculations can tell.
 */
export interface ToolDefinition {
  key: string
  tab: string
  labelKey: string
  icon: string
  inputVersion: number
  engineVersion: number
  component: Component
  summarize: Summarizer
  /**
   * Whether results of this tool are kept as saved calculations. The fit
   * calculator and the reference tables are looked up, not saved.
   */
  saveable: boolean
  /**
   * Loads the tool's PDF report body. A tool without one prints the
   * browser page instead.
   */
  report?: () => Promise<ToolReportBuilder>
  /** Checkboxes the export dialog offers for the tool's report. */
  reportOptions?: readonly ReportOption[]
}

export const TOOLS: readonly ToolDefinition[] = [
  {
    key: 'fit_calculator',
    tab: 'fit-calculator',
    labelKey: 'tools.tabs.fitCalculator',
    icon: 'mdi-diameter-variant',
    inputVersion: 1,
    engineVersion: 1,
    component: asyncTab(() => import('./components/FitCalculatorTab.vue')),
    summarize: summarizeFit,
    saveable: false,
  },
  {
    key: 'drive_sizing',
    tab: 'drive-sizing',
    labelKey: 'tools.tabs.driveSizing',
    icon: 'mdi-axis-arrow',
    inputVersion: DRIVE_SIZING_INPUT_VERSION,
    engineVersion: DRIVE_SIZING_ENGINE_VERSION,
    component: asyncTab(() => import('./components/DriveSizingTab.vue')),
    summarize: summarizeDriveSizing,
    saveable: true,
    report: () => import('./utils/driveSizing/report').then((module) => module.driveSizingReport),
  },
  {
    key: 'safety_distance',
    tab: 'safety-distance',
    labelKey: 'tools.tabs.safetyDistance',
    icon: 'mdi-shield-half-full',
    inputVersion: SAFETY_DISTANCE_INPUT_VERSION,
    engineVersion: SAFETY_DISTANCE_ENGINE_VERSION,
    component: asyncTab(() => import('./components/SafetyDistanceTab.vue')),
    summarize: summarizeSafetyDistance,
    saveable: true,
    report: () => import('./utils/safetyDistance/report').then((module) => module.safetyDistanceReport),
    reportOptions: [{ key: 'appendix', labelKey: 'tools.safetyDistance.report.appendixOption' }],
  },
]

/**
 * The reference tables under /tables: values that are looked up rather than
 * calculated and saved, kept apart from the tools.
 */
export const TABLES: readonly ToolDefinition[] = [
  {
    key: 'general_tolerances',
    tab: 'general-tolerances',
    labelKey: 'tools.tabs.generalTolerances',
    icon: 'mdi-ruler',
    inputVersion: 1,
    engineVersion: 1,
    component: asyncTab(() => import('./components/GeneralTolerancesTab.vue')),
    summarize: summarizeGeneralTolerances,
    saveable: false,
  },
  {
    key: 'threads',
    tab: 'threads',
    labelKey: 'tools.tabs.threads',
    icon: 'mdi-screw-flat-top',
    inputVersion: 1,
    engineVersion: 1,
    component: asyncTab(() => import('./components/ThreadsTab.vue')),
    summarize: summarizeThreads,
    saveable: false,
  },
]

/** The tools whose results can be saved, offered wherever a calculation is started. */
export const SAVEABLE_TOOLS: readonly ToolDefinition[] = TOOLS.filter((tool) => tool.saveable)

export function toolByKey(key: string): ToolDefinition | undefined {
  return TOOLS.find((tool) => tool.key === key)
}

export function toolByTab(tab: string): ToolDefinition | undefined {
  return TOOLS.find((tool) => tool.tab === tab)
}
