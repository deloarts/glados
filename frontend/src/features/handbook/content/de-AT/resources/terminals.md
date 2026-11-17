---
title: Terminals
summary: Wie du einen Wandbildschirm einrichtest, freigibst, verortest und betreust, einzeln oder alle auf einmal, und was dir seine Details sagen.
sourceRefs:
  - backend/src/modules/operations/domain/services/terminal_rules.py
  - backend/src/modules/operations/domain/value_objects/terminal.py
  - backend/src/modules/operations/domain/value_objects/terminal_device_details.py
  - backend/src/modules/operations/application/use_cases/terminal/create_terminal_key.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_admin.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_bulk.py
lastVerified: 2026-11-10
---

Ein Terminal ist ein Fernseher an einem Raspberry Pi mit glados-terminal, der einen Infoscreen zeigt. Unter Ressourcen, **Terminals** listet die Tabelle die Bildschirme, die laufen. Die Liste und die Details darf jede und jeder ansehen. Für alle anderen Aktionen brauchst du **Terminals verwalten**, ohne die Berechtigung sind die Schaltflächen deaktiviert und zeigen einen Hinweis.

## Einen neuen Bildschirm einrichten {#setup}

Leg unter Einstellungen, **API-Schlüssel** einen Terminal-Schlüssel an. Trag den Schlüssel in die Einstellungen von glados-terminal auf dem Pi ein und starte es. Der Fernseher zeigt einen sechsstelligen Kopplungscode, und die Zahl an **Warten auf Freigabe** steigt. Gib den Bildschirm mit diesem Code frei und wähl seinen Infoscreen, dann wechselt der Fernseher in wenigen Sekunden.

## Der Terminal-Schlüssel {#terminal-key}

Klick auf **Terminal-Schlüssel erstellen** und gib dem Schlüssel einen **Name** und ein Datum unter **Läuft ab am**, das Pflicht ist, solange der Tab Sicherheit die Gültigkeit von Token begrenzt. Glados zeigt den Schlüssel nur einmal. Mit einem Schlüssel können sich beliebig viele neue Bildschirme anmelden, und ein freigegebener Bildschirm arbeitet weiter, wenn sein Schlüssel abläuft oder gesperrt wird.

## Einen Bildschirm freigeben {#approve}

**Warten auf Freigabe** listet die Bildschirme, die auf ihren Code warten. Klick auf **Freigeben**, tipp den **Kopplungscode** vom Fernseher ein, damit ist klar, dass du vor dem richtigen Bildschirm stehst, und gib ihm einen **Name**. **Standort** und **Bildschirm** sind optional. Ein Code gilt eine Stunde, und höchstens zwanzig Bildschirme können gleichzeitig warten.

## Einen Bildschirm betreuen

Mit der rechten Maustaste auf einen Bildschirm findest du seine Aktionen, oder du schaltest unter **Ansichten** **Aktionen anzeigen** ein und bekommst sie als Knöpfe. **Name und Standort bearbeiten** und **Bildschirm ändern** wirken sofort. **Neu laden** lässt den Fernseher seine Seite neu laden, und **Identifizieren** zeigt ein paar Sekunden lang Name und Standort. **Anzeige aus- oder einschalten** übersteuert die [Anzeigezeiten](/handbook/resources/display-schedule#override) seines Infoscreens, und die Spalte **Anzeige** zeigt, ob der Bildschirm an ist und bis wann. Ein Bildschirm, der sich fünf Minuten nicht meldet, gilt als **Offline**. Einen kurzen Text für viele Bildschirme auf einmal schickst du als [Nachricht an Terminals](/handbook/resources/terminal-messages).

## Details eines Bildschirms {#details}

Klick auf eine Zeile oder auf **Details**, um zu sehen, was der Bildschirm über seinen Computer, sein System und seinen Monitor gemeldet hat. **Unterspannung** deutet auf ein schwaches Netzteil hin. Adressen, Seriennummern, der Hostname und der Schlüssel-Fingerabdruck machen ein Gerät erkennbar, darum sehen sie nur Personen mit **Terminals verwalten**; für alle anderen stehen sie als **Verborgen** da.

## Sperren und löschen {#all}

**Sperren** hält einen Bildschirm sofort an, etwa wenn er gestohlen wurde. Läuft er weiter, zeigt er einen neuen Kopplungscode und braucht eine neue Freigabe. **Löschen** entfernt den Eintrag, und ein Bildschirm, der noch läuft, meldet sich als neuer wieder an.

**Alle Terminals** lädt alle freigegebenen Bildschirme neu, identifiziert oder sperrt sie, oder löscht alle Einträge, wartende und gesperrte eingeschlossen. Jede Rückfrage nennt, wie viele Bildschirme sie trifft, und bei **Alle sperren** und **Alle löschen** tippst du diese Zahl zuerst ein.

## Doppelte Nutzung und erlaubte Adressen {#allowlist}

**Doppelte Nutzung erkannt** erscheint, wenn sich derselbe Bildschirm von einer zweiten Adresse anmeldet, während seine erste Sitzung gültig ist, das deutet auf eine kopierte Speicherkarte hin. Sperr ihn, wenn du nicht weißt, warum. Unter Einstellungen, **Sicherheit** schaltet **Terminals** alle Bildschirme ab, und **Erlaubte IPs für Terminals** beschränkt ihre Adressen. Hinter einem Reverse Proxy leite zuerst die Adresse des Bildschirms weiter.

## Beispiele

**Ein neuer Bildschirm in der Halle.** Der Fernseher zeigt K7M2QX. Du öffnest **Warten auf Freigabe**, klickst auf **Freigeben**, tippst k7m2qx, nennst ihn Halle 1 Eingang, trägst den Standort Halle 1, über Tor 3 ein und wählst Hallentafel.

**Ein Bildschirm, der immer wieder neu startet.** Seine Details zeigen **Unterspannung** mit Ja, also tauschst du sein Netzteil.
