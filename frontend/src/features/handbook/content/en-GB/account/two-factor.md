---
title: Two-Factor Authentication
summary: How to protect your account with a code from an authenticator app, how to turn it off again, and when Glados requires it.
sourceRefs:
  - frontend/src/features/auth/views/TwoFactorView.vue
  - backend/src/modules/platform/application/use_cases/user/enroll_totp.py
  - backend/src/modules/platform/application/use_cases/user/confirm_totp_enrollment.py
  - backend/src/modules/platform/application/use_cases/user/disable_totp.py
  - backend/src/modules/platform/domain/services/login_policy.py
lastVerified: 2026-11-12
---

Two-factor authentication asks for a six digit code from an app on your phone each time you sign in, after your password. Someone who learns your password still cannot get in without your phone. You set it up under Account, **2FA**, and the tag next to the title says whether it is **Enabled** or **Disabled**.

## Turning it on {#enable}

You need an authenticator app on your phone, such as Google Authenticator, Microsoft Authenticator or Authy. Click **Enable 2FA**, enter your **Current Password** and click **Continue**, and Glados shows a QR code. The password keeps someone who finds your session open from putting their own phone on your account. When Glados asks you to set it up at sign-in, you have just entered your password and are not asked again. Scan it with the app, which then shows a new code every 30 seconds. If you cannot scan, type the **Manual entry key** into the app instead. Enter the current code under **Verification Code**, and two-factor authentication is on as soon as the sixth digit is in. A wrong or outdated code is refused, so wait for the next one and try again. **Cancel** stops the setup and nothing changes.

To move to a new phone, turn it off and set it up again with the new phone.

## Signing in with a code {#sign-in}

After your password, Glados asks for the **Authentication Code** from the app. You can tick **Don't ask again on this device for 30 days**, with the number of days an administrator set, so that browser skips the code until the trust runs out. Those browsers are listed as trusted devices under [Sessions](/handbook/account/sessions#devices). A [passkey](/handbook/account/passkeys) skips both the password and the code.

## Turning it off {#disable}

Click **Disable 2FA**, enter the current **Authentication Code** from the app and the protection is off. Every trusted device is removed at the same time. If an administrator requires two-factor authentication for everyone, or you hold **Write Settings**, you are asked to set it up again at your next sign-in.

## When it is required {#required}

An administrator can require two-factor authentication for every account under Settings, **Security**. Accounts with **Write Settings** always need it. The system account needs it too and cannot turn it off; only an administrator on the server can reset it.

## Examples

**Setting it up.** You click **Enable 2FA**, scan the code with Microsoft Authenticator and type the six digits the app shows. The tag turns to **Enabled**, and your next sign-in asks for a code.

**A new phone.** Before you hand in the old phone, you click **Disable 2FA** and enter its code. Then you click **Enable 2FA** and scan the new QR code with the new phone.

**A code that is refused.** You type a code just as the app changes it. Glados says the code is invalid, and you enter the next one.
