---
title: Benachrichtigungen und Berechtigungen
summary: Was dir die Benachrichtigungen deines Kontos sagen, wie du sie als gelesen markierst und wie du siehst, welche Berechtigungen du hast.
sourceRefs:
  - frontend/src/features/account/views/AccountNotificationsView.vue
  - frontend/src/features/notifications/components/NotificationPanel.vue
  - backend/src/modules/platform/application/use_cases/notification/handle_event_notifications.py
  - frontend/src/features/account/views/AccountPermissionsView.vue
  - frontend/src/shared/utils/permissionGroups.ts
lastVerified: 2026-11-10
---

Glados sagt dir Bescheid, wenn etwas passiert, das dich betrifft, etwa wenn eine Bestellung von dir storniert oder dir ein Projekt zugewiesen wird. Diese Benachrichtigungen erscheinen bei der Glocke oben auf jeder Seite und im Konto-Tab **Benachrichtigungen**. Der Konto-Tab **Berechtigungen** daneben zeigt, was du in Glados darfst.

## Deine Benachrichtigungen {#notifications}

Die Zahl an der Glocke zählt die Benachrichtigungen, die du noch nicht gelesen hast. Glados schaut jede Minute nach neuen, darum kann eine Benachrichtigung einen Moment brauchen. Klick auf die Glocke für die neuesten, oder öffne Konto, **Benachrichtigungen** für die ganze Liste. Jeder Eintrag zeigt einen Titel, eine kurze Nachricht und wann es passiert ist, und ein ungelesener trägt einen Punkt. Klick auf einen Eintrag, um ihn als gelesen zu markieren, oder auf **Alle als gelesen markieren**, um den Punkt bei allen auf einmal zu entfernen.

**Nach Datum filtern** schränkt die Liste auf einen Zeitraum ein, und **Zurücksetzen** zeigt wieder alles. **Synchronisieren** lädt neue Benachrichtigungen, ohne auf die nächste Minute zu warten.

## Worüber du Bescheid bekommst {#kinds}

Benachrichtigungen kommen aus der Arbeit, an der du beteiligt bist. Du erfährst, wenn eine Bestellung oder ein Bedarf von dir storniert wird, wenn gelieferte Teile zurückgewiesen werden, wenn ein Teil, auf das du wartest, geliefert ist, und wenn ein Los verkürzt endet oder Teile verschrottet werden. Du erfährst auch, wenn dir ein Projekt oder Produkt zugewiesen wird und wenn jemand ein Dokument übernimmt, das du bearbeitet hast, deine Bearbeitung beendet oder eine Revision als ungültig markiert. Erwähnt dich jemand in einer Besprechung oder macht dich für eine Aufgabe zuständig, wartet Glados fünf Minuten und fasst dann in einer Benachrichtigung zusammen, was dich in dieser Besprechung betrifft, etwa „Jonas hat dich in MTG-26-0021 zweimal erwähnt und dir 2 Aufgaben zugewiesen“. Ein Klick darauf öffnet die Besprechung. Auch Änderungen an deinem eigenen Konto erscheinen, etwa geänderte Berechtigungen oder eine Abmeldung durch eine Administration. Je nachdem, wie der Mailversand eingerichtet ist, kommen manche davon auch als Mail.

## Deine Berechtigungen {#permissions}

Konto, **Berechtigungen** listet jede Berechtigung von Glados in Gruppen wie Bestellungen, Fertigungslose oder Drucken. Eine Berechtigung, die du hast, zeigt ein grünes Häkchen, eine, die du nicht hast, ist ausgegraut und trägt ein Schloss. Jede Zeile nennt die Berechtigung so, wie sie überall sonst heißt, etwa **Bestellungen schreiben**, und sagt in einem Satz, was sie erlaubt. Die Liste enthält auch, was du über eine Benutzergruppe bekommst, sie zeigt also vollständig, was du darfst. Das Systemkonto hat jede Berechtigung, und der Tab sagt das oben.

Deine Berechtigungen kann nur eine Administration ändern. Passiert das, bekommst du eine Benachrichtigung, und Schaltflächen, die du vorher nicht verwenden konntest, werden aktiv. Eine Schaltfläche, für die dir die Berechtigung fehlt, bleibt sichtbar, ist aber deaktiviert, und ihr Tooltip nennt meist die Berechtigung.

## Beispiele

**Eine stornierte Bestellung.** Die Glocke zeigt 1. Du klickst darauf, liest, dass deine Bestellung storniert wurde, und der Punkt verschwindet.

**Ein Blick auf letzte Woche.** Unter **Benachrichtigungen** wählst du bei **Nach Datum filtern** Montag bis Freitag der letzten Woche und siehst nur die Benachrichtigungen dieser Tage.

**Eine deaktivierte Schaltfläche.** **Token erstellen** ist bei dir ausgegraut. Unter **Berechtigungen** siehst du ein Schloss bei der Token-Berechtigung und fragst eine Administration danach.
