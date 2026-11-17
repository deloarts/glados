---
title: Abläufe freigeben
summary: Wie ein Ablauf angelegt oder kopiert, von einer Person nach der anderen bearbeitet, für den SPS-Programmierer freigegeben, überarbeitet und als ungültig markiert wird.
sourceRefs:
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - backend/src/modules/quality/application/use_cases/sequence/lock_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/release_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/revise_sequence.py
  - backend/src/modules/quality/application/use_cases/sequence/delete_sequence.py
  - frontend/src/features/sequences/components/SequenceControls.vue
  - frontend/src/features/sequences/components/SequencesTab.vue
lastVerified: 2026-11-10
---

Ein Ablauf ist ein gelenktes Dokument, wie eine Berechnung oder eine Prüfliste: Einen Entwurf bearbeitet immer nur eine Person, eine freigegebene Revision ändert sich nie mehr, und eine Korrektur ist eine neue Revision. Diese Seite beschreibt, was nur für Abläufe gilt. Die Regeln, die alle drei teilen, stehen unter [Dokumente bearbeiten](/handbook/workspace/document-editing) und [Revisionen und Freigabe](/handbook/workspace/document-revisions), und wie du die Schritte baust, unter [Abläufe](/handbook/workspace/flow-sequences).

## Einen Ablauf anlegen und kopieren

**Neuer Ablauf** im Reiter **Abläufe** eines Produkts fragt nach einem Namen. Wähle einen der vorgeschlagenen Namen, die aus der Liste **Ablaufnamen** unter Ressourcen, **Produktgeräte** kommen, oder gib einen eigenen ein. Ein Rechtsklick auf eine Zeile der Liste bietet **Kopieren** an, das einen neuen Entwurf mit denselben Schritten wie die Revision beginnt, die die Liste zeigt. In beiden Fällen öffnet sich der neue Entwurf zum Bearbeiten. Beides braucht die Berechtigung **Abläufe schreiben**; ohne sie ist **Neuer Ablauf** ausgegraut und nennt die Berechtigung im Tooltip, und **Kopieren** ist im Menü ausgegraut und nennt sie, wenn du darauf zeigst. Ein archiviertes Produkt nimmt keine neuen Abläufe an.

## Einen Entwurf bearbeiten

Ein gespeicherter Ablauf öffnet sich schreibgeschützt. **Bearbeiten** startet das Bearbeiten und hält den Entwurf für dich, sodass ihn inzwischen niemand sonst ändern kann. Bearbeiten darf ihn, wer ihn angelegt hat, und jede Person mit **Abläufe verwalten**. **Speichern** übernimmt deine Änderungen, und du bearbeitest weiter. **Fertig** beendet das Bearbeiten und heißt **Verwerfen**, solange es ungespeicherte Änderungen gibt, und fragt dann nach, bevor es sie wegwirft. Ungespeicherte Änderungen bleiben auf diesem Gerät, wenn du die Seite verlässt, und wer **Abläufe verwalten** hat, kann einen offen gelassenen Entwurf übernehmen. Eine Schaltfläche, für die dir die Berechtigung fehlt, ist ausgegraut, und ihr Tooltip nennt die Berechtigung.

## Freigeben

**Freigeben** zeichnet den Ablauf ab, und der SPS-Programmierer arbeitet mit dieser Revision. Das braucht **Abläufe freigeben**, und wer den Ablauf erstellt hat, darf ihn selbst freigeben. Während du bearbeitest, speichert **Freigeben** deine Änderungen vorher und beendet das Bearbeiten. Ein Ablauf ohne Schritte lässt sich nicht freigeben, und jedes Gerät, jede Stellung und jede Variante, die seine Schritte nennen, muss noch in Verwendung sein. Ein Schritt, der ein archiviertes Gerät nennt, muss also zuerst geändert werden. Die Freigabe behält Gerätenamen, Stellungen, Grundstellungen und Verfahrzeiten so, wie sie jetzt sind, und eine spätere Umbenennung eines Geräts ändert einen freigegebenen Ablauf nie.

## Neue Revisionen und Verlauf

**Neue Revision** beginnt die nächste Revision als Entwurf mit denselben Schritten und fragt nach einem Grund. Die freigegebene Revision bleibt gültig, bis die neue freigegeben ist, und heißt dann **Ersetzt**. **Verlauf** listet jede Revision mit ihrem Grund, und jede lässt sich öffnen. Eine ältere Revision zeigt einen Hinweis mit einem Link zur neuesten.

## Eine Revision als ungültig markieren

Eine Freigabe lässt sich nicht zurücknehmen. Stellt sich eine freigegebene Revision als falsch heraus, klickt jemand mit **Abläufe verwalten** auf **Als ungültig markieren** und gibt den Grund an. Die Revision bleibt dokumentiert, trägt neben ihrem Status die Markierung **Ungültig** und zeigt den Grund in einem roten Hinweis. Korrigiere sie in einer neuen Revision. **Löschen** entfernt nur einen Entwurf und fragt vorher nach.

## Beispiele

**Eine erste Freigabe.** Du baust den Automatikzyklus und klickst noch beim Bearbeiten auf **Freigeben**. Glados speichert die Schritte, beendet das Bearbeiten, und der Ablauf ist **Freigegeben**.

**Eine Korrektur nach der Inbetriebnahme.** Schritt 4 braucht eine längere Überwachungszeit. **Neue Revision** mit dem Grund „Längere Überwachungszeit für den Greifer“ beginnt einen Entwurf, und der SPS-Programmierer arbeitet mit der freigegebenen Revision weiter, bis du die Korrektur freigibst.

**Ein umbenanntes Gerät.** Aus B01 Hubzylinder P1 wird B01 Hebezylinder P1. Die freigegebene Revision behält den alten Namen, und die nächste Revision zeigt den neuen.
