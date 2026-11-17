---
title: Zeiterfassung
summary: Wie du dein Zeiterfassungskonto mit Glados verbindest, was die Seite Zeiterfassung über deine Stunden zeigt und was Glados davon behält.
sourceRefs:
  - frontend/src/features/time-tracking/views/AccountTimeTrackingView.vue
  - frontend/src/features/time-tracking/components/AccountTimeTrackingSection.vue
  - frontend/src/features/time-tracking/components/TimeTrackingConsentDialog.vue
  - backend/src/modules/operations/application/use_cases/time_tracking/save_my_time_tracking_credentials.py
  - backend/src/modules/operations/application/use_cases/time_tracking/check_my_time_tracking_access.py
  - backend/src/modules/operations/application/use_cases/time_tracking/get_my_time_tracking_month.py
lastVerified: 2026-11-10
---

Glados kann dir neben deiner Arbeit die Stunden zeigen, die das Zeiterfassungssystem deiner Firma für dich erfasst hat. Der Konto-Tab **Zeiterfassung** erscheint nur, wenn eine Administration die Zeiterfassung eingeschaltet hat, und nur für dein persönliches Konto; geteilte Konten und das Systemkonto können sie nicht verwenden. Niemand sonst sieht deine Zeitdaten, auch keine Administration.

## Dein Konto verbinden {#connect}

Der Abschnitt Zeiterfassung unter [Mein Konto](/handbook/account/me#time-tracking) nimmt den Benutzernamen und das Passwort, die du im Zeiterfassungssystem verwendest. Klick oben auf der Seite auf **Speichern**. Beim ersten Mal, und immer wenn sich der Text ändert, fragt Glados nach deiner Einwilligung: Es liest deine Zeitdaten nur, während du die Seite öffnest, behält nichts davon und speichert dein Passwort versiegelt, sodass Glados selbst es nicht lesen kann. Hak an, dass du einverstanden bist, und klick auf **Bestätigen**. **Zugriff prüfen** zeigt dann, als wer du angemeldet bist und ob du **Einzelne Tage**, den **Monat** und das **Jahr** lesen darfst.

Sagt der Abschnitt, dass deine gespeicherte Anmeldung nicht mehr funktioniert, etwa nach einer Passwortänderung im Zeiterfassungssystem, gib das Passwort neu ein und speichere. **Einwilligung bestätigen** erscheint, wenn sich nur der Text der Einwilligung geändert hat. Entfernst du die Zugangsdaten, entfernst du auch deine Einwilligung, und die Seite Zeiterfassung bleibt leer, bis du sie wieder eingibst.

## Dein Monat {#month}

Die Seite Zeiterfassung öffnet mit dem aktuellen Monat. Die Pfeile wechseln zum Monat davor oder danach, **Aktueller Monat** kommt zurück, und **Neu laden** holt die Daten neu. Zukünftige Monate lassen sich nicht anzeigen. Die Karte **Überblick** zeigt, ob du **Eingestempelt** oder **Ausgestempelt** bist, dein **Erstes Kommen** heute, was du bisher gearbeitet hast, die Sollzeit heute, deinen Tages- und laufenden Saldo und wann du die Sollzeit erreichst. **Konten** listet die Salden deiner Zeitkonten für den Monat.

Die Tabelle listet jeden Tag mit **Schicht**, **Kommen**, **Gehen**, **Gearbeitet**, **Soll**, **Tagessaldo** und **Laufender Saldo**, und **Buchungen anzeigen** listet jedes Kommen und Gehen. **Status** kennzeichnet einen Tag als **Normal**, **Schichtfrei**, **Feiertag**, **Abwesenheit** oder **Offen**. Diagramme darunter vergleichen die gearbeiteten Stunden mit dem Soll pro Tag und pro Wochentag, und der Jahresabschnitt zeigt auf Wunsch das ganze Jahr nach Monaten.

## Beispiele

**Einrichten.** Du öffnest **Mein Konto**, tippst Benutzername und Passwort deiner Zeiterfassung ein und klickst auf **Speichern**. Du bestätigst die Einwilligung, klickst auf **Zugriff prüfen** und siehst deinen Namen mit **Monat** und **Jahr** erlaubt.

**Den Saldo prüfen.** Am Freitagnachmittag öffnest du **Zeiterfassung** und liest im **Überblick**, wann du die heutige Sollzeit erreichst.

**Nach einem neuen Passwort.** Du hast dein Passwort im Zeiterfassungssystem geändert, und die Seite bittet dich, deine Zugangsdaten neu einzugeben. Du öffnest **Mein Konto**, tippst das neue Passwort ein und speicherst.
