---
title: Eine Lieferung korrigieren
summary: Wie du irrtümlich angenommene Teile zurücknimmst oder Teile zurückweist, deren Schaden du erst später findest, was eine Korrektur an der Position und ihrer Bestellung ändert und wie sie auf der KPI-Seite erscheint.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/order/correct_order_item_delivery.py
  - backend/src/modules/fulfillment/domain/services/order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
  - backend/src/modules/fulfillment/application/use_cases/order/_lines.py
  - backend/src/modules/fulfillment/domain/services/delivery_booking_rules.py
  - backend/src/modules/fulfillment/application/use_cases/order/upload_delivery_picture.py
lastVerified: 2026-11-13
---

Eine Lieferbuchung wird nie bearbeitet oder gelöscht. Hast du zu viele Teile angenommen, zum Beispiel weil eine Kiste doppelt gezählt wurde, buchst du stattdessen eine Korrektur: einen neuen Eintrag in der Lieferhistorie, der die Teile zurücknimmt. Die Historie zeigt dann die ursprüngliche Buchung und die Korrektur, und die gelieferte Menge der Position ist die Summe aus beiden.

## Eine Korrektur buchen

Öffne die **Lieferhistorie** der Position und nutze bei der falschen Buchung **Lieferung korrigieren**, die Rückgängig-Schaltfläche in der Spalte **Korrektur**. Gib die **Zurückzunehmende Stück** und einen **Grund** ein und wähle dann **Korrektur buchen**. Der Grund ist Pflicht, damit später jeder in der Historie sieht, warum die Teile verschwunden sind.

Du kannst höchstens zurücknehmen, was diese Buchung angenommen hat, abzüglich dessen, was frühere Korrekturen derselben Buchung schon zurückgenommen haben. Korrigiert werden nur angenommene Teile, zurückgewiesene und verlorene Teile bleiben, wie sie gebucht wurden. Du brauchst **Lieferungen erfassen**. Ohne diese Berechtigung ist die Schaltfläche deaktiviert, und ihr Tooltip nennt die fehlende Berechtigung.

## Schaden nach dem Wareneingang entdeckt {#damage}

Versteckte Schäden zeigen sich oft erst beim Auspacken oder bei der Prüfung, nachdem die Ware schon als angenommen gebucht ist. Nutze **Schaden melden**, die Schaltfläche neben der Rückgängig-Schaltfläche, oder wähle im Korrekturdialog unter **Was ist passiert?** die Option **Schaden nach dem Wareneingang entdeckt**. Statt eines Grundes wählst du den **Grund** der Zurückweisung, etwa **Transportschaden**, und die **Weitere Behandlung**, wie beim Wareneingang, und du kannst eine **Notiz** und Fotos dazugeben. **Stück zurückweisen** nimmt die Teile als zurückgewiesene zurück.

**Lieferant liefert nach** öffnet die Position wieder, und ihr erwarteter Liefertermin wird gelöscht, bis der Lieferant einen neuen bestätigt. **Stück ist verloren** lässt die Position geliefert, weil der Lieferant für das Teil nichts mehr schickt, und die der Position zugeordneten Bedarfe schrumpfen auf das, was sie noch geliefert hat, damit das fehlende Teil bei einem Bedarf wieder erscheint und neu bestellt werden kann. In beiden Fällen geht eine Meldung an alle, die Bestellungen bearbeiten dürfen, und die Zurückweisung zählt auf der KPI-Seite wie eine beim Wareneingang. Es gelten dieselben Grenzen wie für eine Korrektur.

## Fotos {#pictures}

Die Spalte **Fotos** der Lieferhistorie hält Fotos zu einer Buchung, etwa vom Schaden oder vom abgestempelten Lieferschein. **Foto hinzufügen** nimmt JPEG-, PNG- oder WebP-Dateien, und am Handy bietet es die Kamera an. Ein Foto erscheint auch bei den Dateien der Bestellung. Fotos hinzufügen und entfernen braucht **Lieferungen erfassen**.

## Wann sich eine Position nicht korrigieren lässt

Eine Position für ein Los lässt sich hier nicht korrigieren, weil ihr Los die gelieferten Teile schon als fertig zählt. Eine Position einer stornierten Bestellung wird abgelehnt, weil sie nichts mehr beliefern kann und sonst für immer offen bliebe. Eine Position, deren Restmenge ausgebucht ist, wird abgelehnt, bis du sie wieder öffnest, siehe [Aktionen an Bestellpositionen](/handbook/procurement/order-line-actions#close-short).

Ein Bedarf, den die Lieferungen der Position erfüllt haben, hält eine Korrektur nicht auf: Er geht wieder auf bestellt oder zugeteilt zurück und zeigt die fehlenden Teile wieder an. Abgelehnt wird eine Korrektur nur, solange ein Bedarf, der der Position zugeteilt ist, die Teile schon verbraucht hat, also ein Bedarf, den jemand von Hand als erfüllt markiert hat, oder ein Rohblock-Bedarf, dessen Los im ersten Schritt schon Teile bearbeitet hat.

## Was eine Korrektur an der Position ändert

Eine Korrektur kann eine Position wieder öffnen. Eine gelieferte Position wird wieder teilweise geliefert und wartet auf den Rest. Die Bestellung folgt ihren Positionen, eine gelieferte Bestellung kann also wieder auf Teillieferung gehen.

Eine Position kann innerhalb ihrer [Toleranz für Überlieferung](/handbook/procurement/delivery-tolerances#over) mehr als ihre Menge angenommen haben, und die zusätzlichen Teile können an andere Bedarfe gegangen sein. Nimmt eine Korrektur diese Teile zurück, werden die Zuordnungen der Position an das angepasst, was sie noch geliefert hat, und ein Bedarf, der auf die zusätzlichen Teile gebaut hat, zeigt sie wieder als fehlend.

## Auf der KPI-Seite

Die KPI-Seite zählt eine Korrektur an ihrem eigenen Datum, nicht am Datum der korrigierten Buchung. Ein Zeitraum, der nur die Korrektur enthält, zeigt für diesen Lieferanten deshalb eine negative gelieferte Menge.

## Beispiele

**Beim Auspacken verbeult.** Bestellt 10, gebucht 10, und beim Öffnen der Kiste sind zwei verbeult. Nutze bei der Buchung **Schaden melden**, nimm 2 mit **Transportschaden** und **Lieferant liefert nach** zurück und häng ein Foto an. Die Position zeigt 8 von 10 und wartet auf den Ersatz.

**Doppelt gezählt.** Bestellt 10, gebucht 10, aber in der Kiste sind nur 9. Korrigiere die Buchung um 1 mit dem Grund "doppelt gezählt". Die Position zeigt 9 von 10 und wartet auf das letzte Teil.

**Nach dem Ausbuchen der Restmenge.** Der Lieferant hat 8 von 10 geschickt, und du hast die Restmenge bei 8 ausgebucht. Später stellt sich heraus, dass zwei der 8 zu einer anderen Bestellung gehören. Öffne die Position wieder, damit kommt ihre Menge von 10 zurück, und korrigiere die Buchung um 2: Die Position zeigt 6 von 10 und wartet auf den Rest. Schickt der Lieferant nichts mehr, buchst du die Restmenge wieder bei 6 aus.

**Ein erfüllter Bedarf.** Die 10 Teile einer Position haben den Bedarf eines Projekts erfüllt, und eines davon wurde doppelt gezählt. Korrigiere die Buchung um 1: Der Bedarf ist nicht mehr erfüllt und zeigt das fehlende Teil an. Hätte jemand den Bedarf von Hand als erfüllt markiert, würde die Korrektur abgelehnt, weil das Projekt die Teile vielleicht schon verbraucht hat.
