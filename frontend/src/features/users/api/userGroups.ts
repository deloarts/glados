import { webApi } from '@/core/api/webRequest'

import type { SaveUserGroupRequest, UserGroupResponse } from '../types/userGroup'

export async function getUserGroups(): Promise<UserGroupResponse[]> {
  return webApi.get('/user-groups/')
}

export async function createUserGroup(payload: SaveUserGroupRequest): Promise<UserGroupResponse> {
  return webApi.post('/user-groups/', { body: payload })
}

export async function updateUserGroup(
  groupId: number,
  payload: SaveUserGroupRequest,
): Promise<UserGroupResponse> {
  return webApi.put('/user-groups/{group_id}', { path: { group_id: groupId }, body: payload })
}

export async function deleteUserGroup(groupId: number): Promise<void> {
  await webApi.delete('/user-groups/{group_id}', { path: { group_id: groupId } })
}
