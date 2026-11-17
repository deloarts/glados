import { passkeyRegistrationOptions, registerPasskey, type PasskeySummary } from '../api/passkeys'
import { rememberUser } from './rememberedUsers'
import { createPasskey } from './webauthn'

/**
 * Registers a passkey for the signed-in user on this device: confirms the
 * password, runs the browser prompt, stores the passkey, and remembers on
 * this device which passkey to offer at the next login.
 */
export async function setUpPasskeyOnThisDevice(
  password: string,
  name: string,
  user: { username: string; full_name: string },
): Promise<PasskeySummary> {
  const challenge = await passkeyRegistrationOptions(password)
  const credential = await createPasskey(challenge.options)
  const created = await registerPasskey(challenge.challenge_token, credential, name)
  rememberUser({
    username: user.username,
    fullName: user.full_name,
    credentialId: credential.rawId as string,
    passkeyPublicId: created.public_id,
    passkeyDeclined: false,
  })
  return created
}
