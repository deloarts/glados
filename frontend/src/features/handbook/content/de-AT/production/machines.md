---
title: Maschinenseite
summary: Was die Seite einer Maschine zeigt, auf welchen Auftrag ihre Schaltflächen wirken und wie Bediener ihre Schicht von dort aus führen.
sourceRefs:
  - frontend/src/features/production/machines/views/MachineDetailView.vue
  - frontend/src/features/production/machines/components/MachineDetailContent.vue
  - frontend/src/features/production/machines/components/MachineCurrentOrderCard.vue
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

Die Maschinenseite zeigt eine Maschine und ihre Arbeit und ist dafür gedacht, die ganze Schicht über auf einem Bildschirm an der Maschine offen zu bleiben. Du öffnest sie mit einem Klick auf einen Maschinennamen in der [Warteschlange](/handbook/production/queue) oder auf eine Maschine in der Liste **Fertigungsmaschinen** unter Ressourcen. Sie aktualisiert sich von selbst, sobald sich ein Auftrag, ein Los oder die Maschine ändert.

## Die Leiste oben {#info}

Die Leiste oben nennt die Maschine mit Hersteller und Modell, ihre Fertigungsverfahren und die Pools, zu denen sie gehört. Ein Tag zeigt, ob die Maschine **Läuft**, **Pausiert** oder im **Leerlauf** ist, und solange ein Stillstand offen ist, sagt ein rotes Tag, seit wann die Maschine steht.

## Die Karten {#cards}

**Aktueller Auftrag** zeigt den Auftrag, der auf der Maschine läuft oder pausiert ist. Er zeigt das 3D-Modell oder Bild des Artikels, das Teil, das Los, die **Auftragsnummer**, die Menge, wann er **Gestartet** wurde und von wem. Darunter folgen die Dateien und Daten des Artikels und das Ausgangsmaterial mit seiner Bestellung und dem Stand seines Materialbedarfs. Laufen mehrere Aufträge auf der Maschine, stehen die anderen unter **Ebenfalls auf dieser Maschine**.

**Warteschlange** listet die Aufträge, die auf dieser Maschine für heute oder überfällig eingeplant sind, in der Reihenfolge der Warteschlange. Für jeden Pool, zu dem die Maschine gehört, listet eine Karte mit der Pool-Warteschlange die Aufträge des Pools, die noch keine Maschine übernommen hat, ebenfalls für heute oder überfällig. Die Karten in beiden Listen haben dieselben Schaltflächen wie in der Warteschlange, nur ohne Ziehen.

## Die Schaltflächen {#controls}

Die Schaltflächen in der Steuerleiste wirken auf den aktuellen Auftrag, oder auf den ersten Auftrag der Warteschlange, wenn nichts läuft. **Starten** oder **Fortsetzen**, **Pausieren**, **Abschließen**, **Teile verschrotten** und **Stornieren** funktionieren wie in der [Warteschlange](/handbook/production/queue) beschrieben, und **Abschließen** öffnet den Dialog aus [Fertigmeldungen erfassen](/handbook/production/completions). **Laufzettel drucken** druckt den Laufzettel des Auftrags, und sein Menü bietet auch **Etikett drucken**. **Artikel öffnen**, **Materialquelle öffnen** und **Auftrag öffnen** zeigen die Details in einem Dialog. **Stillstände** öffnet die Stillstände der Maschine, wie unter [Fertigungsmaschinen](/handbook/resources/machines) beschrieben.

Die Auftragsschaltflächen brauchen **Fertigungsaufträge schreiben**, und Drucken braucht **Dokumente drucken**. Eine Schaltfläche, für die dir die Berechtigung fehlt, bleibt deaktiviert, und ihr Tooltip nennt die Berechtigung.

Um eine Maschine ohne Schaltflächen auf einem Wandbildschirm zu zeigen, nimm das Widget **Maschinenansicht** eines [Infoscreens](/handbook/resources/infoscreens).

## Beispiele {#examples}

Auf der Maschine läuft nichts, und die Warteschlange hat zwei Aufträge. Der Bediener drückt **Starten**, und der erste Auftrag wird zum aktuellen Auftrag.

Ein Auftrag wartet in der Pool-Warteschlange einer Maschine. **Starten** auf seiner Karte fragt, welche Maschine des Pools ihn fertigt, und nach dem Start steht er als aktueller Auftrag dieser Maschine.

Der Bediener fertigt die letzten Stück und drückt **Abschließen**. Nach dem Erfassen fragt die **Fertigungsbewertung**, wie der Auftrag gelaufen ist, und der nächste Auftrag der Warteschlange wird zum Ziel der Schaltflächen.
