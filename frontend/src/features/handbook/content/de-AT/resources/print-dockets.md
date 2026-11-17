---
title: Laufzettel
summary: Was ein Laufzettel ist, worin er sich bei der Einrichtung von einem Etikett unterscheidet, auf welches Papier er druckt und wo du ihn druckst oder herunterlädst.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_document/download_print_document.py
  - backend/src/modules/quality/application/services/docket_spec.py
  - backend/src/modules/quality/application/use_cases/print_template/update_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/reset_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/preview_print_template.py
  - backend/src/modules/quality/domain/services/print_template_rules.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
  - backend/src/modules/quality/application/use_cases/print_document/handle_event_auto_print.py
lastVerified: 2026-11-10
---

Ein Laufzettel ist ein PDF-Begleitblatt, das mit der Arbeit durch die Werkstatt geht, gedruckt auf einem Dokumentdrucker oder heruntergeladen. Unter Ressourcen hat **Laufzettel** eine feste Zeile pro Art: **Bestellung-Laufzettel**, **Los-Laufzettel**, **Fertigungsauftrag-Laufzettel**, **Fertigartikel-Laufzettel**, **Kaufartikel-Laufzettel** und **Rohblock-Laufzettel**. Eine Zeile kannst du weder anlegen noch löschen, nur einrichten.

## Worin sich ein Laufzettel von einem Etikett unterscheidet

**Laufzettel bearbeiten** öffnet denselben Editor wie bei Etiketten, beschrieben in [Druck-Etiketten](/handbook/resources/print-labels), mit ein paar Unterschieden. **Drucker** bietet nur Dokumentdrucker an. Die **Kopienregel** ist immer **Fest**, ein Laufzettel druckt also die **Feste Kopienanzahl**, nie mehr als **Max. Kopien**. Der **Bestellung-Laufzettel** hat kein Ereignis, bei dem er druckt, und wird immer von Hand gedruckt.

Der Inhalt ist ein Layout statt eines Etiketts: Die **Block-Spezifikation (JSON)** beschreibt die Blöcke der Seite, und der Editor warnt sofort, wenn sie kein gültiges JSON ist. Die **Feldzuordnung** verknüpft jedes Feld, das das Layout nennt, mit einer Angabe des Laufzettels. Beim Speichern wird dasselbe geprüft wie bei einem Etikett, und dazu, ob der Drucker ein Dokumentdrucker ist.

## Papier {#paper}

**Papier** bestimmt, wie der Laufzettel auf dem Blatt liegt. **A4 (zentriert mit Schnittmarken)** setzt ihn in die Mitte einer A4-Seite, mit Marken zum Schneiden. **A4 ausgerichtet (in der Hälfte schneiden für A5-Laufzettel)** legt ihn so, dass die halbierte Seite einen A5-Laufzettel ergibt. **A5 (1:1)** druckt ihn in seiner eigenen Größe auf A5-Papier. Die Tabelle zeigt die Wahl unter **Papiergröße**.

## Vorschau und Herunterladen

Gib im Vorschaubereich eine **Datensatz-ID** ein, dann siehst du den Laufzettel für einen echten Datensatz. **PDF herunterladen** daneben speichert den Laufzettel als Datei, statt ihn zu drucken; das geht nur, solange der Laufzettel aktiviert ist und Inhalt hat. Beim Herunterladen ist kein Drucker beteiligt, deshalb taucht es in keinem **Druckverlauf** auf.

## Wo Laufzettel gedruckt werden

Auf der Seite eines Teils drucken **Drucken** und **Laufzettel** seinen Laufzettel. In der Lostabelle bietet **Drucken** den Punkt **Los-Laufzettel drucken**, und die Losseite druckt ihn mit **Laufzettel drucken**. Die Karten der Fertigungswarteschlange und die Maschinenseite drucken den Laufzettel des Fertigungsauftrags mit **Laufzettel drucken**. In der Tabelle der Bestellungen bietet die rechte Maustaste **Laufzettel herunterladen**, um den Bestellung-Laufzettel zu speichern, und **Laufzettel drucken**, um ihn an seinen Drucker zu schicken.

Automatischer Druck, fehlgeschlagene Drucke und **Auto-Druck deaktivieren** funktionieren wie bei Etiketten: Ein fehlgeschlagener Laufzettel hält die Arbeit nie auf und steht als **Fehlgeschlagen** im **Druckverlauf** des Druckers.

## Wer was darf

Zum Bearbeiten und für **Inhalt löschen** brauchst du **Drucker und Druckvorlagen schreiben**. **Vorschau**, **Testdruck**, Herunterladen und Drucken brauchen **Dokumente drucken**. Ohne sie sind **Laufzettel bearbeiten**, **Inhalt löschen** und **Testdruck** deaktiviert.

## Beispiele

**Ein Los-Laufzettel zu jedem neuen Los.** Wähl **Los erstellt** als **Auslöser**, den Bürodrucker und **A4 ausgerichtet (in der Hälfte schneiden für A5-Laufzettel)**, dann schalt **Auto-Druck** ein. Jedes neue Los druckt einen Laufzettel, und die halbierte Seite ergibt das A5-Blatt, das mit den Teilen mitgeht.

**Ein Bestellung-Laufzettel als Datei.** Klick in der Tabelle der Bestellungen mit der rechten Maustaste auf die Bestellung und wähl **Laufzettel herunterladen**. Das PDF wird auf deinem Computer gespeichert, bereit zum Drucken oder zum Ablegen bei der Bestellung.

**Ein kaputtes Layout.** Du fügst eine Block-Spezifikation mit einer fehlenden Klammer ein. Der Editor zeigt, dass sie kein gültiges JSON ist, und das Speichern bleibt verweigert, bis du sie korrigierst.
