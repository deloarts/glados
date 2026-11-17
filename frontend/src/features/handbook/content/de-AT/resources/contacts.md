---
title: Kontakte
summary: Wie du die Leute von Kunden und Lieferanten als Kontakte führst, welche Mails sie erreichen, wie Produkte und Projekte sie für die Besprechungsprotokolle verknüpfen und wie du einen Kontakt anonymisierst.
sourceRefs:
  - frontend/src/features/contacts/views/ContactManagementView.vue
  - frontend/src/features/contacts/components/ContactFormDialog.vue
  - frontend/src/features/contacts/components/ContactLinksSection.vue
  - backend/src/modules/catalogue/domain/services/contact_rules.py
  - backend/src/modules/catalogue/application/use_cases/contact/anonymise_contact.py
  - backend/src/modules/workspace/domain/services/contact_link_rules.py
lastVerified: 2026-11-10
---

Ein Kontakt ist eine Person, mit der du zu tun hast: die Projektleiterin eines Kunden, der Verkäufer eines Lieferanten oder jemand Unabhängiges wie ein Prüfer. Ressourcen, **Kontakte** listet sie alle mit Name und Rolle, E-Mail, Telefon, Organisation und wo sie verwendet werden. Kontakte sind personenbezogene Daten, darum brauchst du zum Lesen die Berechtigung **Kontakte lesen** und zum Ändern **Kontakte schreiben**. Ohne das Recht zum Ändern bleiben die Schaltflächen sichtbar, aber deaktiviert.

## Einen Kontakt anlegen

**Neuer Kontakt** öffnet das Formular. Nur **Name** ist Pflicht. **Rolle**, **E-Mail**, **Telefon**, **Mobil** und **Notiz** sind optional. **Gehört zu** bindet den Kontakt an höchstens einen Kunden oder einen Lieferanten, oder an keinen. Die Formulare von Kunden und Lieferanten haben einen Abschnitt **Kontakte**, der ihre Leute listet und neue anlegt, sobald der Kunde oder Lieferant gespeichert ist.

**Gruppieren nach** **Organisation** gruppiert die Tabelle nach Kunden und Lieferanten, und **Archivierte anzeigen** zeigt auch die archivierten Kontakte.

## Lieferanten-Mails

Bei einem Kontakt eines Lieferanten lassen sich **Erhält Anfrage-Mails** und **Erhält Bestell-Mails** anhaken. Die Anfragen und Bestellmails des Lieferanten gehen dann an die angehakten Kontakte. Solange kein Kontakt eines Lieferanten angehakt ist, gehen sie an die eigenen Adressen des Lieferanten.

## Produkte, Projekte und die Besprechungsprotokolle

Die Übersicht eines Produkts und eines Projekts hat einen Abschnitt **Kontakte**. **Kontakt verknüpfen** fügt einen hinzu, wobei die Kontakte des Kunden des Eintrags zuerst angeboten werden, und **Besprechungsprotokolle** sagt, ob der Kontakt die Besprechungsprotokolle erhält, die der Versand dann vorschlägt und anhakt. Jedes Projekt eines Produkts übernimmt die Kontakte des Produkts. Ein Projekt kann einen übernommenen Kontakt nicht lösen, aber für sich den Haken bei **Besprechungsprotokolle** entfernen, das schaltet den Kontakt nur für dieses Projekt stumm. Das Verknüpfen folgt dem Recht, das Produkt oder Projekt zu bearbeiten.

## Archivieren und anonymisieren

Ein Kontakt wird archiviert, nie gelöscht. Ein archivierter Kontakt bleibt bei allen Produkten, Projekten und Besprechungen, die ihn nennen, wird aber für neue nicht mehr angeboten. **Wiederherstellen** im Kontaktformular oder in der Tabelle holt ihn zurück.

Möchte eine Person vergessen werden, entfernt **Anonymisieren** im Kontaktformular Name, E-Mail-Adresse, Telefonnummern und Notiz endgültig und archiviert den Kontakt. Dieselben Angaben verschwinden aus den Besprechungen, die die Person als Teilnehmende oder zuständig für eine Aufgabe nennen, und aus den Ständen gesendeter Protokolle, während der Nachweis, dass das Protokoll hinausging, bleibt. Zum Anonymisieren brauchst du **Kontakte schreiben** zusammen mit **Besprechungen verwalten**, und es lässt sich nicht rückgängig machen.

## Beispiele

**Die Projektleiterin der Kundschaft.** Du legst Eva Bogus an, Rolle Projektleiterin, gehört zum Kunden Acme Maschinenbau, und verknüpfst sie beim Produkt mit Haken bei **Besprechungsprotokolle**. Jedes Projekt des Produkts schlägt sie nun vor, wenn sein Protokoll gesendet wird.

**Ein Projekt ohne sie.** Bei einem Projekt dieses Produkts entfernst du für Eva den Haken bei **Besprechungsprotokolle**. Seine Protokolle schlagen sie nicht mehr vor, die anderen Projekte schon.

**Ein neuer Sachbearbeiter für Bestellungen.** Beim Lieferanten hakst du für den neuen Sachbearbeiter **Erhält Bestell-Mails** an. Die nächste Bestellmail trägt unter An ihn ein statt der Bestelladresse des Lieferanten.
