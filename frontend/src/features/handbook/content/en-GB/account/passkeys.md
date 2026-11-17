---
title: Passkeys
summary: How to sign in with Windows Hello, Touch ID or a security key instead of your password and code, and how to rename or remove a passkey.
sourceRefs:
  - frontend/src/features/auth/views/PasskeysView.vue
  - frontend/src/features/auth/utils/passkeySetup.ts
  - backend/src/modules/platform/application/use_cases/passkey/register_passkey.py
  - backend/src/modules/platform/application/use_cases/passkey/manage_passkeys.py
  - backend/src/modules/platform/domain/services/login_policy.py
lastVerified: 2026-11-10
---

A passkey lets you sign in without typing your password and two-factor code. Your device confirms that it is you, with Windows Hello, Touch ID, a fingerprint or a security key, and Glados lets you in. Each device has its own passkey, and under Account, **Passkeys** you see all of yours.

## Adding a passkey {#add}

Click **Add Passkey** on the device you want to use. Glados suggests a **Name** such as Windows Hello, which you can change, and asks for your **Current Password** to make sure it is you. Then follow the prompt of your device, such as the fingerprint reader or the PIN of Windows Hello. The passkey appears in the list with **This device** next to it. After a sign in with your password, Glados may also offer to set up a passkey for this device, and **Not Now** skips that.

**Add Passkey** shows disabled with a tooltip when the browser cannot use passkeys. That happens when Glados is not opened over https, or on a browser without passkey support. The system account cannot use passkeys at all, because its two-factor code is mandatory.

## Signing in with a passkey {#sign-in}

On the sign in page, click **Sign In With Passkey** and confirm on your device. If the prompt is cancelled or the passkey is not accepted, enter your password as usual. An account from the company directory has to sign in with its password once every 30 days, so that an account switched off in the directory cannot keep using its passkey.

## The list {#list}

Each row shows the **Name**, when the passkey was **Added** and when it was **Last Used**. **This device** marks the passkey of the device you are using. **Synced** marks a passkey your phone or password manager copies to your other devices, so it also works there.

## Renaming and removing {#remove}

**Rename** gives a passkey a clearer name, such as Office laptop. **Remove** deletes one passkey, and that device asks for your password again. **Remove All Passkeys** deletes every passkey of your account, which is the right step when a device was lost and you are not sure which one it was.

## Examples

**Windows Hello at the office.** You click **Add Passkey**, keep the name Windows Hello, enter your password and confirm with your PIN. From then on you sign in at that computer with **Sign In With Passkey**.

**A lost laptop.** You open **Passkeys** on another computer and click **Remove** on the laptop's passkey. The laptop can no longer sign in without your password.

**A new phone.** Your passkey shows **Synced**, so your new phone already has it after you sign in to your phone account. You remove the old phone's passkey if it had its own.
