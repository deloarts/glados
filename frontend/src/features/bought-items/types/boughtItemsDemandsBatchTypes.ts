// Bought items aliases of the generic demand import types.
import type {
  ImportCommitResponse,
  ImportDivergence,
  ImportRowValidation,
  ImportValidateResponse,
} from '@/shared/demand-import'
import type { BoughtItemResponse } from './boughtItemsResponse'
import type { Schemas } from '@/core/api/generated'

// Derived from the schema so a backend change is caught at compile time.
export type BatchDivergenceField = Schemas['FieldDivergenceResponse']['field']

export type BatchRowStatus = Schemas['RowValidationResponse']['row_status']

export type BatchMatchSource = NonNullable<Schemas['RowValidationResponse']['match_source']>

/**
 * Every field is sent, null when the sheet left it empty, although the
 * schema lets the optional ones be omitted.
 */
export type BatchDemandRowInput = Required<Schemas['BatchDemandRowSchema']>

export type FieldDivergence = ImportDivergence<BatchDivergenceField>

export type RowValidationResult = ImportRowValidation<
  BoughtItemResponse,
  BatchDivergenceField,
  BatchMatchSource
>

export type ValidateBatchDemandsRequest = Schemas['ValidateBatchDemandsRequest']

export type ValidateBatchDemandsResponse = ImportValidateResponse<RowValidationResult>

export type CommitBatchDemandsRequest = Schemas['CommitBatchDemandsRequest']

export type CommitBatchDemandsResponse = ImportCommitResponse
