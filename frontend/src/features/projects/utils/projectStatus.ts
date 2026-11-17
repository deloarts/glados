import type { ProjectStatus } from '@/features/projects/types/projectResponse'

export const PROJECT_STATUSES: ProjectStatus[] = ['active', 'on_hold', 'completed', 'archived']

export const projectStatusSeverity: Record<ProjectStatus, string> = {
  active: 'success',
  on_hold: 'warn',
  completed: 'info',
  archived: 'secondary',
}
