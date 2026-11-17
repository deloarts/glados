---
title: Projekte
summary: Wie die Projektliste und die Seite eines Projekts seine Bedarfe, Bestellungen, Kosten und Dokumente zeigen, und wer ein Projekt anlegen, bearbeiten und löschen darf.
sourceRefs:
  - backend/src/modules/workspace/domain/services/project_rules.py
  - backend/src/modules/workspace/domain/policies/project_activity.py
  - backend/src/modules/workspace/application/use_cases/project/create_project.py
  - backend/src/modules/workspace/application/use_cases/project/update_project.py
  - backend/src/modules/workspace/application/use_cases/project/delete_project.py
  - frontend/src/features/projects/components/ProjectFormDialog.vue
  - frontend/src/features/workspace/views/ProjectDetailView.vue
lastVerified: 2026-11-10
---

Workspace, **Projekte** listet jedes Projekt: einen Kundenauftrag, eine Maschine oder einen Teil davon zu bauen, zu dem Bedarfe, Lose, Bestellungen, Berechnungen und Prüflisten gehören. Ein Projekt gehört meist zu einem [Produkt](/handbook/workspace/products), der Maschine, die es baut, und mehrere Projekte können ein Produkt teilen. Am Handy bietet Workspace nur die Projekte an, und ein Projekt nur seine Übersicht.

## Die Projektliste

Die Spalten filtern nach Status, Nummer, Produkt, Kunde, Beschreibung, Lieferterminen, zuständigem Benutzer und Erstelldatum, und die Ansichtsleiste sortiert und gruppiert nach **Kunde** oder **Status**. Ein Klick auf eine Zeile öffnet die Seite des Projekts. Ein Rechtsklick bietet **Projektdetails**, **Projekt bearbeiten**, **Artikel anzeigen** und **Löschen** an. **Artikel anzeigen** listet die Zukaufteile des Projekts mit **Menge angefragt** und **Menge geliefert**.

## Ein Projekt anlegen und bearbeiten

**Projekt erstellen** braucht **Projekte schreiben**. Die **Projektnummer** muss zum **Muster für Projektnummer** unter Einstellungen, **Nummerierung** passen. Ein **Produkt** ist Pflicht, außer **Projekte ohne Produkt zulassen** ist unter Einstellungen, **Allgemein** eingeschaltet. **Zuständiger Benutzer** bist du, und nur wer **Projekte verwalten** hat, kann eine andere Person wählen. **Fertigungszeitbudget** ist optional und gibt der Planung die für das Projekt verkauften Fertigungsminuten. **Liefertermin (Eigenfertigung)** und **Liefertermin (Zukaufteile)** belegen neue Bedarfe des Projekts vor. Änderst du einen davon, fragt Glados, ob du ihn **Für alle übernehmen** willst oder **Nur dieses Projekt** änderst.

Ein Projekt bearbeitet seine zuständige Person oder jede Person mit **Projekte verwalten**. Für alle anderen ist **Projekt bearbeiten** ausgegraut, und sein Tooltip sagt, warum. Den **Status** zu ändern braucht **Projekte verwalten**, und ein Status, in den das Projekt nicht wechseln kann, ist ausgegraut und nennt darunter den Grund, wie unter [Lebenszyklus eines Projekts](/handbook/workspace/project-lifecycle) beschrieben.

## Die Seite eines Projekts

Die **Übersicht** zeigt die Details, die Zahlen zu Beschaffung und Fertigung wie **Gesamt bestellt** und **Gesamt geliefert** und Links zu den anderen Reitern. **Stückliste** listet Zukaufteile, Fertigungsteile und Rohblöcke mit dem Status ihres Bedarfs. **Bestellungen** listet die Lieferantenbestellungen mit den Kosten für das Projekt, und **Kosten** teilt sie nach Lieferanten auf. **Berechnungen** und **Prüflisten** erscheinen, solange diese Funktionen eingeschaltet sind, und enthalten die Dokumente des Projekts, mit **Neue Berechnung** und **Neue Prüfliste**; siehe [Revisionen und Freigabe](/handbook/workspace/document-revisions).

## Ein Projekt löschen

**Löschen** braucht **Projekte verwalten** und ein Projekt ohne offene Arbeit: keine offenen Lose, Fertigungsaufträge, Bestellpositionen, Bedarfe oder Anfragen. Sonst ist die Schaltfläche ausgegraut, und ihr Tooltip nennt, was fehlt, oder zählt die offene Arbeit auf.

## Beispiele

**Ein neuer Kundenauftrag.** Du legst Projekt 24-118 für Produkt M-2045 an, setzt den Liefertermin für Zukaufteile auf den 3. März und legst die Bedarfe an. Jeder neue Bedarf an Zukaufteilen beginnt mit dem 3. März.

**Ein Liefertermin verschiebt sich.** Der Kunde verschiebt die Maschine um zwei Wochen. Du änderst **Liefertermin (Eigenfertigung)** und wählst **Für alle übernehmen**, und jeder offene Bedarf an Fertigungsteilen des Projekts wandert mit.

**Ein versehentlich angelegtes Projekt.** Es hat noch keine Bedarfe, also löscht es jemand mit **Projekte verwalten** aus der Liste.
