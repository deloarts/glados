import type { Schemas } from '@/core/api/generated'

export type ProductDeviceOption = Schemas['ProductDeviceOptionResponse']
export type ProductDeviceOptionCategory = Schemas['ProductDeviceOptionCategory']
export type ProductDeviceKind = Schemas['ProductDeviceKindResponse']
export type ProductDeviceKindPosition = Schemas['ProductDeviceKindPositionResponse']
export type ProductDeviceKindParameter = Schemas['ProductDeviceKindParameterResponse']
export type ProductDeviceKindSignal = Schemas['ProductDeviceKindSignalResponse']
export type ProductDeviceParameterType = Schemas['ProductDeviceParameterType']
export type ProductDeviceKindSaveRequest = Schemas['ProductDeviceKindSaveRequest']
export type ProductDeviceOptionCreateRequest = Schemas['ProductDeviceOptionCreateRequest']
export type ProductDeviceOptionUpdateRequest = Schemas['ProductDeviceOptionUpdateRequest']

export type ProductDevice = Schemas['ProductDeviceResponse']
export type ProductDeviceComponent = Schemas['ProductDeviceComponentResponse']
export type ProductDeviceSignalType = Schemas['ProductDeviceSignalType']
export type ProductDeviceSaveRequest = Schemas['ProductDeviceSaveRequest']
export type ProductDeviceComponentRequest = Schemas['ProductDeviceComponentRequest']
export type ProductDeviceNamePreview = Schemas['ProductDeviceNamePreviewResponse']
export type ProductDeviceNamePreviewRequest = Schemas['ProductDeviceNamePreviewRequest']

export const PARAMETER_TYPES: ProductDeviceParameterType[] = ['number', 'text', 'boolean']

export const SIGNAL_TYPES: ProductDeviceSignalType[] = ['di', 'do', 'ai', 'ao', 'bus']

export type PlcEnvironment = Schemas['PlcEnvironmentResponse']
export type PlcEnvironmentSaveRequest = Schemas['PlcEnvironmentSaveRequest']
export type PlcEnvironmentSettings = Schemas['PlcEnvironmentSettingsSchema']
export type PlcExportColumn = Schemas['ExportColumnSchema']
export type PlcExportColumnSource = Schemas['ExportColumnSource']
export type PlcCharConversion = Schemas['CharConversionSchema']

/** The prefix keys of a PLC environment, in the order the editor shows them. */
export const PLC_PREFIX_KEYS = [
  'di',
  'do',
  'ai',
  'ao',
  'bus',
  'safety_di',
  'safety_do',
  'safety_ai',
  'safety_ao',
] as const

export const PLC_EXPORT_SOURCES: PlcExportColumnSource[] = [
  'tag_name',
  'tag_table',
  'data_type',
  'address',
  'comment',
  'device_name',
  'device_name_ascii',
  'signal_type',
  'safety',
  'constant',
]

export type PlcTag = Schemas['PlcTagResponse']
export type PlcTagList = Schemas['PlcTagListResponse']

/** The disciplines a machine has, from its product. */
export interface ProductDisciplines {
  pneumatics: boolean
  hydraulics: boolean
  electrics: boolean
  robotics: boolean
}

export type ProductDeviceCompleteness = Schemas['ProductDeviceCompletenessResponse']
export type DevicePlan = Schemas['DevicePlan']
export type SequenceCoverage = ProductDeviceCompleteness['sequence_coverage']
