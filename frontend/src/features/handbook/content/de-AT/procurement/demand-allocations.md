---
title: Bedarfe zuteilen
summary: Wie ein Zukaufteile- oder Rohmaterialbedarf über Auto-Zuteilen, Zuteilungen verwalten und Aus Lager decken von Bestellpositionen und vom Lager gedeckt wird, und wie ein Ersatzartikel festgehalten wird.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/auto_allocate.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/allocation_writers.py
  - backend/src/modules/fulfillment/application/use_cases/_demand_family/fulfill_from_stock.py
  - backend/src/modules/fulfillment/domain/services/allocation_coverage.py
  - backend/src/modules/fulfillment/domain/services/allocation_service.py
  - frontend/src/features/procurement/components/BoughtItemManageAllocationsDialog.vue
  - frontend/src/features/production/source-item-demands/components/SourceItemManageAllocationsDialog.vue
lastVerified: 2026-11-10
---

Eine Zuteilung verbindet einen Teil eines Bedarfs mit dem, was ihn deckt: eine Menge auf einer Bestellposition oder eine Menge aus dem Lager. Zukaufteile-Bedarfe und Rohmaterialbedarfe werden so zugeteilt, und ihr Status ergibt sich daraus, siehe [Lebenszyklus eines Zukaufteile-Bedarfs](/handbook/procurement/bought-item-demand-lifecycle). Fertigungsteile-Bedarfe werden stattdessen von Losen gedeckt und nutzen nur den Lageranteil. Jede Aktion hier braucht **Zuordnungen schreiben**; ohne die Berechtigung ist die Aktion ausgegraut, und der Tooltip nennt sie. Ein erfüllter oder abgebrochener Bedarf nimmt keine neue Zuteilung an.

## Auto-Zuteilen

**Auto-Zuteilen** im Zeilenmenü oder im Bedarfsdialog sucht Bestellpositionen für den eigenen Artikel des Bedarfs mit dem Status **Bestellt** oder **Teillieferung** und füllt den Bedarf daraus. Bestellte Positionen gehen vor teilweise gelieferten, dann der früheste erwartete Liefertermin, dann die Position mit dem meisten Rest, damit möglichst wenige Positionen berührt werden. Eine Position, die sich mehrere Bedarfe teilen, bietet nur an, was die anderen noch nicht halten. Positionen, die noch **Ausstehend** oder **Angefragt** sind, werden nie verwendet, und wenn nichts passt, meldet Glados „Keine passenden Bestellpositionen gefunden."

## Zuteilungen verwalten

**Zuteilungen verwalten** im Zeilenmenü oder **Verwalten** im Bedarfsdialog öffnet eine Liste aller Zuteilungen des Bedarfs. Ändere eine Menge und speichere sie mit dem Häkchen, oder entferne die Zuteilung mit dem Mistkübel. Unter **Bestellposition verknüpfen** suchst du eine Bestellung über ihre Nummer oder ihren Lieferanten, in jedem Status, wählst dann die Position und die Menge und drückst **Hinzufügen**. Eine Verknüpfung von Hand funktioniert für eine Position in jedem Status, du kannst einen Bedarf also mit einer Position verbinden, die noch angefragt wird; der Bedarf bleibt dann Zugeteilt, bis die Position bestellt ist. Bei einem Rohmaterialbedarf legt **Neue Bestellposition für dieses Material anlegen** eine Position auf der gewählten Bestellung an und verknüpft sie mit **Anlegen & Zuteilen** in einem Schritt. **Lagerzuteilung hinzufügen** hält fest, was aus dem Regal kommt; ein Bedarf hat eine Lagerzuteilung, die du in ihrer Zeile änderst.

Glados lehnt eine Zuteilung ab, die größer ist als das, was dem Bedarf noch fehlt, oder als das, was die Position frei hat, eine stornierte Position und eine, die Teile nehmen würde, die schon für einen anderen Bedarf geliefert wurden. Eine Position in einer anderen Einheit ist mit Warnung erlaubt, denn nichts wird umgerechnet.

## Aus Lager decken

**Aus Lager decken** deckt einen Teil eines Bedarfs direkt aus dem Regal, höchstens das, was noch nicht zugeteilt ist. Du findest es im Zeilenmenü, im Bedarfsdialog und für mehrere ausgewählte Bedarfe auf einmal im Bereich **Lager verwalten**. Glados hält nur fest, wie viel entnommen wurde; den Lagerstand selbst führt Glados nicht.

## Ersatzartikel

Verknüpfst du eine Position mit einem anderen Zukaufteil, wird das als Ersatz festgehalten: Der Dialog warnt „Anderer Artikel als der Bedarf, wird als Substitution verknüpft." und fragt nach einem optionalen Grund. Ein Rohmaterialbedarf darf jede Rohblock-Position der Bestellung als Ersatz nehmen, während ein Zukaufteil als Material genau passen muss. Der Bedarfsdialog zeigt Ersatzartikel unter **Als Ersatz bestellt**, und die Zeile zeigt „Mit Ersatzartikel erfüllt".

## Beispiele

**Der Normalfall.** Ein Bedarf über 20 Kabelverschraubungen, und eine bestellte Position über 50 hat noch 30 frei. **Auto-Zuteilen** nimmt 20, und der Bedarf steht auf Bestellt.

**Eine Position, die noch angefragt wird.** **Auto-Zuteilen** findet nichts, also verknüpfst du die Position unter **Zuteilungen verwalten**, und der Bedarf wartet als Zugeteilt.

**Ein Teil aus dem Regal.** Vier von zehn Sicherungen sind auf Lager. **Aus Lager decken** mit 4 deckt sie, und die übrigen sechs werden bestellt.
