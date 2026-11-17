# time tracking credentials

The time tracking settings and their validation, the admin routes, how a user saves and checks their own credentials, when stored credentials may be used, how they are sealed, encrypted and fingerprinted, and when they are deleted. The guide [TIME_TRACKING.md](../TIME_TRACKING.md) explains the integration; the contract with the service is in [time-tracking-provider.md](time-tracking-provider.md) and the security reasoning in [time-tracking-security.md](time-tracking-security.md).

- [time tracking credentials](#time-tracking-credentials)
  - [1 settings](#1-settings)
  - [2 admin routes](#2-admin-routes)
  - [3 the credential key](#3-the-credential-key)
  - [4 saving and checking](#4-saving-and-checking)
    - [4.1 preconditions](#41-preconditions)
    - [4.2 the check and what is stored](#42-the-check-and-what-is-stored)
    - [4.3 reading the account](#43-reading-the-account)
  - [5 when stored credentials can be used](#5-when-stored-credentials-can-be-used)
  - [6 encryption and fingerprint](#6-encryption-and-fingerprint)
  - [7 lifecycle](#7-lifecycle)
  - [8 failed check lockout](#8-failed-check-lockout)

## 1 settings

- `admin_time_tracking_settings` is a singleton row (`id = 1`) that the first save writes. A database without the row reads as time tracking switched off.
- The service URL is an absolute `http://` or `https://` URL, optionally with a path, without user information, query or fragment. Plain http needs no opt-in: the service runs in the stack and passwords travel sealed.
- The API key is an `EncryptedString` column, write-only: requests take it, responses only say whether one is stored, an omitted key keeps the stored one and an empty one clears it.
- Enabling requires the service URL and the API key.
- Time tracking is available to users (`is_ready`, `features.time_tracking`) only when it is enabled, configured and a credential key is confirmed.
- A changed service URL clears the confirmed key, its id and the provider label.
- The privacy policy URL is linked from the users' consent dialog.

## 2 admin routes

| Route | Permission | Purpose |
| ----- | ---------- | ------- |
| `GET /admin/settings/time-tracking` | `read:settings` | Settings plus every user with stored credentials: Glados user name, full name, when saved, and whether the credentials can be used. Never the time tracking user name or anything sealed. |
| `PUT /admin/settings/time-tracking` | `write:settings` | Update; omitted fields keep their value, and an empty string clears an optional one. |
| `POST /admin/settings/time-tracking/test` | `write:settings` | Test the given or stored service: `info` and `status`, with whether the contract and the credential fields are supported and whether the served key is the confirmed one. Stores nothing. |
| `POST /admin/settings/time-tracking/confirm-key` | `write:settings` | Confirm the key the saved service serves, by its id ([section 3](#3-the-credential-key)). |
| `DELETE /admin/settings/time-tracking/credentials` | `write:settings` | Delete every user's stored credentials. |
| `DELETE /users/{id}/time-tracking-credentials` | `write:settings` | Delete one user's stored credentials. |

- The routes exist on the web surface only, and never echo request input in a validation error.
- Every change is written to the settings audit log under the domain `time_tracking`. A changed service URL names the old and the new URL, a changed API key is mentioned without its value, and a confirmed key names its id and the previous one.
- `GET /host/capabilities` reports `features.time_tracking` and `features.time_tracking_provider_label`, the label stored with the confirmed key, so the capabilities call never reaches the service.

## 3 the credential key

- The connection test shows the `credential_key_id` the service serves.
- Confirming sends that id; Glados reads `info` from the saved service again and stores the public key, its id and the provider label only when the id still matches, else it answers `TimeTrackingKeyChangedError`. A key that changed between test and confirmation is never confirmed unseen.
- The confirmation works only for the saved settings, so the admin saves a changed URL or API key first.
- Credentials sealed for another key id are not usable from then on ([section 5](#5-when-stored-credentials-can-be-used)).

## 4 saving and checking

### 4.1 preconditions

A user saves through `PUT /time-tracking/me/account` with user name, password and the confirmed consent version. Before anything reaches the service, all of the following must hold.

1. Time tracking is available.
2. The account is a personal account; shared accounts, service accounts and the system user cannot hold time tracking credentials.
3. The request confirms the current consent text version (`TIME_TRACKING_CONSENT_VERSION`).
4. A password is present, unless the stored sealed value may be re-verified: same user name (casefolded), usable apart from the consent.
5. The user name is not stored for another Glados user, checked by fingerprint, and the answer does not say which user holds it.
6. The user is not locked out after failed checks ([section 8](#8-failed-check-lockout)).

### 4.2 the check and what is stored

- Glados seals user name and password for the confirmed key and has the service verify the sealed value.
- A rejected login stores nothing and counts as a failed check.
- On success the row is written with the user name, the sealed value, the binding the service answered, the key id it was sealed for, a fresh consent stamp and no failure mark.
- The success answer carries the employee name and the rights, which are not stored.
- `POST /time-tracking/me/account/check` verifies the stored sealed value the same way.
- At most one row exists per user, enforced by a unique `user_id`.
- User names and passwords are restricted so they cannot corrupt the auth header they end up in: no colon in the user name, no control characters, at most 128 and 256 characters.

### 4.3 reading the account

- `GET /time-tracking/me/account` never calls the service.
- It returns the stored user name (to its owner only), whether a password is stored, the consent version to confirm, whether the stored consent is current, the privacy policy link, the provider label, and `time_tracking_credentials_valid` with a reason when they are not usable.
- The password never leaves the server, not even sealed.

## 5 when stored credentials can be used

Stored credentials are usable when every condition below holds, decided from Glados state alone (`credentials_invalid_reason`).

| Reason when not | Condition |
| --------------- | --------- |
| `missing` | A row exists. |
| `undecryptable` | The user name decrypts with a configured key. |
| `binding_changed` | A sealed value is stored, and it was sealed for the confirmed key. |
| `auth_failed` | The attendance system has not rejected them since they were saved. |
| `consent_outdated` | The stored consent version is the current one. |

- Every call that uses stored credentials checks this first and sends nothing otherwise; the user enters the password again in My Account.
- When the service answers `credentials_rejected` for stored credentials, the failure time is recorded and no further call is made with them until the user saves again, so repeated page loads cannot lock the account on the attendance system after the user changed their password.
- When it answers `binding_changed`, the sealed value is dropped, because Glados cannot re-seal it; the reason reads `binding_changed` from then on.

## 6 encryption and fingerprint

- The password exists only inside the sealed value, which only the service can open ([time-tracking-provider.md section 3](time-tracking-provider.md#3-sealed-credentials)).
- The user name and the API key are `EncryptedString` columns, encrypted with `SECURITY__ENCRYPTION_KEY` like every stored secret ([ADR 0005](../adr/0005-secret-encryption-at-rest.md)), and re-encrypted on key rotation. A value no configured key can decrypt loads as unset.
- The user name cannot carry a unique index in encrypted form, so a keyed fingerprint with a unique index does: HMAC-SHA256 over the trimmed, casefolded user name, keyed with a key derived from `SECURITY__ENCRYPTION_KEY` through HKDF under its own label.
- The key id of the fingerprint key is stored next to it, and a boot step recomputes every fingerprint whose key id differs after a rotation.

## 7 lifecycle

- `DELETE /time-tracking/me/account` deletes the credentials and the consent stored with them, and works even while time tracking is disabled, so withdrawing is always possible.
- Deactivating a user, by editing the user or by deleting it (which deactivates), deletes their credentials, and a hard delete of the user row removes them through the foreign key.
- Turning a user with stored credentials into a shared or service account is refused with `TimeTrackingCredentialsNotAllowedError` until an admin removes them.
- Disabling time tracking keeps the stored credentials.
- "Delete All Stored Credentials" in the admin tab switches time tracking off for good or reacts to an incident.

## 8 failed check lockout

- Five failed credential checks (Save or Check access) per Glados user lock further checks for 15 minutes.
- Successful checks do not reset the count, so the save form cannot be used to guess a colleague's password or to lock their account by interleaving valid attempts.
