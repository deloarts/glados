---
title: Revisionen und Freigabe
summary: Wie Berechnungen, Prüflisten und Abläufe ihre Dokumentnummer und Revisionen bekommen, endgültig freigegeben, als ungültig markiert und in den Listen gefunden werden.
sourceRefs:
  - backend/src/modules/quality/domain/entities/controlled_document.py
  - backend/src/modules/quality/application/services/controlled_documents.py
  - backend/src/modules/platform/adapters/outbound/persistence/number_counters.py
  - backend/src/modules/quality/domain/services/calculation_rules.py
  - backend/src/modules/quality/domain/services/checklist_rules.py
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - frontend/src/shared/documents/utils/rowMenu.ts
lastVerified: 2026-11-10
---

Berechnungen, Prüflisten und Abläufe sind gelenkte Dokumente: Eine freigegebene Revision ändert sich nie mehr, und eine Korrektur ist eine neue Revision. Ein Produkt zeigt sie in seinen Reitern **Berechnungen**, **Prüflisten** und **Abläufe**, ein Projekt in seinen Reitern **Berechnungen** und **Prüflisten**. Wie du einen Entwurf bearbeitest, steht unter [Dokumente bearbeiten](/handbook/workspace/document-editing), und was nur für Abläufe gilt, unter [Abläufe freigeben](/handbook/workspace/flow-sequence-release).

## Dokumentnummern

Jedes Dokument bekommt beim ersten Speichern eine Nummer, zum Beispiel CAL-26-0042 für eine Berechnung, CHK-26-0017 für eine Prüfliste oder SEQ-26-0003 für einen Ablauf. Alle Revisionen des Dokuments teilen sie, daher bezeichnet CAL-26-0042 Rev. B genau eine Revision. Die Nummer steht in der Infoleiste, in den Listen und auf jedem Bericht, und die Suche findet ein Dokument auch mit ihr. Administratoren legen die Formate unter Einstellungen, **Nummerierung** fest. Ein geändertes Format gilt nur für neue Dokumente.

## Revisionen

Die Revisionen werden gezählt wie in den Einstellungen für Revisionen von Fertigungsteilen, zum Beispiel 0, 1, 2 oder A, B, C. Eine noch nicht freigegebene Revision erscheint als B (Entwurf). **Neue Revision** setzt ein freigegebenes Dokument fort: Die neue Revision beginnt als Entwurf mit demselben Inhalt und der Begründung, die du angibst. Die freigegebene Revision bleibt gültig, bis die neue freigegeben ist, dann ist sie ersetzt. Eine ältere Revision zeigt einen Hinweis mit einem Link zur neuesten. **Als neu speichern** bei einer Berechnung ist etwas anderes, denn es beginnt eine eigenständige Berechnung mit eigener Nummer und eigenen Revisionen.

## Freigeben

Mit der Freigabe zeichnest du eine Revision ab. Sie ändert sich danach nie mehr und wird nie gelöscht, auch nicht von Administratoren; löschen lassen sich nur Entwürfe. Eine Berechnung und einen Ablauf darf ihr Ersteller freigeben, mit **Berechnungen freigeben** oder **Abläufe freigeben**. Eine Prüfliste, deren Art eine Freigabe verlangt, braucht eine zweite Person mit **Prüflisten freigeben**, denn wer eine Revision erstellt hat, gibt sie nie selbst frei. Ohne die Berechtigung ist **Freigeben** ausgegraut, und sein Tooltip nennt sie.

## Eine Revision als ungültig markieren

Eine Freigabe lässt sich nicht zurücknehmen. Stellt sich eine freigegebene Revision als falsch heraus, klickt jemand mit der Verwaltungsberechtigung ihrer Art, etwa **Berechnungen verwalten**, auf **Als ungültig markieren** und gibt die Begründung an. Die Revision bleibt dokumentiert, zeigt einen roten Hinweis mit der Begründung, und jeder Bericht daraus trägt einen Warnhinweis. Korrigiere sie in einer neuen Revision. Wird eine Revision als ungültig markiert oder eine neue Revision begonnen, bekommt jede Person, die eine Revision des Dokuments erstellt oder gespeichert hat, eine Benachrichtigung.

## In den Listen

Die Listen zeigen bei jedem Dokument die Revision, wer es wann freigegeben hat, ob es als ungültig markiert ist, und ein Schloss, solange es jemand bearbeitet. Ein Rechtsklick auf eine Zeile öffnet ihr Menü: öffnen, auch in einem neuen Tab, Link kopieren, drucken, wo es einen Bericht gibt, und die Schritte des Dokuments selbst, etwa **Bearbeiten**, **Verlauf**, **Neue Revision**, **Freigeben** und **Als ungültig markieren**. Diese öffnen das Dokument und starten den Schritt dort. **Löschen** gibt es nur für Entwürfe. Ein Schritt, den das Dokument zulässt, den du aber nicht ausführen darfst, ist ausgegraut, und zeigst du darauf, nennt er die fehlende Berechtigung oder wer das Dokument gerade bearbeitet.

## Ausgedruckte Kopien

Jeder Bericht einer gespeicherten Berechnung oder Prüfliste trägt einen QR-Code, der genau diese Revision öffnet. Wer einen Ausdruck in der Hand hat, kann so jederzeit prüfen, ob er noch gültig ist. Siehe [Berichte exportieren und drucken](/handbook/resources/report-export).

## Beispiele

**Eine Prüfliste abzeichnen.** Der Konstrukteur füllt die CE-Prüfliste aus und bittet die Sicherheitsingenieurin, sie freizugeben. Er selbst kann sie nicht freigeben, weil er diese Revision erstellt hat.

**Ein später gefundener Fehler.** Eine freigegebene Antriebsauslegung hat mit der falschen Last gerechnet. Jemand mit Verwaltungsberechtigung markiert CAL-26-0042 Rev. A als ungültig, und der Konstrukteur korrigiert die Last in Rev. B.
