---
title: Bedarfe aus einer Tabelle anlegen
summary: Wie die Stapelerstellung aus einer Excel-Tabelle viele Zukaufteile- oder Fertigungsteile-Bedarfe macht, wie jede Zeile ihren Artikel und ihr Projekt findet und was die Status der Prüfung bedeuten.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/batch_demands.py
  - backend/src/modules/fulfillment/application/services/batch_demand_import.py
  - backend/src/modules/fulfillment/application/use_cases/bought_item_demand/batch_demand_items.py
  - backend/src/modules/fulfillment/application/use_cases/made_item_demand/batch_demand_items.py
  - frontend/src/shared/demand-import/components/DemandImportDialog.vue
  - frontend/src/shared/demand-import/stores/createDemandImportDraftStore.ts
lastVerified: 2026-11-12
---

**Stapelerstellung** in den Listen **Zukaufteile Bedarf** und **Fertigungsteile Bedarf** legt für jede Zeile einer Excel-Tabelle einen Bedarf an, zum Beispiel aus einer Stückliste, die für ein Projekt exportiert wurde. Du brauchst dafür **Bedarfsteile schreiben**. Der Import sucht Artikel und Projekte nur: Er legt nie einen Katalogartikel oder ein Projekt an, beide müssen also vor dem Hochladen existieren. Umgekehrt speichert **Exportieren** in derselben Leiste eine Bedarfsliste als Excel-Datei, siehe [Bedarfe und Bestellungen exportieren](/handbook/procurement/list-export).

## Die Tabelle vorbereiten

Die Tabelle braucht eine Kopfzeile. Zieh die Datei auf **Excel-Datei hochladen** oder klick, um sie zu wählen. **Spaltennamen** zeigt jeden Spaltennamen, den Glados für jedes Feld erkennt. Werden alle Pflichtspalten erkannt, öffnet sich die Prüfung und die Zeilen werden sofort validiert; sonst ordnest du die Spalten von Hand zu und drückst **Weiter**.

Eine Zeile für Zukaufteile braucht **Projekt**, **Menge**, **Einheit** und entweder eine **Teilenummer** oder eine **Bestellnummer / Partnummer** mit ihrem **Hersteller**. Glados versucht es zuerst mit der Teilenummer und weicht dann auf Bestellnummer und Hersteller aus. Eine Zeile für Fertigungsteile braucht **Projekt**, **Menge**, **Teilenummer** und **Revision**. **Artikelbezeichnung**, **Notiz** und **Gewünschtes Lieferdatum** sind optional. Eine Menge in Stück muss eine ganze Zahl über null sein, und eine Datei darf höchstens so viele Zeilen haben, wie die Einstellungen zum Datenimport erlauben.

## Die Prüfung lesen

Zeilen mit **Übereinstimmend** sind bereit. **Ungelöst** heißt, die Projektnummer passt zu keinem Projekt. **Nicht gefunden** heißt, kein Katalogartikel hat diese Nummer, und **Mehrdeutig**, dass mehrere sie haben. **Ungültig** sagt, was nicht stimmt, zum Beispiel eine fehlende Einheit, ein Projekt, das nicht aktiv ist, oder ein Artikel, für den kein neuer Bedarf mehr angelegt werden kann. Eine übereinstimmende Zeile, deren Artikelbezeichnung oder andere Angaben vom Katalog abweichen, zeigt **Weicht vom Katalog ab**; der Bedarf wird trotzdem für den Katalogartikel angelegt, und die Werte aus der Datei werden nie in den Katalog geschrieben.

Eine Zeile lässt sich nicht direkt bearbeiten. Entferne sie mit **Zeile entfernen**, gib sie mit **Zeile hinzufügen** neu ein und drück **Validieren**.

## Die Bedarfe anlegen

**Erstellen** ist erst aktiv, wenn jede Zeile übereinstimmt. Glados prüft jede Zeile noch einmal und legt alle Bedarfe gemeinsam an, oder keinen, wenn eine Zeile scheitert. Bis dahin bleiben die Zeilen als Entwurf in diesem Browser: **Stapelerstellung** zeigt eine Markierung mit „Du hast einen unfertigen Stapelimport", und **Entwurf verwerfen** wirft die Zeilen weg.

## Beispiele

**Eine saubere Stückliste.** Zwölf Zukaufteile-Zeilen für Projekt 24017, jede mit Teilenummer. Alle stimmen überein, und **Erstellen** legt zwölf Bedarfe an.

**Ein Tippfehler im Projekt.** Eine Zeile sagt 24071. Sie zeigt **Ungelöst**, also entfernst du sie, fügst sie mit der richtigen Nummer neu hinzu und validierst.

**Eine Revision, die es nicht gibt.** Eine Fertigungsteile-Zeile verlangt Revision C eines Teils, das nur A und B hat. Sie zeigt **Nicht gefunden**, bis die Zeile eine vorhandene Revision nennt.
