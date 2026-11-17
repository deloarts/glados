import { webApi } from '@/core/api/webRequest'
import type { PlcEnvironment, PlcEnvironmentSaveRequest, PlcEnvironmentSettings } from '../types/productDevice'

/** Every PLC environment, archived ones included. */
export function getPlcEnvironments(): Promise<PlcEnvironment[]> {
  return webApi.get('/product-device-resources/plc-environments', { query: { include_archived: true } })
}

/** The settings of Siemens TIA Portal, which a new environment starts from. */
export function getPlcEnvironmentTemplate(): Promise<PlcEnvironmentSettings> {
  return webApi.get('/product-device-resources/plc-environments/template')
}

export function createPlcEnvironment(body: PlcEnvironmentSaveRequest): Promise<PlcEnvironment> {
  return webApi.post('/product-device-resources/plc-environments', { body })
}

export function updatePlcEnvironment(id: number, body: PlcEnvironmentSaveRequest): Promise<PlcEnvironment> {
  return webApi.put('/product-device-resources/plc-environments/{environment_id}', { path: { environment_id: id }, body })
}

export function setPlcEnvironmentArchived(id: number, archived: boolean): Promise<PlcEnvironment> {
  return archived
    ? webApi.post('/product-device-resources/plc-environments/{environment_id}/archive', { path: { environment_id: id } })
    : webApi.post('/product-device-resources/plc-environments/{environment_id}/restore', { path: { environment_id: id } })
}
