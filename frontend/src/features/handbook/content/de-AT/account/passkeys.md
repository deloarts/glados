---
title: Passkeys
summary: Wie du dich mit Windows Hello, Touch ID oder einem Sicherheitsschlüssel statt mit Passwort und Code anmeldest und wie du einen Passkey umbenennst oder entfernst.
sourceRefs:
  - frontend/src/features/auth/views/PasskeysView.vue
  - frontend/src/features/auth/utils/passkeySetup.ts
  - backend/src/modules/platform/application/use_cases/passkey/register_passkey.py
  - backend/src/modules/platform/application/use_cases/passkey/manage_passkeys.py
  - backend/src/modules/platform/domain/services/login_policy.py
lastVerified: 2026-11-10
---

Mit einem Passkey meldest du dich an, ohne Passwort und Zwei-Faktor-Code einzutippen. Dein Gerät bestätigt, dass du es bist, mit Windows Hello, Touch ID, einem Fingerabdruck oder einem Sicherheitsschlüssel, und Glados lässt dich hinein. Jedes Gerät hat seinen eigenen Passkey, und unter Konto, **Passkeys** siehst du alle deine.

## Einen Passkey hinzufügen {#add}

Klick auf dem Gerät, das du verwenden willst, auf **Passkey hinzufügen**. Glados schlägt einen **Name** wie Windows Hello vor, den du ändern kannst, und fragt nach deinem **Aktuelles Passwort**, um sicherzugehen, dass du es bist. Dann folgst du der Abfrage deines Geräts, etwa dem Fingerabdruckleser oder der PIN von Windows Hello. Der Passkey erscheint in der Liste mit **Dieses Gerät** daneben. Nach einer Anmeldung mit Passwort bietet Glados manchmal auch selbst an, einen Passkey für dieses Gerät einzurichten, und **Nicht jetzt** überspringt das.

**Passkey hinzufügen** ist deaktiviert und zeigt einen Hinweis, wenn der Browser keine Passkeys verwenden kann. Das passiert, wenn Glados nicht über https geöffnet ist, oder in einem Browser ohne Passkeys. Das Systemkonto kann gar keine Passkeys verwenden, weil sein Zwei-Faktor-Code Pflicht ist.

## Mit einem Passkey anmelden {#sign-in}

Klick auf der Anmeldeseite auf **Mit Passkey anmelden** und bestätige auf deinem Gerät. Wird die Abfrage abgebrochen oder der Passkey nicht angenommen, gib wie gewohnt dein Passwort ein. Ein Konto aus dem Firmenverzeichnis muss sich alle 30 Tage einmal mit seinem Passwort anmelden, damit ein im Verzeichnis gesperrtes Konto seinen Passkey nicht weiter verwenden kann.

## Die Liste {#list}

Jede Zeile zeigt den **Name**, wann der Passkey **Hinzugefügt** und wann er **Zuletzt verwendet** wurde. **Dieses Gerät** markiert den Passkey des Geräts, an dem du sitzt. **Synchronisiert** markiert einen Passkey, den dein Handy oder dein Passwortmanager auf deine anderen Geräte kopiert, sodass er auch dort funktioniert.

## Umbenennen und entfernen {#remove}

**Umbenennen** gibt einem Passkey einen klareren Namen, etwa Bürolaptop. **Entfernen** löscht einen Passkey, und dieses Gerät fragt wieder nach deinem Passwort. **Alle Passkeys entfernen** löscht alle Passkeys deines Kontos, der richtige Schritt, wenn ein Gerät verloren ist und du nicht sicher bist, welches.

## Beispiele

**Windows Hello im Büro.** Du klickst auf **Passkey hinzufügen**, behältst den Namen Windows Hello, gibst dein Passwort ein und bestätigst mit deiner PIN. Ab dann meldest du dich an diesem Computer mit **Mit Passkey anmelden** an.

**Ein verlorener Laptop.** Du öffnest **Passkeys** an einem anderen Computer und klickst beim Passkey des Laptops auf **Entfernen**. Der Laptop kommt ohne dein Passwort nicht mehr hinein.

**Ein neues Handy.** Dein Passkey zeigt **Synchronisiert**, also hat ihn dein neues Handy schon, sobald du dich dort in deinem Handykonto anmeldest. Hatte das alte Handy einen eigenen Passkey, entfernst du ihn.
