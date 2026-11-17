---
title: Lose
summary: Wie du auf dem Reiter Lose Fertigungslose anlegst, findest und bearbeitest, und was die Seite eines Loses zeigt und anbietet.
sourceRefs:
  - frontend/src/features/production/lots/views/ProductionLotsListView.vue
  - frontend/src/features/production/lots/components/LotsControls.vue
  - frontend/src/features/production/lots/components/LotsViewsBar.vue
  - frontend/src/features/production/lots/views/LotDetailView.vue
  - frontend/src/features/production/lots/components/lot-detail/LotDetailRecordGrid.vue
  - backend/src/modules/fulfillment/application/use_cases/production_lot/create_lot.py
lastVerified: 2026-11-10
---

Ein Los fertigt ein Fertigungsteil in einer festen Menge für ein Projekt, entlang eines Arbeitsplans aus Positionen. Der Reiter **Lose** unter Produktion listet alle Lose. Ein Klick öffnet ein Los in einem Dialog, und **Los öffnen** in dessen Kopfzeile öffnet die eigene Seite des Loses.

## Lose anlegen und bearbeiten {#create}

**Neues Los** fragt nach **Fertigungsteil**, **Projekt** und **Menge**. **Priorität**, **Notiz** und **Gewünschter Liefertermin** sind optional, und ein hier gesetzter Termin geht dem aus einem Bedarf vor. Das Los übernimmt Arbeitsplan und Materialquelle des Artikels. Ohne Materialquelle wird das Los trotzdem angelegt, sein erster interner Schritt wartet aber auf eine, siehe [Materialquelle](/handbook/production/material-source).

**Bearbeiten** öffnet einen Bereich für die Lose, die du auswählst. Er setzt **Priorität** und **Gewünschte Lieferung** für alle zugleich oder verschiebt einen Schritt: Wähl den **Neu zu planender Schritt** und gib einen **Geplanter Start** an. Lose ohne diesen Schritt werden übersprungen. Beide Schaltflächen brauchen **Fertigungslose schreiben** und sind ohne diese Berechtigung deaktiviert, mit einem Tooltip.

Die vier Verwalten-Schaltflächen öffnen einen Bereich neben der Tabelle, erklärt in [Bestellungen verwalten](/handbook/production/manage-orders), [Angebote verwalten](/handbook/production/manage-quotes), [Produktion verwalten](/handbook/production/manage-production) und [Materialquelle](/handbook/production/material-source). Fehlt dir eine Berechtigung, ist die Schaltfläche deaktiviert und ihr Tooltip nennt die Berechtigung.

## Lose finden {#views}

**Zeitleiste** zeigt die Lose als Balken über die Zeit. Im **Spaltenmodus**, der Vorgabe, hat jeder Schritt eines Loses seine eigene Zeile, der **Einfacher Modus** setzt alle Schritte in eine Zelle, und der **Breitbildmodus** gibt jedem Schritt eigene Spalten. Gruppieren nach Status, Priorität oder Projekt schaltet in den Breitbildmodus. **Fertiggestellt ausblenden**, **Storniert ausblenden**, **Zuweisung erforderlich** und **Freigabe erforderlich** grenzen die Liste ein. Der **Smart-Filter** ist von Haus aus an und zeigt bei geöffnetem Verwalten-Bereich nur Lose, bei denen dort noch etwas zu tun ist. Auf einem schmalen Bildschirm klappen die Modi und diese Filter in zwei Schaltflächen zusammen, und **Filter** zählt die eingeschalteten.

In der Filterzeile durchsuchen die Spalten Artikel und Quelle ihre beiden Zeilen getrennt, und Menge, Rüstzeit und Stückzeit nehmen ein Minimum und ein Maximum.

## Die Seite eines Loses {#lot}

Die obere Leiste zeigt Losnummer, Status und Hinweise wie **Wartet auf Rohmaterial**, **Wartet auf Qualitätsprüfung** oder **Verspätet**. Die Reiter rechts sind **Ausführung** mit Positionen, Fertigungsaufträgen und Fertigmeldungen, **Material & Bedarf** mit dem Rohmaterial, seinem Bedarf und den Eingängen, **Stückbilanz** mit dem Verbleib jedes Stücks, **Projekt** und **Prüfprotokoll**.

Die Schaltflächen darüber drucken Laufzettel, Etikett, Ausschuss-Etikett oder Prüfbericht und bieten **Verwalten**, **Pausieren**, **Fortsetzen**, **Teile verschrotten**, **Los abschließen** und **Los stornieren**, erklärt in [Lebenszyklus eines Loses](/handbook/production/lot-lifecycle). **Verwalten** braucht **Fertigungslose schreiben** und öffnet Materialquelle, Arbeitsschritte, Positionsgruppierung und die Positionsbereiche. Ein Los zu beenden braucht zusätzlich **Fertigungslose verwalten**, und **Teile verschrotten** braucht **Fertigungsaufträge schreiben**. Fehlt dir die Berechtigung, ist die Schaltfläche deaktiviert und ihr Tooltip nennt sie.

## Am Handy {#phone}

Ein Handy listet jedes Los mit Artikel, Status und gewünschter Lieferung. Ein angetipptes Los öffnet seine Seite, wo die Aktionen in einem Menü **Aktionen** liegen. Die Verwalten-Bereiche fehlen dort.

## Beispiele

Ein Kunde braucht 40 Halter. Klick auf **Neues Los**, wähl Fertigungsteil und Projekt, gib 40 ein und speichere. Das Los erscheint in der Liste, und seine Positionen warten auf ihre Zuweisung.

Der Einkauf fragt, welche Lose auf eine Materialentscheidung warten. Schalte **Freigabe erforderlich** ein und gib jede Quelle frei oder lehne sie ab.

Bei drei Losen soll der zweite Schritt eine Woche später laufen. Wähl sie aus, klick auf **Bearbeiten**, wähl Schritt 2 als **Neu zu planender Schritt** und gib den neuen **Geplanter Start** ein.
