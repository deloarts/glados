---
title: Access Tokens
summary: How a personal access token lets a script or the SolidWorks add-in work as you, with the permissions you choose, and how to revoke it.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/pat/create_pat.py
  - backend/src/modules/platform/application/use_cases/pat/revoke_pat.py
  - backend/src/modules/platform/domain/services/pat_rules.py
  - backend/src/modules/platform/domain/services/token_permission_rules.py
  - backend/src/modules/platform/domain/services/token_lifetime.py
  - backend/src/modules/platform/application/services/token_lifetime_cap.py
  - frontend/src/shared/components/tokens/TokenFormDialog.vue
  - frontend/src/shared/components/tokens/TokenManagementControls.vue
lastVerified: 2026-11-13
---

A personal access token lets a program work in Glados as you, without your password. The SolidWorks add-in or a script uses one instead of signing in. Everything a token does is recorded under your name, and it stops working when your account is switched off. You find your tokens under Account, **Access Tokens**.

## What a token is {#what}

A token is a long secret text. Glados shows it once, right after you create it, so copy it into the program that needs it before you close the dialog. Nobody can show it again later, not even an administrator; if it is lost, revoke it and create a new one. The table shows only the first characters under **Prefix**, enough to tell your tokens apart.

## Creating a token {#create}

Click **Create Token** and give it a **Name** that says what uses it, such as Weekly order export. Under **Permissions** tick what the token may do. **Expires In (days)** starts at 30 and goes up to the **Maximum Token Lifetime (days)** an administrator set on the Security tab. **Never expires** is only offered while the Security tab sets no maximum. Enter your **Current Password** last: a token keeps working after you sign out, so a session left open on someone else's screen must not be enough to create one. A wrong password counts like a failed sign-in. Creating tokens needs **Write Access Token**; without it **Create Token** and the add-in buttons show disabled with a tooltip that names the permission.

## The add-in tokens {#addin}

While SolidWorks PDM is switched on, two buttons fill in the form for an add-in. **Create SolidWorks Add-in Token** is for the SolidWorks add-in. The name becomes SW Addin with today's date, the add-in's permissions **Write Source Items** and **Use EPLAN Data Portal** are ticked and the expiry is the end of this year, or earlier if the Security tab allows less. The add-in needs the first to create source items and the second for its Data Portal lookup. If your own account does not hold one of them, the dialog says so and the token is created without it; ask an administrator for the permission first.

**Create PDM Add-in Token** is for the PDM vault add-in, which tells Glados when a file in the vault changes. The name becomes PDM Addin with today's date, its only permission **Use PDM Add-in** is ticked and the expiry is the same. You paste the token on the Glados tab of a vault view in File Explorer. The token can do nothing but ask Glados to look at a file again and show what Glados did with the files you select. If your account does not hold **Use PDM Add-in**, the dialog says so; ask an administrator for it.

## What a token may do {#scope}

A token may do only what you ticked, and you can only tick permissions you hold yourself. The permissions of a token are fixed when it is created. To change them, create a new token and revoke the old one. If you lose a permission later, your tokens lose it too. Some permissions never go on a token, even if you hold them: **Read Settings**, **Write Settings**, **Manage API Keys** and **Connect Terminals**. A token with **Use AI Agents** is held to the shorter lifetime set for agent tokens. Tokens you create on the **AI Agents** tab are listed here too. The system account cannot create tokens.

## Revoking {#revoke}

**Revoke** in a row stops that token at once and for good. **Revoke All** stops every token you own. Changing your password revokes all your tokens too, and so does an administrator who changes it or signs your account out everywhere, so the programs that used them need new ones. You need no permission to revoke your own tokens, so **Revoke** and **Revoke All** work even without **Write Access Token**. Apart from you, only people with **Write Settings** can revoke your tokens.

## The usage log {#usage}

**View Usage Log** in a row lists every call the token made, with the time, what was called and whether it worked. It answers whether a token is still in use. A call you do not recognise, or one at night when nobody works, is a reason to revoke the token.

## Examples

**A script for the order export.** You create Weekly order export with only the permission it needs and 90 days in **Expires In (days)**. You paste the token into the script and close the dialog.

**The add-in on a new PC.** You click **Create SolidWorks Add-in Token**, keep the values and paste the token into the add-in settings. It runs until the end of the year.

**A lost laptop.** You click **Revoke All**. Every program that used your tokens stops at once, and you create new tokens for the ones you still need.
