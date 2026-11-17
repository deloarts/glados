import { webApi } from '@/core/api/webRequest'

import type { Schemas } from '@/core/api/generated'

/** A contact of the project: one of its own or inherited from its product. */
export type ProjectContactResponse = Schemas['ProjectContactResponse']

/** Every call answers the project's contacts as they are afterwards. */
export async function getProjectContacts(projectId: number): Promise<ProjectContactResponse[]> {
  return webApi.get('/projects/{project_id}/contacts', { path: { project_id: projectId } })
}

export async function linkProjectContact(
  projectId: number,
  contactId: number,
  receivesMeetingNotes: boolean,
): Promise<ProjectContactResponse[]> {
  return webApi.post('/projects/{project_id}/contacts', {
    path: { project_id: projectId },
    body: { contact_id: contactId, receives_meeting_notes: receivesMeetingNotes },
  })
}

/** Also for an inherited contact, which is how the project mutes one for itself. */
export async function setProjectContactMeetingNotes(
  projectId: number,
  contactId: number,
  receivesMeetingNotes: boolean,
): Promise<ProjectContactResponse[]> {
  return webApi.put('/projects/{project_id}/contacts/{contact_id}', {
    path: { project_id: projectId, contact_id: contactId },
    body: { receives_meeting_notes: receivesMeetingNotes },
  })
}

export async function unlinkProjectContact(
  projectId: number,
  contactId: number,
): Promise<ProjectContactResponse[]> {
  return webApi.delete('/projects/{project_id}/contacts/{contact_id}', {
    path: { project_id: projectId, contact_id: contactId },
  })
}
