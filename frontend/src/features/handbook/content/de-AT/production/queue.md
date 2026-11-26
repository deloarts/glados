---
title: Warteschlange
summary: Wie der Reiter Warteschlange die offenen Fertigungsaufträge nach Maschine und Tag ordnet und wie du sie verschiebst, anheftest, startest, pausierst, teilst und zusammenführst.
sourceRefs:
  - frontend/src/features/production/queue/components/ProductionQueueBoard.vue
  - frontend/src/features/production/queue/composables/useQueueBoardGroups.ts
  - frontend/src/features/production/queue/components/ProductionOrderCard.vue
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/split_production_order.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/merge_production_orders.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/record_manufacturing_assessment.py
lastVerified: 2026-11-26
---

Der Reiter **Warteschlange** unter Produktion zeigt jeden offenen Fertigungsauftrag als Karte, eine Spalte je Maschine, und aktualisiert sich von selbst, wenn jemand einen Auftrag ändert.

## Spalten und Tage {#columns}

**Manuelle Arbeit** sammelt Schritte, die keine Maschine brauchen, und **Prüfung** die QS-Schritte, danach folgen die Pools und Maschinen alphabetisch. Jeder Schritt unter **Manuelle Arbeit** und **Prüfung** wird für sich geplant, ein wartender Schritt hält also keinen anderen auf, und beide Spalten listen ihre Karten nach geplantem Start. **Keine Maschine zugewiesen** erscheint nur für alte Aufträge ohne Maschine und ohne Pool. Ein Klick auf einen Maschinennamen öffnet ihre [Maschinenseite](/handbook/production/machines).

In einer Spalte listet **In Bearbeitung** die laufenden Aufträge, danach folgen die wartenden nach geplantem Starttag. Der **Zeitraum** in der Leiste reicht anfangs von heute bis Sonntag und umfasst bis zu 31 Tage. Was vor dem Zeitraum geplant ist, steht unter **Überfällig**, und was danach geplant ist, bleibt von der Tafel weg.

**Abgeschlossene anzeigen** zeigt die Aufträge der letzten sieben Tage unter **Abgeschlossen / Storniert**. **Nicht bereite ausblenden** blendet die wartenden Aufträge aus, die **Starten** gerade ablehnen würde, und dieser Browser merkt sich den Schalter. **Horizontal** und **Vertikal** legen die Anordnung fest.

## Verschieben und anheften {#pin}

Zieh eine Karte an ihrem Griff, um die Warteschlange umzuordnen, oder auf eine andere Spalte am selben Tag, um sie dorthin zu verschieben, sofern diese Maschine oder dieser Pool ihre Fertigungsverfahren abdeckt. Ziehen braucht **Fertigungsaufträge schreiben** und geht auf dem Handy nicht.

**Nach oben anheften** hält einen Auftrag fest: Er lässt sich nicht ziehen, seine Termine bleiben, und Auto-Planen lässt ihn in Ruhe, außer **Überschreiben von manuell geplanten Terminen erlauben** ist an. Anheften braucht **Fertigungsaufträge verwalten**.

## Starten und fortsetzen {#start}

**Starten** beginnt einen eingeplanten Auftrag und **Fortsetzen** setzt einen pausierten fort, normalerweise sofort. Der Dialog **Fertigungsauftrag starten** öffnet sich nur, wenn ein gemeinsames Werkstattkonto den **Bediener** wählen muss oder ein Auftrag auf einem Pool seine **Maschine**. Ist Starten deaktiviert, sagt der Tooltip warum, zum Beispiel dass der Schritt davor noch nichts bereitgestellt hat oder das Los pausiert ist.

## Pausieren {#pause}

**Pausieren** unterbricht einen laufenden Auftrag. Der **Grund** ist optional, und ein gemeinsames Konto wählt auch den **Bediener**. Ein Auftrag, der pausiert wurde, weil sein Los pausiert ist, läuft mit dem Los wieder weiter.

## Teilen {#split}

**Teilen** unter **Weitere Aktionen** teilt einen eingeplanten Auftrag mit mehr als einem Stück in zwei oder mehr Teile. Jeder Teil bekommt ganze Stück, und **Speichern** geht erst, wenn die Teile zusammen die Menge des Auftrags ergeben. Jeder Teil bekommt seine eigene Rüstzeit und reiht sich am Ende derselben Warteschlange ein.

## Zusammenführen {#merge}

**Zusammenführen** vereint eingeplante Aufträge derselben Losposition auf derselben Maschine und demselben Pool. Hak die Aufträge an und drück **Zusammenführen**. Der Auftrag, der in der Warteschlange am weitesten vorne steht, übernimmt die Summe, die anderen werden storniert, und die Dauer rechnet wieder mit einer Rüstzeit. Ein Zusammenführen lässt sich nicht rückgängig machen.

## Abschließen und stornieren {#assessment}

**Abschließen** öffnet den Dialog aus [Fertigmeldungen erfassen](/handbook/production/completions). Ist der Auftrag fertig, fragt die **Fertigungsbewertung**, wie er wirklich gelaufen ist, damit künftige Zeitschätzungen besser werden. **Tatsächliche Minuten pro Stück** ist Pflicht, und **Überspringen** schließt sie ohne Speichern.

**Stornieren**, ebenfalls unter Weitere Aktionen, fragt zuerst nach und storniert dann den Auftrag. Einen Auftrag, den du selbst angelegt hast, kannst du stornieren, für den Auftrag von jemand anderem brauchst du **Fertigungsaufträge verwalten**. Einen Prüfschritt zu starten und abzuschließen braucht zusätzlich **Qualitätsprüfungen erfassen**. Eine Schaltfläche, für die dir die Berechtigung fehlt, ist deaktiviert, und ihr Tooltip nennt die Berechtigung, ein Menüeintrag nennt sie, wenn du auf ihn zeigst.

## Beispiele {#examples}

Ein Auftrag über 40 Stück wartet auf einem Pool. Der Bediener drückt **Starten**, wählt die freie Maschine, und die Karte wandert zu dieser Maschine.

Eine Planerin teilt einen Auftrag über 25 Stück in 13 und 12 und zieht den zweiten Teil auf eine andere Maschine.

Zwei Aufträge über 5 Stück für eine Position warten auf einer Maschine. Zusammengeführt bleibt ein Auftrag über 10 mit einer Rüstzeit.
