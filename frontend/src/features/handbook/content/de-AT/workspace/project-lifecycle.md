---
title: Lebenszyklus eines Projekts
summary: Welche Status ein Projekt durchläuft, was pausiert, abgeschlossen und archiviert für seine Arbeit bedeuten und was verhindert, dass ein Projekt abgeschlossen oder gelöscht wird.
sourceRefs:
  - backend/src/modules/workspace/domain/services/lifecycle/project.py
  - backend/src/modules/workspace/domain/policies/project_activity.py
  - backend/src/modules/workspace/domain/value_objects/project_live_work.py
  - backend/src/modules/workspace/domain/services/project_rules.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Den Status eines Projekts setzt du von Hand unter **Status** in seinem Formular. Nichts leitet ihn aus den Losen oder Bestellungen des Projekts ab, aber sie bestimmen, welche Wechsel erlaubt sind. Diese Seite zeigt die Status und was jeder Wechsel bewirkt. Wie Projekte angelegt und bearbeitet werden, steht unter [Projekte](/handbook/workspace/projects).

<StateMachineEmbed machine-key="project_status" />

## Was jeder Status bedeutet

Ein neues Projekt beginnt **Aktiv**, und nur ein aktives Projekt nimmt neue Arbeit an: neue Bedarfe, neue Lose, Bestellpositionen, die darauf verschoben werden, und Positionen, die darauf wieder geöffnet werden. **Pausiert** stoppt neue Arbeit, die offene Arbeit läuft aber weiter, laufende Lose werden also fertig und bestellte Teile weiterhin geliefert. **Abgeschlossen** und **Archiviert** schließen das Projekt. Arbeit, die schon auf einem nicht aktiven Projekt liegt, lässt sich weiterhin bestellen, liefern, korrigieren und abschließen, damit sie aufgeräumt werden kann. Aktive Projekte erscheinen im Widget **Aktuelle Projekte** eines Infoscreens.

## Den Status wechseln

Ein aktives Projekt wird pausiert, und ein pausiertes wird wieder aktiv. Abgeschlossen wird ein Projekt aus aktiv oder pausiert, archiviert aus jedem dieser drei. Ein abgeschlossenes oder archiviertes Projekt lässt sich wieder öffnen und ist dann wieder aktiv. Jeder Wechsel braucht **Projekte verwalten**. Die zuständige Person darf den Rest des Projekts bearbeiten, aber nicht seinen Status. Im Formular bleibt ein Status, in den das Projekt gerade nicht wechseln kann, in der Liste, ausgegraut, mit dem Grund darunter: die fehlende Berechtigung, die offene Arbeit oder der aktuelle Status, aus dem es so nicht herauskommt.

## Offene Arbeit

Abschließen, Archivieren und Löschen setzen voraus, dass das Projekt keine offene Arbeit hat: kein Los, das weder abgeschlossen, storniert noch verschrottet ist, keinen Fertigungsauftrag, der weder abgeschlossen noch storniert ist, keine Bestellposition, die weder geliefert noch storniert ist, keinen offenen Bedarf und keine offene Anfrage mit einer Position für das Projekt. Der Grund unter dem Status nennt die Anzahl, etwa 2 Lose und 1 Bestellposition. Pausieren ist auch mit offener Arbeit erlaubt.

## Beispiele

**Ein Kunde pausiert den Auftrag.** Du setzt das Projekt auf **Pausiert**. Die Lose in der Fertigung laufen weiter, aber niemand kann einen Bedarf hinzufügen, bis du es wieder auf **Aktiv** setzt.

**Ein fertiges Projekt abschließen.** Eine Bestellposition ist noch offen, daher ist **Abgeschlossen** ausgegraut und nennt sie. Sobald die Position geliefert oder storniert ist, schließt du das Projekt ab.

**Ein Folgeauftrag.** Der Kunde bestellt Ersatzteile für ein abgeschlossenes Projekt. Setzt du es wieder auf **Aktiv**, nimmt es neue Bedarfe an.
