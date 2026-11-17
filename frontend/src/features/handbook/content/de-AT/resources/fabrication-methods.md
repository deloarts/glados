---
title: Fertigungsmethoden
summary: Was eine Fertigungsmethode ist, was jede ihrer Einstellungen bei Planung und Bestellung bewirkt und wie die Reihenfolge der Liste funktioniert.
sourceRefs:
  - backend/src/modules/catalogue/application/use_cases/fabrication_method/update_fabrication_method.py
  - backend/src/modules/catalogue/application/use_cases/fabrication_method/_assembly_default.py
  - backend/src/modules/catalogue/domain/services/fabrication_method_rules.py
  - backend/src/modules/catalogue/domain/services/label_name_rules.py
  - backend/src/modules/catalogue/application/services/catalogue_list_order.py
lastVerified: 2026-11-10
---

Eine Fertigungsmethode ist eine Art von Arbeit, die ein Fertigungsteil durchläuft, etwa Laserschneiden, Drehen, Schweißen oder Montage. Jeder Schritt im Ablauf eines Teils verwendet eine Methode, Maschinen führen die Methoden, die sie können, und die Planung entscheidet damit, welche Maschine einen Auftrag übernehmen kann. Die Liste findest du unter Ressourcen, **Fertigungsmethoden**.

## Name, Beschreibung und Farben

Jede Methode hat einen **Name** und eine **Beschreibung** in jeder Sprache der Oberfläche. Der Name ist in der Standardsprache Pflicht und darf bis zu 200 Zeichen lang sein. Zwei Methoden, die nicht archiviert sind, dürfen in derselben Sprache nicht denselben Namen zeigen, Groß- und Kleinschreibung egal. **Label-Farbe** und **Schriftfarbe** legen fest, wie die Methode als Label erscheint, und die **Vorschau** zeigt das Ergebnis.

## Maschine oder Handarbeit

**Benötigt eine Maschine** ist bei neuen Methoden angehakt. Nimm den Haken weg, wenn es reine Handarbeit ist, etwa Entgraten von Hand. Ein Schritt mit so einer Methode bekommt nie eine Maschine oder einen Pool und wird im Standardkalender geplant.

**Üblicherweise extern** kennzeichnet Arbeit, die du meist an einen Lieferanten gibst. Das ist nur ein Hinweis: Du kannst so einen Schritt trotzdem einer internen Maschine zuweisen, und die Oberfläche warnt dich dabei. Sobald der Haken gesetzt ist, erscheint **Lieferzeit (Tage)**. Das Feld ist optional und sagt in Kalendertagen vorher, wann die Arbeit zurückkommt. Bleibt es leer, gilt die **Standard-Vorlaufzeit extern (Tage)** aus den Produktionseinstellungen, und ein Lieferant mit eigener Lieferzeit hat immer Vorrang. Auch **Standardlieferant** ist optional und füllt den Lieferanten vor, wenn du eine Bestellung für einen Schritt mit dieser Methode anlegst.

## Standard für Baugruppen

**Standard für Baugruppen** kennzeichnet die Methode, die das SolidWorks-Add-in vorauswählt, wenn es den Ablauf einer Baugruppe aufbaut. Nur eine Methode kann das sein, wenn du den Haken hier setzt, verliert ihn die Methode, die ihn bisher hatte. Eine archivierte Methode kann ihn nicht haben, und archivierst du die Methode mit dem Haken, gibt es danach keinen Standard.

## Die Liste verwalten

Zum Anlegen, Bearbeiten, Verschieben, Archivieren und Wiederherstellen von Methoden brauchst du die Berechtigung **Fertigungsmethoden schreiben**. Ohne sie sind die Schaltflächen deaktiviert. Methoden werden archiviert, nicht gelöscht, damit bestehende Schritte ihre behalten. **Archivierte anzeigen** listet sie wieder auf, und das Wiederherstellen wird abgelehnt, solange eine aktive Methode denselben Namen trägt. In der Tabelle zeigt die Spalte **Maschine** bei Handarbeit Manuell, und **Merkmale** zeigt Extern, Baugruppen-Standard und Archiviert. Nach jeder gespeicherten Änderung wird der Zeitplan neu berechnet, weil Lieferzeiten die externen Schritte terminieren.

In der Reihenfolge der Liste bieten die Auswahlfelder die Methoden an. Darfst du Fertigungsmethoden bearbeiten, zeigt die erste Spalte in jeder Zeile einen Griff. Halt den Griff fest und zieh die Zeile an ihren neuen Platz; eine Linie zeigt, wo sie landet. Der Griff erscheint nur, solange keine Sortierung, Suche und kein Filter aktiv ist, weil die Zeilen dann in einer anderen Reihenfolge stehen. Neue Methoden kommen ans Ende.

## Beispiele

**Eine Maschinenmethode.** Leg Laserschneiden an, lass **Benötigt eine Maschine** angehakt und nimm die Methode in die Fähigkeiten deines Lasers auf. Schritte mit dieser Methode lassen sich jetzt auf dieser Maschine planen.

**Extern beschichten.** Leg Pulverbeschichten an, hak **Üblicherweise extern** an, trag 10 bei **Lieferzeit (Tage)** ein und wähl deinen Beschichter als **Standardlieferant**. Ein Beschichtungsschritt wird zehn Tage nach dem Versand zurückerwartet, und seine Bestellung startet mit diesem Lieferanten.

**Montage von Hand.** Leg Montage an, nimm den Haken bei **Benötigt eine Maschine** weg und hak **Standard für Baugruppen** an. Das Add-in wählt die Methode jetzt für Baugruppen vor, und diese Schritte werden ohne Maschine geplant.
