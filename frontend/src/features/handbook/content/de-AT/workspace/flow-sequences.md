---
title: Abläufe
summary: Wie ein Ablauf einer Maschine aus Schritten, Aktionen und Übergängen entsteht und als Diagramme mit geschätzter Taktzeit gelesen wird.
sourceRefs:
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - backend/src/modules/quality/domain/value_objects/sequence_content.py
  - backend/src/modules/quality/application/use_cases/sequence/save_sequence.py
  - frontend/src/features/sequences/utils/validation.ts
  - frontend/src/features/sequences/utils/suggestions.ts
lastVerified: 2026-11-10
---

Der Reiter **Abläufe** eines Produkts enthält seine Abläufe, etwa den Automatikzyklus und die Grundstellungsfahrt. Ein Ablauf sagt, was jedes Gerät in welchem Schritt tut, immer unter den aktuellen Gerätenamen, und Glados zeichnet daraus ein **Weg-Schritt-Diagramm** und ein **GRAFCET**. Wie ein Ablauf angelegt, freigegeben und überarbeitet wird, steht unter [Abläufe freigeben](/handbook/workspace/flow-sequence-release).

## Schritte und Aktionen

Ein Ablauf ist eine Liste nummerierter Schritte. **Schritt hinzufügen** hängt einen am Ende an, und **Schritt einfügen** zwischen zwei Schritten setzt einen dort ein. Die Aktionen eines Schritts starten gemeinsam, wenn der Schritt aktiv wird. Eine **Geräteaktion** fährt ein Gerät in eine Stellung seines Typs, mit einem Wert, wo die Stellung einen braucht. Eine Aktion nennt den SPS-Befehl, etwa Ausfahren, eine Bedingung die Stellung, etwa Ausgefahren. Ein Gerät, das sich mit einem anderen bewegt, ist ausgegraut, bewege also das antreibende Gerät. Eine **Textaktion** beschreibt in Worten, was außerhalb der Geräte passiert, etwa dass der Roboter ein Teil greift. Jede Aktion ist speichernd (S), kontinuierlich (N) oder ein Impuls (P) und kann vor dem Start auf eine Bedingung warten. Die optionale **Überwachungszeit** ist die Zeit, nach der die SPS einen Fehler meldet.

## Einen Schritt verlassen

Ein Schritt wird über seine Übergänge verlassen. **Weiter zu** nennt den nächsten Schritt, einen beliebigen anderen Schritt oder das **Ende des Ablaufs**. **Alternativer Zweig** ergänzt einen zweiten Weg, etwa Teil OK und Teil nicht OK, und dann braucht jeder Zweig eine Bedingung. Eine Bedingung besteht aus einem oder mehreren Teilen, die alle gelten müssen: ein Gerät **In Stellung**, ein **Wert** eines Geräts verglichen mit einer Schwelle, ein anderer Schritt **Schritt fertig**, die **Zeit im Schritt** und ein **Text** für alles außerhalb der Geräte, etwa Roboter bereit.

Unter jedem Übergang bietet **Vorschläge:** die Stellungen an, in die der Schritt seine Geräte fährt, und **Alle hinzufügen** übernimmt alle. So wartest du üblicherweise, bis eine Bewegung fertig ist. Ein Vorschlag mit Warnzeichen ist eine Stellung, die kein Sensor bestätigt, daher kann die SPS sie nicht prüfen.

Beim Bearbeiten zeigt ein Schritt rot, was das Speichern ablehnen würde, etwa einen fehlenden Wert. Er warnt außerdem, wenn zwei Zweige dieselbe Bedingung haben oder wenn ein Übergang auf ein Gerät in einer anderen Stellung wartet, als der Schritt es fährt.

## Grundstellung und Varianten

**Grundstellung** zeigt die Grundstellung jedes Geräts, die eine freigegebene Revision von ihrer Freigabe behält. Die **Varianten** des Produkts, etwa Schelle 60 und Schelle 80, können unter **Werte je Variante** eigene Werte bekommen; eine leere Variante verwendet den gemeinsamen Wert.

## Geschätzte Taktzeit

Jeder Schritt zeigt seine geschätzte Dauer aus den Verfahrzeiten der Geräte, den Zeiten seiner Aktionen, den Zeitbedingungen, auf die er wartet, und seiner **Erwartet**-Dauer. Ein Schritt, der auf eine **Text**-Bedingung wartet, braucht eine erwartete Dauer, sonst lautet die Summe „mindestens“. Die Infoleiste zeigt den Takt entlang des ersten Zweigs jedes Schritts, oder des Zweigs, den du mit dem Uhr-Knopf wählst, und den ungünstigsten Fall. **Zeitachse** macht die Spalten des Diagramms so breit wie ihre Dauer.

## Beispiele

**Ein einfacher Zyklus.** Schritt 1 wartet, bis B00 Taster Start in Stellung Gedrückt ist, die Schritte 2 bis 4 fahren Achse und Zylinder, und der letzte Schritt geht zu Schritt 1.

**Auf eine Bewegung warten.** Schritt 2 fährt B01 Hubzylinder P1 aus. **Vorschläge:** bietet den Zylinder in Ausgefahren an, und ein Klick lässt den Schritt warten, bis sein Sensor ihn draußen meldet.

**Ein Hub je Variante.** B02 Linearachse E1 fährt in Position, mit 120 mm für Schelle 60 und 160 mm für Schelle 80.
