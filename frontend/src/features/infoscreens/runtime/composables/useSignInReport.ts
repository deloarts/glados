import { computed } from 'vue'
import type { ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { buildSignInReport } from '../utils/signInReport'
import type { SignInReport } from '../utils/signInReport'
import type { InfoscreenRuntime } from './useInfoscreenRuntime'

/** The waiting screen of a wall display, following the device runtime. */
export function useSignInReport(runtime: InfoscreenRuntime): ComputedRef<SignInReport> {
  const { t } = useI18n()
  const origin = typeof window !== 'undefined' ? window.location.origin : ''

  return computed(() =>
    buildSignInReport(
      {
        phase: runtime.phase.value,
        sessionError: runtime.sessionError.value,
        signInStep: runtime.signInStep.value,
        deviceState: runtime.deviceState.value,
        identity: runtime.identity.value,
        attempt: runtime.attempt.value,
        lastAttemptAt: runtime.lastAttemptAt.value,
        origin,
        version: __APP_VERSION__,
      },
      t,
    ),
  )
}
