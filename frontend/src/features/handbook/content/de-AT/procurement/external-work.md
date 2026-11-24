---
title: Fremdbearbeitung
summary: Wie die Liste Fremdbearbeitung zeigt, welche Teile zum Härten, Beschichten oder einer anderen Bearbeitung zu einem Lieferanten gehen, bis wann sie weg müssen und wie du sie einem Lieferanten gibst.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/external_work/get_external_work.py
  - backend/src/modules/fulfillment/domain/services/scheduling/external_work.py
  - backend/src/modules/fulfillment/domain/services/scheduling/external_work_explanation.py
  - frontend/src/features/procurement/components/ExternalWorkTable.vue
  - frontend/src/features/procurement/composables/useExternalWorkRowMenu.ts
lastVerified: 2026-11-24
---

**Fremdbearbeitung** im Einkauf listet jedes Teil eines offenen Loses, das für eine Bearbeitung außer Haus zu einem Lieferanten geht, etwa zum Härten oder Verzinken. Sie zeigt dir, wann das Teil gehen kann, bis wann es gehen muss, damit die Schritte danach nicht zu spät kommen, und wann es zurückkommt. So kannst du Teile für einen Lieferanten sammeln und gemeinsam schicken.

## Welche Teile erscheinen

Ein Teil erscheint, sobald sein Losschritt auf einer Bestellung bei einem Lieferanten steht, oder solange es auf einen Lieferanten wartet und sein Fertigungsverfahren als normalerweise fremd vergeben markiert ist. Lose mit nur internen Schritten erscheinen nicht. Gib den fremd vergebenen Verfahren eine Lieferzeit und einen Standardlieferanten, sonst bekommen ihre Teile keine Termine und keinen Vorschlag.

## Was die Termine bedeuten

**Bereit ab** ist, wann der Schritt davor fertig ist oder das Rohmaterial da ist, plus die Reaktionszeit. **Spätestens weg** rechnet vom Zieltermin des Loses zurück: abzüglich des Sicherheitsabstands, der Schritte danach und der Lieferzeit. **Zurück bis** ist der Termin des Lieferanten, sobald die Bestellposition einen hat, sonst **Spätestens weg** plus die Lieferzeit. Fahre über die kleine Zeile unter einem Termin, dann siehst du, wie er gerechnet wurde. Den Sicherheitsabstand stellst du in den Produktionseinstellungen unter **Sicherheitsabstand für Fremdbearbeitung (Tage)** ein.

Ein Hinweis in der Spalte **Hinweis** markiert ein Teil, das bis zu seinem Tag **Spätestens weg** nicht fertig wird, eines, dessen Tag **Spätestens weg** schon vorbei ist, und ein Los ohne Zieltermin.

## Gruppieren und Filtern

**Gruppieren nach** ordnet die Seite nach **Verfahren** oder **Lieferant**. Jede Gruppe zeigt ihren nächsten Versandtag und wie viele Teile kritisch sind. **Nur mit Lieferant** blendet die Teile aus, die noch niemand bestellt hat, **Nur kritische** lässt nur die späten stehen. Jede Spalte hat ihren eigenen Filter in der Zeile unter den Überschriften.

## Ein Teil einem Lieferanten geben

Klicke mit der rechten Maustaste auf eine Zeile. **Vorschlag übernehmen** setzt das Teil auf eine Entwurfsbestellung beim Standardlieferanten des Verfahrens, auf den offenen Entwurf, wenn es einen gibt. **Lieferant wählen…** öffnet den Dialog, in dem du einen anderen Lieferanten oder eine Bestellung wählst. **Aus Bestellung entfernen** nimmt es wieder herunter, solange noch keine Teile weg sind, und **Bereitstellung erfassen…** bucht die Teile, die du übergeben hast. Diese Einträge brauchen **Bestellungen schreiben**, die Bereitstellung **Fertigungslose schreiben**; ohne die Berechtigung sind sie ausgegraut.

## Beispiele

**Eine Charge zum Härten.** Du gruppierst nach **Lieferant**: Die Gruppe der Härterei sagt, ihr nächster Versand ist am Dienstag. Du klickst jedes Teil, das bereit ist, mit der rechten Maustaste an und wählst **Vorschlag übernehmen**, und alle landen auf einer Entwurfsbestellung.

**Ein Teil, das zu spät kommt.** **Bereit ab** sagt Freitag, **Spätestens weg** aber Donnerstag, und der Hinweis sagt, dass es nicht rechtzeitig fertig wird. Du siehst dir den Schritt davor im Los an.
