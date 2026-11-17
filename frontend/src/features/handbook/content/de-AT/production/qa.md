---
title: QS-Prüfungen
summary: Was der Reiter QS listet, wie du ihn filterst und wie du auf der Seite einer QS-Aufgabe eine Prüfung startest, Nachweise anhängst und ihr Ergebnis erfasst.
sourceRefs:
  - frontend/src/features/production-qa/components/QaControls.vue
  - frontend/src/features/production-qa/components/QaViews.vue
  - frontend/src/features/production-qa/components/QaTaskTable.vue
  - frontend/src/features/production-qa/views/ProductionQaTaskView.vue
  - frontend/src/features/production-qa/components/QaTaskControls.vue
  - backend/src/modules/fulfillment/application/use_cases/production_order/get_qa_tasks.py
lastVerified: 2026-11-10
---

Eine Prüfung ist eine Position eines Loses wie jede andere, und ihr Fertigungsauftrag ist die QS-Aufgabe. Der Auftrag wird eingeplant, sobald das Los angelegt ist. Ist **Qualitätsprüfung erforderlich** unter Systemeinstellungen, Produktion eingeschaltet, bekommt jedes neue Los, dessen Arbeitsplan nicht mit einer Prüfung endet, eine angehängt. Der Reiter **QS** unter Produktion listet diese Aufgaben für die Prüfenden, und ein Klick auf eine Zeile öffnet die eigene Seite der Aufgabe.

## Die Arbeitsliste {#list}

Die Leiste oben zählt die Aufgaben, die **Bereit** sind, und die, denen noch ein Nachweis fehlt. **Nur Lesen** erscheint, wenn dir **Qualitätsprüfungen erfassen** fehlt, das jedes Ergebnis braucht. **Bereitschaft** sagt, wo eine Aufgabe steht: **Wartet**, solange der Schritt davor keine Stück bereitgestellt hat, **Bereit**, wenn sie starten kann, danach **In Arbeit**, **Pausiert**, **Erledigt** oder **Storniert**. **Nachweise** zeigt, ob das Messprotokoll, das eine Methode verlangt, vorliegt.

Von Haus aus zeigt die Liste offene Aufgaben, die jetzt bearbeitet werden können. **Abgeschlossene anzeigen**, **Stornierte anzeigen** und **Zukünftige anzeigen** fügen die erledigten, die stornierten und die hinzu, die noch nicht starten können, nicht geplant sind oder erst nach heute geplant sind. Die Suche findet eine Auftragsnummer, und der Mengenfilter nimmt ein Minimum und ein Maximum.

## Die Seite einer Aufgabe {#task}

Links stehen das Teil mit Werkstoff, Los, Position, Projekt, Menge und geplantem Start sowie 3D-Modell und Zeichnung, wenn sie hinterlegt sind. Rechts stehen die Prüfmethode mit Prüfanweisung und Notizen, die bisher erfassten Ergebnisse und die Nachweisdateien.

**QS starten**, oder **QS fortsetzen** bei einer pausierten Aufgabe, startet die Prüfung. Das braucht **Fertigungsaufträge schreiben** und **Qualitätsprüfungen erfassen** und wartet, bis der Schritt davor Stück fertig hat. **Ergebnis erfassen** öffnet den Dialog mit **Angenommen** und **Zurückgewiesen**, erklärt in [Fertigmeldungen erfassen](/handbook/production/completions#rejects). **Dokument hinzufügen** nimmt Fotos oder Dateien direkt in die Nachweise, und **Prüfbericht** druckt den Bericht des Loses. Ohne die Berechtigungen sind diese Schaltflächen deaktiviert, und ihr Tooltip nennt die Berechtigung, die sie brauchen.

## Nachweise {#evidence}

Verlangt die Prüfmethode einen Nachweis, lässt sich das Ergebnis erst erfassen, wenn ein Messprotokoll hochgeladen ist. Die Aufgabe zeigt das als Warnung, und die Arbeitsliste zählt sie unter den fehlenden Nachweisen. Lad das Protokoll im Nachweisbereich hoch oder fotografier es mit **Dokument hinzufügen** am Tablet oder Handy.

## Beispiele

Ein Los mit 12 Wellen ist fertig gedreht. Seine QS-Aufgabe zeigt **Bereit**. Öffne sie, klick auf **QS starten**, miss die Wellen und erfasse mit **Ergebnis erfassen** 12 **Angenommen**.

Einer Aufgabe fehlt ein Nachweis. Öffne sie, lad das Messprotokoll im Nachweisbereich hoch, und **Ergebnis erfassen** kann das Ergebnis speichern.

Du willst die Prüfungen der letzten Woche sehen. Schalte **Abgeschlossene anzeigen** ein und sortiere nach geplantem Datum.
