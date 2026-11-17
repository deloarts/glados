---
title: Dokumente bearbeiten
summary: Wie Berechnungen, Prüflisten und Abläufe von einer Person nach der anderen bearbeitet werden, wie nicht gespeicherte Änderungen erhalten bleiben und wie ein offen gelassener Entwurf übernommen wird.
sourceRefs:
  - backend/src/modules/quality/domain/entities/controlled_document.py
  - backend/src/modules/quality/domain/services/document_control.py
  - frontend/src/shared/documents/composables/useDocumentLock.ts
  - frontend/src/shared/documents/composables/useLocalDraft.ts
  - frontend/src/shared/composables/useLeaveGuard.ts
  - frontend/src/features/tools/components/ToolCalculationControls.vue
  - frontend/src/features/checklists/components/ChecklistControls.vue
  - frontend/src/features/sequences/components/SequenceControls.vue
lastVerified: 2026-11-10
---

Berechnungen, Prüflisten und Abläufe sind Dokumente, die in den technischen Unterlagen einer Maschine landen können. Deshalb bearbeitest du sie alle gleich: Einen Entwurf bearbeitet immer nur eine Person, und nichts, was du eingibst, geht beim Arbeiten verloren. Du öffnest sie über die Reiter eines Produkts oder Projekts. Wie sie nummeriert, freigegeben und überarbeitet werden, steht unter [Revisionen und Freigabe](/handbook/workspace/document-revisions).

## Einen Entwurf bearbeiten

Ein gespeicherter Entwurf öffnet sich schreibgeschützt. Klick auf **Bearbeiten**, um ihn zu ändern. Einen Entwurf bearbeitet die Person, die ihn angelegt hat, oder jemand mit der Verwaltungsberechtigung seiner Art, etwa **Prüflisten verwalten**. Ohne die Berechtigung ist **Bearbeiten** ausgegraut, und sein Tooltip nennt, was fehlt. Ab dann hältst du den Entwurf: Andere sehen einen Hinweis mit deinem Namen und seit wann du ihn bearbeitest, und sie können ihn nicht speichern, freigeben oder bearbeiten, bis du fertig bist.

**Speichern** übernimmt deine Änderungen in den Entwurf, und du bearbeitest weiter. **Fertig** beendet das Bearbeiten; solange es nicht gespeicherte Änderungen gibt, heißt es **Verwerfen** und fragt nach, bevor es sie wegwirft. **Freigeben** geht auch während des Bearbeitens: Es speichert deine Änderungen vorher und beendet das Bearbeiten. Auch das Verlassen der Seite beendet das Bearbeiten.

Arbeitet etwa 13 Minuten lang niemand auf der Seite, endet das Bearbeiten von selbst und der Entwurf ist wieder frei, eine über Nacht offene Seite blockiert also niemanden. Schließt du den Browser beim Bearbeiten, ist der Entwurf nach 15 Minuten wieder frei.

In einem Berechnungswerkzeug kannst du auch ohne **Bearbeiten** andere Eingaben ausprobieren. Solche Werte stehen nur auf deinem Bildschirm, und **Speichern** legt sie als neue Berechnung ab. Ein Werkzeug ohne gespeicherte Berechnung merkt sich seine Eingaben auf diesem Gerät, auch wenn du den Tab wechselst oder neu lädst, bis **Neu** sie löscht oder **Speichern** daraus eine Berechnung macht.

## Nicht gespeicherte Änderungen

Nicht gespeicherte Änderungen bleiben beim Arbeiten auf diesem Gerät erhalten. Es geht also nichts verloren, wenn du die Seite verlässt, neu lädst, den Browser schließt, deine Sitzung abläuft oder jemand übernimmt. Verlässt du eine Seite mit nicht gespeicherten Änderungen, fragt Glados vorher nach.

Öffnest du das Dokument wieder, bietet Glados dir die Änderungen mit ihrem Zeitpunkt an. **Wiederherstellen** holt sie zurück und startet das Bearbeiten, **Verwerfen** löscht sie, und Schließen des Dialogs hebt sie für später auf. Hat jemand das Dokument inzwischen gespeichert, warnt der Dialog, dass deine Änderungen die neuere Fassung ersetzen. Aufgehobene Änderungen werden nur dir angeboten und bleiben, bis du sie speicherst oder verwirfst, auch wenn du dich abmeldest. Änderungen, zu denen niemand zurückkommt, werden nach zehn Wochen gelöscht.

## Übernehmen

Hat jemand einen Entwurf offen gelassen und ist nicht erreichbar, kann jemand mit **Berechnungen verwalten**, **Prüflisten verwalten** oder **Abläufe verwalten** im Hinweis auf **Übernehmen** klicken, um selbst zu bearbeiten, oder auf **Bearbeitung beenden**, um den Entwurf für alle freizugeben. Die andere Person wird benachrichtigt, und ihre nicht gespeicherten Änderungen bleiben nur auf ihrem Gerät.

## Beispiele

**Ein langes Telefonat.** Du lässt eine Prüfliste beim Bearbeiten offen. Nach etwa 13 Minuten endet das Bearbeiten, und deine Antworten bleiben auf diesem Gerät. Glados bietet sie dir wieder an, und **Wiederherstellen** holt sie zurück.

**Eine Kollegin auf Urlaub.** Eine Entwurfsberechnung zeigt, dass eine Kollegin sie seit Montag bearbeitet. Jemand mit **Berechnungen verwalten** klickt auf **Übernehmen** und arbeitet am Entwurf weiter.
