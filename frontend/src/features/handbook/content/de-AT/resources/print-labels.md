---
title: Druck-Etiketten
summary: Wie du jedes Etikett einrichtest, wann es von selbst druckt, was bei einem fehlgeschlagenen Druck passiert und wo du Etiketten von Hand druckst.
sourceRefs:
  - backend/src/modules/quality/application/use_cases/print_template/update_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/reset_print_template.py
  - backend/src/modules/quality/application/use_cases/print_template/preview_print_template.py
  - backend/src/modules/quality/domain/services/print_template_rules.py
  - backend/src/modules/quality/domain/services/zpl_template.py
  - backend/src/modules/quality/application/use_cases/print_document/print_document.py
  - backend/src/modules/quality/application/use_cases/print_document/handle_event_auto_print.py
lastVerified: 2026-11-10
---

Unter Ressourcen hat **Druck-Etiketten** eine Zeile pro Etikettenart: **Rohblock-Etikett**, **Kaufartikel-Etikett**, **Fertigungsteil-Etikett**, **Fertigungsauftrag-Etikett**, **Los-Etikett** und **Ausschuss-Etikett**. Die Zeilen stehen fest und lassen sich weder anlegen noch löschen; du richtest jede nur ein.

## Ein Etikett einrichten {#setup}

Klick mit der rechten Maustaste auf eine Zeile und wähl **Etikett bearbeiten**. **Auslöser** ist **Nur manuell** oder eines der Ereignisse, die zu diesem Etikett passen. **Drucker** bietet nur Etikettendrucker an; ein archivierter steht zuletzt und trägt eine Warnung. **Auto-Druck** bleibt ausgegraut, bis ein Auslöser gewählt ist, und ein Etikett, das nicht **Aktiviert** ist, druckt nie.

**Kopienregel** bestimmt, wie viele Kopien ein Druck macht. **Fest** druckt die **Feste Kopienanzahl**. **Pro Vorgangsmenge** druckt eine Kopie pro geliefertem oder fertiggemeldetem Stück, **Pro Losmenge** eine pro Stück des Loses; jedes Etikett bietet nur die Regeln an, die zu ihm passen. **Max. Kopien** ist die feste Obergrenze für jeden einzelnen Druck. Ein von Hand gedrucktes Etikett macht immer die **Feste Kopienanzahl**.

## Der Inhalt

**ZPL-Quelltext** enthält das Etikett in der Etikettendruckersprache ZPL; tipp ihn ein oder klick auf **Hochladen** für eine .zpl- oder .txt-Datei. Jeder Name in geschweiften Klammern ist ein Platzhalter, und die **Feldzuordnung** verknüpft jeden mit einer Angabe dieses Etiketts, etwa der Teilenummer. Gib im Vorschaubereich eine **Datensatz-ID** ein, dann siehst du ein Bild des Etiketts für einen echten Datensatz. **Aus Datei importieren** und **In Datei exportieren** übertragen ein Etikett zwischen Systemen; die Etikettengröße kommt nur aus einer importierten Datei.

Beim Speichern wird geprüft, ob Auslöser und Kopienregel zu diesem Etikett passen, ob jeder Platzhalter zugeordnet ist, ob der Quelltext ein vollständiges Etikett ist und ob der Drucker ein Etikettendrucker ist. **Inhalt löschen** leert Quelltext, Feldzuordnung und Größe und schaltet das Etikett aus, behält aber Auslöser, Drucker und **Auto-Druck**.

## Von selbst drucken

Ein Etikett druckt bei seinem Auslöser nur, wenn es aktiviert ist, für **Auto-Druck** scharf geschaltet ist und einen Drucker hat. **Auto-Druck deaktivieren** schaltet das bei allen Etiketten auf einmal ab und lässt den manuellen Druck in Ruhe. **Alle Drucker deaktivieren** stoppt jeden Druck.

## Wenn ein Druck fehlschlägt

Ein fehlgeschlagener Druck hält die Arbeit in der Werkstatt nie auf. Die Lieferung, Fertigmeldung oder der Ausschuss wird erfasst, und der Druck steht als **Fehlgeschlagen** mit dem Grund im **Druckverlauf** des Druckers. Ein von Hand gestarteter Druck zeigt den Grund zusätzlich in einer Meldung. Genauso geht es, wenn das Etikett deaktiviert oder leer ist, keinen Drucker hat oder sein Drucker deaktiviert oder archiviert ist, siehe [Drucker](/handbook/resources/printers).

## Wo Etiketten gedruckt werden

Klick im Rohblock-, Zukaufteile- oder Fertigungsteilekatalog mit der rechten Maustaste auf ein Teil und wähl **Etikett drucken**, oder nimm auf seiner Seite **Drucken** und **Etikett**. In der Lostabelle bietet **Drucken** die Punkte **Los-Etikett drucken** und **Ausschuss-Etikett**, die Losseite hat beide unter **Laufzettel drucken** als **Los-Etikett drucken** und **Ausschuss-Anhänger drucken**. **Teile verschrotten** bietet **Ausschuss-Etikett drucken** an, angehakt, wenn das **Ausschuss-Etikett** einen Drucker hat. Die Karten der Fertigungswarteschlange und die Maschinenseite bieten **Etikett drucken** und **Laufzettel drucken**.

## Wer was darf

Zum Bearbeiten und für **Inhalt löschen** brauchst du **Drucker und Druckvorlagen schreiben**. **Vorschau**, **Testdruck** und Drucken brauchen **Dokumente drucken**. Ohne sie sind **Etikett bearbeiten**, **Inhalt löschen** und **Testdruck** deaktiviert. Ein automatischer Druck braucht keine Berechtigung der Person, deren Aktion ihn ausgelöst hat.

## Beispiele

**Ein Los-Etikett für jedes neue Los.** Wähl **Los erstellt** als **Auslöser**, den Hallendrucker, **Pro Losmenge** und **Max. Kopien** 20, dann schalt **Auto-Druck** ein. Ein Los mit 12 Stück druckt 12 Etiketten, ein Los mit 50 Stück druckt 20.

**Eine Lieferung bei ausgeschaltetem Drucker.** Das **Kaufartikel-Etikett** druckt bei **Kaufartikel geliefert**, aber sein Drucker ist deaktiviert. Die Lieferung wird trotzdem gebucht, und der Druck steht mit dem Grund als **Fehlgeschlagen** da.
