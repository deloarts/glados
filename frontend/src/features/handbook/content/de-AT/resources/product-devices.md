---
title: Gerätelisten
summary: Die Listen, aus denen jedes Produktgerät wählt, und die SPS-Umgebungen, die seine Variablen benennen und exportieren.
sourceRefs:
  - backend/src/modules/workspace/domain/services/product_device_resource_rules.py
  - frontend/src/features/product-devices/views/ProductDeviceResourcesView.vue
  - backend/src/modules/workspace/domain/services/plc_environment_rules.py
  - backend/src/modules/workspace/application/use_cases/plc_environment/environments.py
  - backend/src/modules/workspace/application/use_cases/product_device_resource/options.py
  - backend/src/modules/workspace/application/use_cases/product_device_resource/kinds.py
lastVerified: 2026-11-10
---

Ressourcen, **Produktgeräte** enthält die Listen, aus denen die Geräte jedes Produkts wählen. Sie gelten für alle Maschinen und werden archiviert statt gelöscht, weil bestehende Geräte und Abläufe auf sie verweisen. Wie die eigenen Geräte eines Produkts benannt und verfolgt werden, steht unter [Produktgeräte](/handbook/workspace/product-devices).

## Arbeiten mit den Listen {#lists}

Der Reiter erscheint nur, solange **Geräte** unter Einstellungen, **Funktionen** eingeschaltet ist. Der Umschalter über der Tabelle wählt die Liste, und jede Liste hat ihre eigene Schaltfläche zum Anlegen, etwa **Neuer Gerätetyp**. Ein Rechtsklick auf eine Zeile bietet Bearbeiten, **Archivieren** und **Wiederherstellen**, und **Archivierte anzeigen** listet archivierte Einträge wieder auf.

Anlegen, Bearbeiten, Archivieren und Wiederherstellen braucht **Gerätelisten schreiben**. Ohne sie sind die Schaltflächen und Menüeinträge deaktiviert, und ein Menüeintrag nennt die Berechtigung, die dir fehlt.

Darfst du diese Listen bearbeiten, ziehst du eine Zeile am Griff in ihrer ersten Spalte an ihren neuen Platz. Die Auswahlfelder im Geräteformular und im Ablaufeditor bieten die Einträge für alle Benutzer in dieser Reihenfolge an, also stell die meistverwendeten nach oben. SPS-Umgebungen haben keine Reihenfolge.

## Antriebsarten

Eine Antriebsart, etwa Pneumatik oder Elektrik, hat eine Bezeichnung und unter **Buchstabe** ein bis vier Großbuchstaben, die in jeden Gerätenamen eingehen. Sobald ein Gerät sie verwendet, lässt sich der Buchstabe nicht mehr ändern, weil jeder Plan den alten tragen würde.

## Gerätetypen und Stellungen

Ein Typ, etwa Zylinder oder Sauggreifer, listet die **Stellungen**, in denen seine Geräte sein können, die **Signale**, die sie daneben üblicherweise haben, etwa einen Störungseingang, und ihre **Technische Parameter**. Eine Stellung **Mit Wert**, etwa eine Achsposition in mm, bekommt ihren Wert im Ablauf. **SPS-Zustand** und **SPS-Befehl** sind optional; sie beenden die Variablen der Eingänge, die die Stellung bestätigen, und der Ausgänge, die in sie fahren, etwa Ausgefahren und Ausfahren. Hake **Ohne Antriebsart** für Bediengeräte wie Taster und Schlüsselschalter an, deren Namen keinen Buchstaben tragen.

## Komponentenrollen, Energieverhalten und Ablaufnamen

**Komponentenrollen** sind die Teile, die ein Gerät haben kann, etwa Ventil oder Sensor. **Energieverhalten** beantwortet, was ein Gerät tut, wenn seine Energie ausfällt oder wiederkommt. **Ablaufnamen** werden beim Anlegen eines Ablaufs vorgeschlagen; ein Ablauf behält seinen Namen als freien Text.

## SPS-Umgebungen {#plc-environments}

Eine SPS-Umgebung, etwa Siemens TIA Portal, legt fest, wie die Variablen einer Maschine benannt und exportiert werden. **Präfixe** bestimmen den Anfang einer Variable je Signaltyp, mit eigenen für Sicherheitssignale. **Zeichenumwandlung** macht aus dem Gerätenamen eine gültige Variable. **Maximale Variablenlänge** ist die Grenze, ab der gewarnt wird. **Variablentabelle**, **Variablentabelle für Sicherheitssignale**, **Name des Tabellenblatts** und die Exportspalten formen die Excel-Datei. Ein Produkt wählt seine Umgebung in seinem Formular; Produkte ohne eigene verwenden die Umgebung, die als **Standard** markiert ist.

Um eine Umgebung in eine andere Installation mitzunehmen, öffne sie und verwende die Schaltflächen unten im Dialog. **In Datei exportieren** speichert das Formular in eine Glados-Vorlagendatei. **Aus Datei importieren** füllt das Formular aus so einer Datei und nennt die Werte, die es nicht verwendet hat. Der Import lässt das Häkchen bei **Standard** unverändert und gilt erst, wenn du auf **Speichern** klickst.

## Beispiele

**Ein neuer Typ.** Du legst Linearachse mit den Stellungen Grundstellung und Position an, die zweite mit einem Wert in mm und dem SPS-Befehl Fahren. Jedes Achsgerät bietet dann beide Stellungen, und seine Ausgangsvariable endet auf Fahren.

**Eine zweite SPS-Marke.** Du legst nach dem Vorbild der TIA-Umgebung eine neue mit anderen Präfixen und einer kürzeren **Maximale Variablenlänge** an und wählst sie bei den Produkten für diesen Kunden.
