// Made items aliases of the generic demand import types.
import type {
  ImportCommitResponse,
  ImportDivergence,
  ImportRowValidation,
  ImportValidateResponse,
} from '@/shared/demand-import'
import type { MadeItemResponse } from './madeItemsResponse'
import type { Schemas } from '@/core/api/generated'

// Derived from the schema so a backend change is caught at compile time.
export type MadeItemBatchDivergenceField = Schemas['MadeItemFieldDivergenceResponse']['field']

export type MadeItemBatchRowStatus = Schemas['MadeItemRowValidationResponse']['row_status']

export type MadeItemBatchMatchSource = NonNullable<
  Schemas['MadeItemRowValidationResponse']['match_source']
>

/**
 * Every field is sent, null when the sheet left it empty, although the
 * schema lets the optional ones be omitted.
 */
export type MadeItemBatchDemandRowInput = Required<Schemas['MadeItemBatchDemandRowSchema']>

export type MadeItemFieldDivergence = ImportDivergence<MadeItemBatchDivergenceField>

export type MadeItemRowValidationResult = ImportRowValidation<
  MadeItemResponse,
  MadeItemBatchDivergenceField,
  MadeItemBatchMatchSource
>

export type ValidateBatchMadeItemDemandsRequest = Schemas['ValidateBatchMadeItemDemandsRequest']

export type ValidateBatchMadeItemDemandsResponse = ImportValidateResponse<MadeItemRowValidationResult>

export type CommitBatchMadeItemDemandsRequest = Schemas['CommitBatchMadeItemDemandsRequest']

export type CommitBatchMadeItemDemandsResponse = ImportCommitResponse
