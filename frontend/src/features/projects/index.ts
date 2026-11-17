// Public barrel of the projects feature. Other features import through here
// (enforced by eslint). Export only what other features consume.

export { getProjects } from './api/getProjects'
export { getProjectChangelog } from './api/getProjectChangelog'
export { getProjectSummary } from './api/getProjectSummary'
export { projectStatusSeverity } from './utils/projectStatus'
export { default as ProjectBomTab } from './components/ProjectBomTab.vue'
export { default as ProjectContactsSection } from './components/ProjectContactsSection.vue'
export { default as ProjectFormDialog } from './components/ProjectFormDialog.vue'

export type { ProjectResponse, ProjectSummaryResponse } from './types/projectResponse'
export type { ProjectChangelogEntry } from './types/projectChangelogResponse'
