---
title: Sessions
summary: Where you are signed in, which devices skip the two-factor code, and how to end either.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/session/manage_sessions.py
  - backend/src/modules/platform/application/use_cases/session/manage_trusted_devices.py
  - backend/src/modules/platform/domain/services/session_rules.py
  - frontend/src/core/session/userActivity.ts
  - backend/src/modules/platform/application/use_cases/auth/totp_login.py
  - backend/src/modules/platform/application/use_cases/user/update_user.py
  - backend/src/modules/platform/application/use_cases/user/force_logout_user.py
lastVerified: 2026-11-12
---

Account, **Sessions** shows two lists. **Active Sessions** are the places where you are signed in right now. **Trusted Devices** are the browsers that may skip the two-factor code at sign-in. The two are separate: signing a device out leaves it trusted, so the next sign-in there asks for no code.

## Your sessions {#sessions}

Each row of **Active Sessions** shows the **Device** as its browser names itself, the **IP Address** it signed in from, when it **Signed In** and when it was **Last Active**. The session you are using now carries the tag **This device**. The list shows only sessions that still work.

## Why a session ends by itself {#idle}

A session ends when you leave it alone for longer than the idle limit an administrator sets. Every click, key, scroll or touch on a page starts that clock again, so you are never signed out in the middle of your work, even while you type a long text. What Glados does by itself, such as checking for notifications, does not count, so a page left open runs out like any other. However active you are, every session also ends 30 days after you signed in, or after the number of days an administrator chose, and you then sign in again.

## Signing a session out {#revoke}

**Sign Out** in a row ends that session at once, and the device has to sign in again. On your own session it signs you out here, and the confirmation warns you. **Sign Out Other Sessions** ends every session except the one you are using. Use it after you signed in on a borrowed computer, or when a row looks unfamiliar.

## Trusted devices {#devices}

When you sign in with two-factor authentication, you can tick **Don't ask again on this device for 30 days**, with the number of days an administrator set. After the code is accepted, that browser becomes a trusted device and skips the code until the trust runs out. The list shows when each device was trusted, when it was **Last Used** and when it **Expires**. If the administrator set the trust to 0 days, the box is not offered. A trusted device stays trusted when you sign out, which is the point of it.

## Removing a trusted device {#untrust}

**Remove** in a row ends the trust of that browser, so it asks for a code again at the next sign-in. **Remove All** does the same for every device. A device you no longer have should be removed, not only signed out.

## What ends them without you {#automatic}

When you change your own password, every other session ends, every trusted device is removed and every [access token](/handbook/account/access-tokens) is revoked, while the session you changed it from stays. When an administrator changes your password, all your sessions end and your tokens are revoked as well. Turning two-factor authentication off, or an administrator resetting it, removes every trusted device. When an administrator signs your account out everywhere, your sessions, trusted devices and [access tokens](/handbook/account/access-tokens) all end.

## Examples

**A borrowed computer.** You signed in at a colleague's desk and forgot to sign out. Back at your own computer you click **Sign Out Other Sessions**, and the borrowed one is signed out at once.

**A lost phone.** You click **Sign Out** on the phone's row and **Remove** on its trusted device. Whoever finds it needs your password and a new code.

**A new password.** You change your password on the office computer. Your laptop at home asks you to sign in again, with a code, the next time you use it.
