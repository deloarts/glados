---
title: Fertigungsteile
summary: Was der Fertigungsteilkatalog enthält, wie Revisionen funktionieren und welche Felder eines Teils aus PDM kommen und welche du im Web bearbeitest.
sourceRefs:
  - frontend/src/features/made-items/components/MadeItemsCatalogueControls.vue
  - frontend/src/features/made-items/composables/useMadeItemsCatalogueActions.ts
  - frontend/src/features/made-items/components/MadeItemDetailDialog.vue
  - frontend/src/features/catalogue/views/MadeItemDetailView.vue
  - backend/src/modules/catalogue/domain/policies/item_field_ownership.py
  - backend/src/modules/catalogue/domain/policies/pdm_ownership.py
lastVerified: 2026-11-12
---

Der Fertigungsteilkatalog listet die Teile, die deine Werkstatt selbst fertigt. Jede Revision eines Teils ist eine eigene Zeile, damit ein Bedarf oder ein Los immer genau die Revision nennt, die es baut. Die Liste ist der Reiter **Fertigungsteile** im Katalog und zeigt die neueste Revision jedes Teils; **Alle Revisionen anzeigen** listet auch die älteren. Ein Klick auf eine Zeile öffnet die Seite des Teils, auf der eine Auswahl neben der Teilenummer zwischen seinen Revisionen wechselt.

## In der Liste arbeiten

**Neu** legt ein Teil an, außer deine Nummerierungseinstellungen überlassen Fertigungsteile dem PDM. **Bearbeiten** schaltet die Liste in den Bearbeitungsmodus, um mehrere Teile auf einmal zu ändern. **Exportieren** speichert die gefilterte Liste als Excel-Datei, siehe [Katalog exportieren](/handbook/catalogue/catalogue-export). Das Zeilenmenü bietet **Bearbeiten**, **Kopieren**, **Neue Revision**, **Zusammenführen**, **Archivieren** oder **Wiederherstellen**, **Zum Bedarf hinzufügen**, **Bedarfs- / Fertigungshistorie**, **Etikett drucken** und **Änderungsprotokoll anzeigen**. Bearbeiten, Kopieren und neue Revisionen brauchen **Fertigungsteile schreiben**, Zusammenführen und Archivieren brauchen **Fertigungsteile archivieren**.

## Die Seite eines Teils

Die Seite zeigt das Teil, seinen **Arbeitsplan**, seine **Materialquelle**, seine **Bedarfe**, **Bestellungen** und **Lose**, seine **Dateien**, seine **Verwendung** und sein **Änderungsprotokoll**. Oben kannst du **Artikel bearbeiten**, **Bedarf anlegen**, wofür du **Bedarfsteile schreiben** brauchst, und mit **Drucken** ein Etikett oder einen Laufzettel drucken. **Zur Bestellung hinzufügen** bleibt ausgegraut, denn ein Fertigungsteil wird über die Schrittliste eines Loses bestellt.

## Felder aus PDM und Felder aus dem Web

Ein in SolidWorks modelliertes Teil zeigt **PDM** als **Datenquelle**. Teilenummer, Revision, Revisionsdatum und Revisionsnotiz kommen aus PDM. Artikelname, Material, Masse, Grundgröße, Notiz, Weblink, Artikelgruppen, Kundendaten, Arbeitsplan und Materialquelle werden in der SolidWorks-Datei geschrieben und kommen mit jeder freigegebenen Version. Sein Status folgt dem PDM-Workflow. Solange dein Administrator PDM-Teile schreibgeschützt hält, sind diese Felder gesperrt mit „Von PDM verwaltet", und du änderst sie in der Datei. Eine Ausnahme ist ein Rohblock als Materialquelle: Den kannst du im Web ändern, und deine Wahl bleibt, bis die Konstruktion in der Datei einen anderen setzt. Nachfolger, Dateien und hochgeladene Fotos bleiben bei dir.

Ein im Web angelegtes Teil zeigt **Web**, und du bearbeitest alles hier. Standardmäßig ändern sich manche Felder, etwa das Material, nur über **Neue Revision**, die die nächste Revision mit deinen Werten anlegt und fragt **Was passiert mit der aktuellen Revision?**: **Ersetzt**, **Inaktiv** oder **Aktiv**. Bearbeitet wird nur die neueste Revision; bei einer älteren lässt sich nur der Status ändern. Bei einem Teil aus PDM ist **Neue Revision** ausgegraut, weil seine Revisionen aus PDM kommen.

## Beispiele

**Ein Webteil bekommt ein neues Material.** Das Materialfeld ist im Bearbeiten-Dialog gesperrt. **Neue Revision** legt Revision B mit dem neuen Material an, und Revision A wird auf **Ersetzt** gesetzt.

**Ein Teil aus PDM.** Der Artikelname ist gesperrt mit „Von PDM verwaltet". Die Konstruktion korrigiert ihn in der SolidWorks-Datei, und die nächste Freigabe bringt ihn herein.

**Eine andere Stange für ein PDM-Teil.** Du wählst im Web einen anderen Rohblock als Materialquelle. Er bleibt, bis die Konstruktion in der Datei einen anderen setzt.
