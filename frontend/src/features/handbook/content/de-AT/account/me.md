---
title: Mein Konto
summary: Wie du Namen, E-Mail, Foto, Datumsformat, Startseite und Aussehen änderst, wie du dein Passwort änderst und wohin deine Anmeldung für die Zeiterfassung kommt.
sourceRefs:
  - frontend/src/features/account/views/AccountMeView.vue
  - frontend/src/features/account/components/AccountPasswordDialog.vue
  - frontend/src/features/time-tracking/components/AccountTimeTrackingSection.vue
  - backend/src/modules/platform/application/use_cases/user/update_user.py
  - backend/src/modules/platform/application/use_cases/user/upload_user_avatar.py
lastVerified: 2026-11-10
---

Konto, **Mein Konto** enthält, was nur dir gehört: deinen Namen, dein Foto und wie Glados für dich aussieht und sich verhält. Änder die Felder, die du willst, und klick oben auf **Speichern**; für alle anderen ändert sich nichts. Auf dem Handy zeigt die Seite nur das Aussehen, der Rest wartet auf einen größeren Bildschirm.

## Profil und Foto {#profile}

Unter **Vollständiger Name** sehen dich Kolleginnen und Kollegen in Listen, Verläufen und Mails. **Benutzername** tippst du bei der Anmeldung ein, und an **E-Mail** schickt Glados deine Mails. **Foto hochladen** setzt das Bild neben deinem Namen, aus einer JPEG-, PNG-, WebP- oder GIF-Datei, und **Foto entfernen** nimmt es nach einer Rückfrage wieder weg. Ohne Foto zeigt Glados deine Initialen. Ist der Dateispeicher nicht aktiviert, sind beide Fotoschaltflächen deaktiviert, und ein Hinweis sagt warum.

## Datumsformat und Startseite {#regional}

**Datumsformat** legt fest, wie dir Datumsangaben angezeigt werden, und das Beispiel darunter zeigt den heutigen Tag in diesem Format. Uhrzeiten stehen immer im 24-Stunden-Format. **Startseite** ist die Seite aus der Seitenleiste, auf der du nach der Anmeldung landest.

## Das Aussehen {#look}

**Preset**, **Primärfarbe** und **Oberfläche** wählen die Farben von Glados, und **Dunkelmodus** schaltet auf einen dunklen Hintergrund. **Flache Schaltflächen**, **Tabellen-Gitternetzlinien** und **Tabellen-Zeilenfärbung** ändern, wie Schaltflächen und Tabellen aussehen, und die **Vorschau** daneben zeigt das Ergebnis, bevor du speicherst.

## Dein Passwort ändern {#password}

**Passwort ändern** öffnet einen Dialog mit **Aktuelles Passwort**, **Neues Passwort** und **Passwort bestätigen**. Dein aktuelles Passwort ist Pflicht, und die beiden neuen müssen gleich sein. Nach der Änderung enden alle deine anderen Sitzungen, und jedes vertrauenswürdige Gerät fragt wieder nach einem Code, wie [Sitzungen](/handbook/account/sessions#automatic) erklärt. Ein Konto aus dem Firmenverzeichnis zeigt stattdessen „Dein Passwort wird vom Verzeichnis verwaltet.“, weil sein Passwort dort geändert wird.

## Zeiterfassung {#time-tracking}

Ist die Zeiterfassung für diese Installation eingeschaltet, zeigt dein persönliches Konto hier auch einen Abschnitt für die Zeiterfassung. Du gibst Benutzername und Passwort deines Zeiterfassungskontos ein, bestätigst die Einwilligung und speicherst. [Zeiterfassung](/handbook/account/time-tracking) erklärt den Abschnitt und die Seite mit deinen Stunden.

## Beispiele

**Ein neuer Nachname.** Du änderst **Vollständiger Name** und klickst auf **Speichern**. Deine Kolleginnen und Kollegen sehen ab dann den neuen Namen.

**Ein dunklerer Bildschirm in der Halle.** Du schaltest **Dunkelmodus** ein, prüfst die **Vorschau** und klickst auf **Speichern**.

**Ein vergessenes altes Passwort.** Ohne **Aktuelles Passwort** kannst du es nicht ändern. Bitte eine Administration, dir ein neues zu setzen, das meldet dich überall ab.
