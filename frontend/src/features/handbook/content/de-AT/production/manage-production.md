---
title: Produktion verwalten
summary: Wie du Lospositionen auf einer Maschine oder in einem Maschinenpool an die hauseigene Fertigung vergibst, und wo die konkrete Maschine gewählt wird.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_order/assign_internal_position.py
  - backend/src/modules/fulfillment/application/use_cases/production_order/reassign_production_order_machine.py
  - backend/src/modules/fulfillment/domain/services/production_order_rules.py
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

Mit „Produktion verwalten“ vergibst du Lospositionen an die hauseigene Fertigung. Klick im Tab Lose auf **Produktion verwalten**, um Schritte über viele Lose hinweg abzuarbeiten. Bei einem einzelnen Los klickst du auf **Verwalten** und öffnest **Produktion verwalten**, oder du klickst bei einer Position auf **Intern vergeben**, das **Position intern vergeben** öffnet. Jede Vergabe legt eingeplante Fertigungsaufträge für die Werkstatt an. **Produktion verwalten** braucht **Fertigungslose schreiben** und **Fertigungsaufträge schreiben**, weil das Vergeben Fertigungsaufträge anlegt, und ist ohne sie deaktiviert, mit einem Tooltip, der die fehlende Berechtigung nennt.

## Der übliche Ablauf {#flow}

Eine Position, die eine Maschine braucht, wird an eine Maschine oder, häufiger, an einen Maschinenpool vergeben. Die Warteschlange des Pools bekommt dann echte Termine aus den Kalendern seiner Maschinen. Die konkrete Maschine wird spätestens beim Start des Auftrags gewählt.

## Eine Position vergeben {#commit}

Wähl unter **Maschine oder Pool** eine Maschine oder einen Pool, und jede ausgewählte Zeile geht dorthin. Mit eingeschaltetem **Smart-Filter** schränkt die Wahl die Liste außerdem auf Lose ein, die sie fertigen kann. Wählst du nichts, geht jede Zeile an ihren am besten passenden Pool, der neben der Zeile steht, und ein Hinweis sagt das, bevor du auf **Zuweisen** klickst. Eine Zeile, die kein Pool fertigen kann, ist deaktiviert, und ihr Tooltip nennt die Fertigungsverfahren, die niemand abdeckt. Eine Position mit nur manuellen Schritten nimmt **Ohne Maschine einplanen**, und eine Prüfposition geht nur an eine QS-Maschine.

**Menge** nimmt ganze Stück bis zur offenen Menge. Im Tab Lose werden archivierte Maschinen und Pools nicht angeboten, weil sie keine neuen Aufträge annehmen. Bei einem einzelnen Los stehen sie am Ende der Liste, nehmen aber ebenfalls keine neuen Aufträge an. In **Position intern vergeben** kannst du eine Position mit **Maschine hinzufügen** auf mehrere Maschinen aufteilen, jede mit eigener **Menge**, während **Zugewiesen** und **Verbleibend** zeigen, was übrig ist. Positionen, deren Fertigungsauftrag noch keine Maschine hat, stehen unter **Benötigt eine Maschine**.

## Aus der Schrittliste {#step-list}

Nachdem du auf der Losseite auf **Verwalten** geklickt hast, vergibt die Spalte **Maschine / Bestellung** der Schrittliste eine Position nach der anderen. Für eine nicht zugewiesene Position bietet sie geeignete Maschinen und Pools, offene Bestellungen, **Bestellung anlegen…** und, für manuelle Positionen, **Ohne Maschine einreihen**. Eine Wahl vergibt alle offenen Stück, und eine Bestellposition zählt in Stück, ohne Preis und ohne Termine. Bei einem eingeplanten oder pausierten Auftrag ändert dieselbe Spalte seine Maschine oder seinen Pool, außer der Auftrag ist angeheftet. Deine Wahl wartet, bis du auf **Speichern** klickst. Nur eine neue Bestellung wird sofort angelegt.

## Die Maschine festlegen {#resolve}

Ein Poolauftrag zeigt ein Pool-Tag, bis er eine Maschine hat, die auf einem von vier Wegen gewählt wird. Der Dialog **Fertigungsauftrag starten** fragt nach der **Maschine** und bei einem gemeinsamen Konto auch nach dem **Bediener**. Du kannst die Karte auf der [Warteschlange](/handbook/production/queue) in eine Maschinenspalte ziehen, in der Schrittliste eine Maschine wählen oder [Auto-Planen](/handbook/production/auto-plan) auf der Ebene **Maschinen** ausführen.

Ein Auftrag kann nur starten, solange sein Los nicht pausiert ist und Stück aus dem vorherigen Schritt oder Rohmaterial verfügbar sind.

## Aufträge ohne Maschine {#no-machine}

Ein Auftrag, der eine Maschine braucht, aber weder Maschine noch Pool hat, bekommt keine Termine. Er steht in der Spalte **Keine Maschine zugewiesen** der Warteschlange mit einer Warnung, bis ihn jemand vergibt, zum Beispiel unter **Benötigt eine Maschine**.

## Beispiele {#examples}

Eine Position über 20 Stück wird in **Position intern vergeben** aufgeteilt, 12 auf eine Drehmaschine und 8 auf eine andere. Zwei eingeplante Aufträge entstehen, einer je Maschine.

Eine Fräsposition geht an den Fräspool. An ihrem Tag klickt der Bediener auf **Starten**, wählt die freie Maschine, und der Auftrag läuft dort.
