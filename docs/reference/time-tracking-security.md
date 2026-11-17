# time tracking security

The full list of mitigations for time tracking, the consent dialog, the risks that remain and the standards the design follows. The guide [TIME_TRACKING.md section 6](../TIME_TRACKING.md#6-security) names the assets, trust boundaries and operator duties; the mechanisms named here are specified in [time-tracking-credentials.md](time-tracking-credentials.md) and [time-tracking-provider.md](time-tracking-provider.md).

- [time tracking security](#time-tracking-security)
  - [1 mitigations](#1-mitigations)
  - [2 no secret leaks](#2-no-secret-leaks)
  - [3 consent](#3-consent)
  - [4 residual risks](#4-residual-risks)
  - [5 reference frame](#5-reference-frame)

## 1 mitigations

| Mitigation | What it does |
| ---------- | ------------ |
| Sealed passwords | The password is sealed for the time tracking service's key at save time ([time-tracking-provider.md section 3](time-tracking-provider.md#3-sealed-credentials)). Glados, its database, its dumps and its admins cannot read it; reading one needs the service's private key too. |
| Confirmed key | The key users seal for is confirmed by an admin and only when the service still serves it, and a changed service URL clears it ([time-tracking-credentials.md section 3](time-tracking-credentials.md#3-the-credential-key)). |
| Binding | Credentials carry the binding the service answered at verification, and the service refuses them for another server or key, before contacting anything. |
| Encryption at rest | The API key and the user names are encrypted with the instance key. It protects database dumps, backups and SQL injection reads, not a compromised host. |
| Failed check lockout | Repeated failed checks lock a user's further checks ([time-tracking-credentials.md section 8](time-tracking-credentials.md#8-failed-check-lockout)). |
| One account per Glados user | The keyed fingerprint of the user name is unique. |
| Stop after the first rejection | Stored credentials the attendance system rejected are not sent again until the user saves. |
| Internal network | The service publishes no port, so only containers on the stack's network reach it, and only with the API key. |
| No redirects | The client never follows a redirect, so the API key cannot travel to a redirect target. |
| No secret leaks | Passwords, sealed values, the API key, headers and bodies stay out of errors and logs (section 2). |
| Header-safe input | User names and passwords are restricted so they cannot corrupt the auth header they end up in. |
| Load limits | Fetch spacing per user in Glados, and the service's own session cap. |
| Personal accounts only | Shared, service and system accounts cannot hold credentials. |
| Consent | Saving requires confirming the consent dialog (section 3). |

## 2 no secret leaks

- The password and the API key are `SecretStr` in requests and commands.
- The time tracking routes and the time tracking settings routes never echo request input in a validation error.
- The client logs no headers or bodies; an unexpected answer is logged by field location only, never by value.
- Exception messages carry no credentials and no API key.
- Log lines for credential changes say only that the credentials were set, changed or removed.

## 3 consent

- Saving credentials for the first time, or after the consent text changed, requires confirming a consent dialog, whose current version is `TIME_TRACKING_CONSENT_VERSION`.
- The dialog explains that Glados reads time data only on the Time Tracking page, shows it only to the user and stores none of it.
- It explains that the credentials are stored encrypted, that the password is sealed so Glados itself cannot read it, and that administrators can see neither the password nor the time data.
- It explains that the user can withdraw at any time by removing the credentials.

## 4 residual risks

- Someone controlling both the Glados database and the service's private key can open every stored password.
- Someone with the API key and network access to the service can have it verify guessed passwords; the service's own limits and the attendance system's lockout apply, Glados' lockout does not.
- The service may depend on an undocumented interface of the attendance system, which can change with any update of it.

## 5 reference frame

The design follows OWASP ASVS 4.0 V6 (stored cryptography), V8 (data protection) and V9 (communications), the OWASP Secrets Management Cheat Sheet, and GDPR Articles 5 (principles), 13 (information), 25 (data protection by design and by default) and 32 (security of processing).
