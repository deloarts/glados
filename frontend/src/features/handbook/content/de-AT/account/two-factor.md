---
title: Zwei-Faktor-Authentifizierung
summary: Wie du dein Konto mit einem Code aus einer Authenticator-App schützt, wie du das wieder ausschaltest und wann Glados es verlangt.
sourceRefs:
  - frontend/src/features/auth/views/TwoFactorView.vue
  - backend/src/modules/platform/application/use_cases/user/enroll_totp.py
  - backend/src/modules/platform/application/use_cases/user/confirm_totp_enrollment.py
  - backend/src/modules/platform/application/use_cases/user/disable_totp.py
  - backend/src/modules/platform/domain/services/login_policy.py
lastVerified: 2026-11-12
---

Die Zwei-Faktor-Authentifizierung verlangt bei jeder Anmeldung nach deinem Passwort einen sechsstelligen Code aus einer App auf deinem Handy. Wer dein Passwort kennt, kommt trotzdem ohne dein Handy nicht hinein. Du richtest sie unter Konto, **2-Faktor-Auth** ein, und das Etikett neben dem Titel sagt, ob sie **Aktiviert** oder **Deaktiviert** ist.

## Einschalten {#enable}

Du brauchst eine Authenticator-App auf deinem Handy, etwa Google Authenticator, Microsoft Authenticator oder Authy. Klick auf **2FA aktivieren**, gib dein **Aktuelles Passwort** ein und klick auf **Weiter**, und Glados zeigt einen QR-Code. Das Passwort hält jemanden, der deine Sitzung offen vorfindet, davon ab, sein eigenes Handy in dein Konto einzutragen. Verlangt Glados die Einrichtung bei der Anmeldung, hast du dein Passwort gerade eingegeben und wirst nicht noch einmal gefragt. Scann ihn mit der App, die dann alle 30 Sekunden einen neuen Code zeigt. Kannst du nicht scannen, tipp stattdessen den **Manueller Eingabeschlüssel** in die App. Gib den aktuellen Code unter **Bestätigungscode** ein, und die Zwei-Faktor-Authentifizierung ist an, sobald die sechste Ziffer drin ist. Ein falscher oder veralteter Code wird abgelehnt, also wart auf den nächsten und versuch es noch einmal. **Abbrechen** beendet die Einrichtung, und nichts ändert sich.

Für ein neues Handy schaltest du sie aus und richtest sie mit dem neuen Handy wieder ein.

## Mit Code anmelden {#sign-in}

Nach deinem Passwort fragt Glados nach dem **Authentifizierungscode** aus der App. Du kannst **Auf diesem Gerät 30 Tage nicht mehr fragen** anhaken, mit der Zahl der Tage, die eine Administration festgelegt hat, dann überspringt dieser Browser den Code, bis das Vertrauen abläuft. Diese Browser stehen als vertrauenswürdige Geräte unter [Sitzungen](/handbook/account/sessions#devices). Ein [Passkey](/handbook/account/passkeys) überspringt Passwort und Code.

## Ausschalten {#disable}

Klick auf **2FA deaktivieren**, gib den aktuellen **Authentifizierungscode** aus der App ein, und der Schutz ist aus. Gleichzeitig werden alle vertrauenswürdigen Geräte entfernt. Verlangt eine Administration die Zwei-Faktor-Authentifizierung für alle, oder hast du **Einstellungen schreiben**, wirst du bei der nächsten Anmeldung gebeten, sie wieder einzurichten.

## Wann sie Pflicht ist {#required}

Eine Administration kann die Zwei-Faktor-Authentifizierung unter Einstellungen, **Sicherheit** für alle Konten verlangen. Konten mit **Einstellungen schreiben** brauchen sie immer. Auch das Systemkonto braucht sie und kann sie nicht ausschalten; nur eine Administration am Server kann sie zurücksetzen.

## Beispiele

**Einrichten.** Du klickst auf **2FA aktivieren**, scannst den Code mit Microsoft Authenticator und tippst die sechs Ziffern ein, die die App zeigt. Das Etikett wechselt auf **Aktiviert**, und deine nächste Anmeldung verlangt einen Code.

**Ein neues Handy.** Bevor du das alte Handy abgibst, klickst du auf **2FA deaktivieren** und gibst seinen Code ein. Dann klickst du auf **2FA aktivieren** und scannst den neuen QR-Code mit dem neuen Handy.

**Ein abgelehnter Code.** Du tippst einen Code genau in dem Moment, in dem die App ihn wechselt. Glados meldet einen ungültigen Code, und du gibst den nächsten ein.
