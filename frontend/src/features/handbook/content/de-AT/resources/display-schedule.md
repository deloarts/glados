---
title: Anzeigezeiten
summary: Wie sich die Wandbildschirme nachts, am Wochenende und an Feiertagen ausschalten, und wie du einen von Hand aus- oder einschaltest.
sourceRefs:
  - backend/src/modules/operations/domain/value_objects/display_schedule.py
  - backend/src/modules/operations/domain/services/display_power_rules.py
  - backend/src/modules/operations/application/services/display_calendar.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_admin.py
lastVerified: 2026-11-10
---

Wandbildschirme müssen nicht laufen, wenn niemand da ist. Jeder Infoscreen kann sagen, wann seine Bildschirme an sind, und jeder Bildschirm, der ihn zeigt, schaltet seinen Monitor innerhalb weniger Sekunden. Du kannst einen Bildschirm auch für eine Weile von Hand aus- oder einschalten.

## Die Zeiten eines Infoscreens festlegen {#schedule}

Unter Ressourcen, [Infoscreens](/handbook/resources/infoscreens) klickst du einen Infoscreen mit der rechten Maustaste an und wählst **Anzeigezeitplan**, oder du nimmst den Kalenderknopf seiner Zeile, wenn **Aktionen anzeigen** eingeschaltet ist. Dieselben Zeiten findest du auch im Editor des Infoscreens unter **Anzeigezeiten**. Die Spalte **Zeitplan** fasst die Zeiten jedes Infoscreens zusammen. Zum Ändern der Zeiten brauchst du **Infoscreens bearbeiten**, ohne die Berechtigung ist der Knopf deaktiviert und zeigt einen Hinweis.

Mit Haken bei **Immer an**, so ist es voreingestellt, schalten sich die Bildschirme nie nach Zeitplan aus. Nimmst du den Haken weg, erscheint ein Raster aus Wochentagen und halben Stunden, voreingestellt mit 06:00 bis 18:00 von Montag bis Freitag und freiem Wochenende. Die Bildschirme sind in den gefüllten halben Stunden an und sonst aus, gelesen in der Zeit dieser Installation. Klick auf eine halbe Stunde, um sie zu schalten, oder zieh über mehrere Tage und Stunden, um den ganzen Block zu füllen oder zu leeren, je nachdem, wie die erste halbe Stunde war. Ein Klick auf einen Wochentag schaltet den ganzen Tag, ein Klick auf eine Uhrzeit diese halbe Stunde an jedem Tag. **Montag auf Werktage kopieren** gibt Dienstag bis Freitag die Zeiten vom Montag, und **Alle an** und **Alle aus** füllen oder leeren die Woche.

Ein Tag kann in höchstens sechs getrennten Abschnitten an sein. Ein Tag mit mehr wird rot markiert und lässt sich erst speichern, wenn du einige zusammenlegst.

## Feiertage

**An Feiertagen ausschalten** hält die Bildschirme an jedem Feiertag, der unter Ressourcen, [Feiertage](/handbook/resources/holidays) steht, den ganzen Tag aus. Das geht mit oder ohne feste Zeiten, so wird auch ein Infoscreen, der Tag und Nacht läuft, zu Weihnachten dunkel.

## Einen Bildschirm von Hand schalten {#override}

Unter Ressourcen, [Terminals](/handbook/resources/terminals) klickst du einen Bildschirm mit der rechten Maustaste an und wählst **Anzeige aus- oder einschalten**, oder du nimmst den Knopf neben **Neu laden**, wenn **Aktionen anzeigen** eingeschaltet ist. Wähl **Ausschalten** oder **Einschalten** und wie lange. Voreingestellt gilt es bis zur nächsten Änderung der Anzeigezeiten, ein am Abend eingeschalteter Bildschirm folgt also am nächsten Morgen wieder seinem Zeitplan. Du kannst auch Datum und Uhrzeit innerhalb der nächsten 31 Tage wählen. **Zurück zu den Anzeigezeiten** beendet das Schalten von Hand sofort. Die Spalte **Anzeige** zeigt das Schalten von Hand mit seinem Ende. Dafür brauchst du **Terminals verwalten**, ohne die Berechtigung ist der Knopf deaktiviert und zeigt einen Hinweis.

## Was der Bildschirm tut

Ein ausgeschalteter Bildschirm schaltet sein Bild ab, und ein Fernseher, der auf Fernsteuerung über HDMI hört, geht zusätzlich in Bereitschaft. Ein Bildschirm, der Glados nicht erreicht, behält seinen letzten Zustand, und einer, der startet, bleibt an, bis er von Glados hört. Ein Bildschirm, der auf Freigabe wartet oder gesperrt ist, bleibt an.

## Beispiele

**Bürozeiten.** Du öffnest **Anzeigezeitplan** bei Hallentafel, nimmst den Haken bei **Immer an** weg und behältst 06:00 bis 18:00 an Werktagen. Die Bildschirme werden um sechs Uhr abends dunkel und gehen um sechs Uhr früh wieder an.

**Zwei Schichten.** Du ziehst am Montag von 05:30 bis 22:00 und klickst **Montag auf Werktage kopieren**. Am Samstag ziehst du von 06:00 bis 12:00, und Sonntag bleibt aus.

**Besuch am Abend.** Um 19:00 wählst du bei Halle 1 Eingang **Einschalten**. Er bleibt an, bis ihn der Zeitplan am nächsten Morgen um 06:00 ohnehin einschaltet, und folgt dann wieder seinen Zeiten.
