// Kept under *Response names, while the backend DTOs carry a DTO suffix.
import type { Schemas } from '@/core/api/generated'

export type StateMachineStateResponse = Schemas['StateMachineStateDTO']

export type StateMachineEdgeResponse = Schemas['StateMachineEdgeDTO']

/** One row of a derivation table, in evaluation order. */
export type StateMachineRuleResponse = Schemas['StateMachineRuleDTO']

/** One user action with the statuses it starts from. */
export type StateMachineIntentResponse = Schemas['StateMachineIntentDTO']

/**
 * key is the stable machine identifier, e.g. "production_order_status".
 * kind says whether a decision table derives the status ("derived") or user
 * actions set it ("intent"). entity is the human-readable name and
 * description the enum's docstring, or null.
 */
export type StateMachineResponse = Schemas['StateMachineDTO']

export type StateMachinesResponse = Schemas['StateMachineCatalogDTO']

/**
 * One status change the code makes, with the derivation rows behind its
 * target, the actions its trigger performs and what the trigger changes on
 * other records. subject is the machine of the record the request acted on.
 */
export type StateMachineTransitionResponse = Schemas['StateMachineTransitionDTO']

export type StateMachineImplicationResponse = Schemas['StateMachineImplicationDTO']
