import type { Schemas } from '@/core/api/generated'

export type TerminalResponse = Schemas['TerminalResponse']
export type TerminalStatus = TerminalResponse['status']
export type TerminalMode = TerminalResponse['mode']
export type TerminalDisplayPower = TerminalResponse['display_power']

/** What the display reported about its computer and its monitor. */
export type TerminalDeviceDetails = Schemas['TerminalDeviceDetailsResponse']

export type TerminalApproveRequest = Schemas['TerminalApproveRequest']
export type TerminalUpdateRequest = Schemas['TerminalUpdateRequest']
export type TerminalDisplayOverrideRequest = Schemas['TerminalDisplayOverrideRequest']
export type TerminalBulkActionResponse = Schemas['TerminalBulkActionResponse']

/** A screen a terminal can be assigned, as the infoscreens list returns it. */
export type TerminalScreenOption = Schemas['InfoscreenResponse']

/** A message shown on many terminals at once, with its audience and author. */
export type TerminalBroadcastResponse = Schemas['TerminalBroadcastResponse']
export type TerminalBroadcastSeverity = TerminalBroadcastResponse['severity']
export type TerminalBroadcastStyle = TerminalBroadcastResponse['style']
export type TerminalBroadcastAudienceRequest = Schemas['TerminalBroadcastAudienceRequest']
export type TerminalBroadcastReachResponse = Schemas['TerminalBroadcastReachResponse']

export type TerminalBroadcastCreateRequest = Schemas['TerminalBroadcastCreateRequest']
