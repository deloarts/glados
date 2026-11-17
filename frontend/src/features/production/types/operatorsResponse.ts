import type { PublicUser } from '@/core/types/userResponse'

// The `/production-operators` endpoint reuses the same PublicUserResponse
// shape as other "live user reference" fields (e.g. LotResponse.creator).
export type Operator = PublicUser
