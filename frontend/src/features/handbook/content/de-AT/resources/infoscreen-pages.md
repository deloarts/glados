---
title: Infoscreen-Seiten und Widgets
summary: Wie die Seiten eines Infoscreens aufgebaut sind, was Kopf- und Fußzeile zeigen und was jedes Widget anzeigt.
sourceRefs:
  - backend/src/modules/operations/domain/value_objects/infoscreen.py
  - backend/src/modules/operations/domain/services/infoscreen_rules.py
  - backend/src/modules/operations/application/use_cases/infoscreen/get_infoscreen_feed.py
  - backend/src/read/application/use_cases/infoscreen/build_infoscreen_feed.py
lastVerified: 2026-11-10
---

Was ein [Infoscreen](/handbook/resources/infoscreens) zeigt, legst du in seinem Editor fest, den du unter Ressourcen, **Infoscreens** mit **Bearbeiten** in einer Zeile öffnest. Dort bestimmt **Kopf- und Fußzeile** die Leisten um die Seiten und **Seiten**, was jede Seite zeigt. Zum Ändern brauchst du **Infoscreens bearbeiten**; ohne die Berechtigung zeigt der Editor den Infoscreen nur an.

## Kopf- und Fußzeile {#bars}

**Kopfzeile anzeigen** setzt eine Leiste über die Seiten und ist bei einem neuen Infoscreen an; **Fußzeile anzeigen** setzt eine darunter und ist aus. Jede Leiste hat drei Bereiche, **Links**, **Mitte** und **Rechts**. Ein Bereich zeigt Elemente wie das Logo, den Namen des Infoscreens, die Uhr, das Datum, den nächsten Feiertag oder einen eigenen Text. Füg ein Element aus der Liste unter einem Bereich hinzu und verschieb es mit den Pfeilen. Jedes Element kannst du pro Leiste einmal verwenden, und der eigene Text braucht seinen Text. Ein neuer Infoscreen hat links das Logo und den Namen und rechts die Uhr.

## Seiten und Layouts {#pages}

Jede Seite hat ein **Layout** mit einer bis sechs Positionen, von Ganzer Bildschirm mit einem Widget bis zu den beiden Rastern mit sechs Feldern. Raster mit sechs Feldern, hoch passt zu einem hochkant gedrehten Fernseher. Wähl für jede Position ein Widget oder lass sie Leer. Wenn du das Layout wechselst, bleiben die Widgets, die noch Platz haben, und der Rest fällt weg. Mit den Pfeilen änderst du die Reihenfolge der Seiten, und ein Infoscreen hat eine bis zwanzig Seiten.

## Widgets für die Werkstatt {#widgets}

Jedes Widget kann einen **Titel** haben. Die **Maschinentafel** zeigt, was auf den gewählten Maschinen und auf allen Maschinen der gewählten Pools läuft, gefolgt von den **Nächste Aufträge pro Maschine**, und fügt für jeden Pool eine Zeile mit den Aufträgen hinzu, die noch keine Maschine haben. Die **Maschinenansicht** zeigt eine **Maschine** ganz: den Auftrag, der gerade darauf läuft, oder den nächsten, mit großem Bild, der Zeichnung, wenn du **Zeichnung zeigen** anhakst, den Artikeldaten und den folgenden Aufträgen. **Fällige Lose** listet die Lose, die innerhalb der **Tage voraus** fällig sind, überfällige zuerst und als verspätet markiert, und **Verspätete Lose** listet die Lose, deren Termin vorbei ist. Beide verbergen Kundennamen, außer du hakst **Kundennamen anzeigen** an. **QS-Warteschlange** zeigt, was auf die Prüfung wartet. **Erwartete Lieferungen** listet, was in den nächsten Tagen kommen soll, und mit **Überfällige Lieferungen zuerst zeigen** auch, was schon da sein sollte.

## Weitere Widgets {#other-widgets}

**Aktuelle Produkte** listet die aktiven Produkte, mit ihren Projekten, wenn du **Projekte je Produkt zeigen** anhakst, und **Aktuelle Projekte** listet die aktiven Projekte. **Wetter** zeigt das Wetter jetzt und für die **Tage voraus** in einem Ort, den du über **Land** und **Ort** wählst. Nur der Ort geht an den Wetterdienst, und ein Admin kann das Wetter unter Einstellungen, **Sicherheit** ausschalten. **Nachricht** zeigt deinen eigenen Text in einem **Stil** wie Warnung, oder Keiner für schlichten Text. Er kann Markdown für fett, kursiv, Überschriften und Listen verwenden, und **Textposition** setzt ihn an eine von neun Stellen. **Uhr** zeigt die Uhrzeit als Uhr im Stil **Digital**, **Analog** oder **Bit (binär)**, auf Wunsch mit Datum, nächstem Feiertag und Sekunden.

## Beispiele

**Eine Hallentafel.** Du legst Hallentafel mit dem Layout Hauptbereich und Seitenleiste an, mit einer Maschinentafel für den Fräspool im Hauptbereich und einer Uhr in der Seitenleiste. Im Tab Terminals weist du sie Halle 1 Eingang zu.

**Ein Infoscreen an einer Maschine.** Du gibst einem Infoscreen eine Seite mit dem Layout Ganzer Bildschirm und einer Maschinenansicht des Lasers und hakst **Zeichnung zeigen** an. Der Bildschirm neben dem Laser zeigt die Zeichnung des laufenden Auftrags und was als Nächstes kommt.
