# terminal security

The full threat and mitigation list for terminals and infoscreens and the risks that remain. The guide [TERMINAL_INTEGRATION.md section 10](../TERMINAL_INTEGRATION.md#10-security) names the assets, the trust boundaries and the operator duties; the mechanisms named here are specified in [terminal-auth.md](terminal-auth.md), [terminal-display.md](terminal-display.md) and [terminal-infoscreens.md](terminal-infoscreens.md).

- [terminal security](#terminal-security)
  - [1 threats and mitigations](#1-threats-and-mitigations)
  - [2 residual risks](#2-residual-risks)

## 1 threats and mitigations

| Threat | Mitigation |
| ------ | ---------- |
| Stolen or guessed credentials | The private key never leaves the bridge, and nothing secret travels in the URL. A session needs a fresh signature over a nonce bound to the key. |
| Replay of a sign-in | The nonce expires after 60 seconds, is HMAC bound to its key and is claimed once in Redis across all workers. |
| A leaked terminal key | It only creates pending terminals, capped at 20, each of which needs a person to type the code shown on that very screen. It is refused on the key API. Revoking it stops further registrations without touching enrolled displays. |
| Token confusion | Terminal tokens are signed with their own derived key and carry their own scope and audience, so a web session never accepts a terminal token and the device endpoints never accept a web token. The request log does not attribute a terminal token to a user. |
| A revoked or stolen display | Revoke takes effect on the next request, because every request reloads the terminal; the display then gets no feed and no live data. Signing in again only puts it back to pending. |
| A copied key | Clone detection marks the terminal and audits it. |
| Brute force on endpoints without a session | Challenge and session have per address rate limits, and pairing codes are only checked on an authenticated, permission gated admin action. |
| Personal data on a wall | Dedicated feed models without persons are guarded by a schema test, and customer names appear only on request. Messages to terminals reach a display without their author, guarded by a schema test over the device state. |
| Untrusted device reports | Device details are cleaned, capped and stored as data; nothing in them is interpreted, and an odd report never blocks a sign-in. |
| Identifying a device from the terminals list | Fingerprints, client addresses, serials and hostnames are left out of the answer for readers without `manage:terminals`. |
| Thumbnail links | A link names one item picture, carries no user and expires within 90 minutes, and it is refused once the item is archived. |
| Privilege escalation through the connect permission | `connect:terminals` cannot be granted to people, normal keys or PATs, and a terminal key's account cannot be widened. |

## 2 residual risks

- Physical access to a Pi gives access to its key and its terminal key file; the guide's operator duties say what to do when a Pi goes missing.
- Behind a proxy the stack is not told to trust, the allowlist and the rate limit see only that proxy. Listing a proxy in `GLADOS_TRUSTED_PROXIES` that clients can reach directly would let them name any address.
- The replay guard fails open while Redis is down, as it does for TOTP, but the nonce expiry and its binding to the key still apply.
- Clone detection cannot tell a clone from a display that changed its address, so it only marks.
- The rate limit is per worker process, so its real ceiling is the limit times the worker count.
- A thumbnail link copied off a display shows that one picture to anyone until it expires.
