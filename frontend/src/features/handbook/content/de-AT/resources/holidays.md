---
title: Feiertage
summary: Wie Feiertage und Betriebsurlaube die Maschinen schließen, wie eine Maschine an so einem Tag trotzdem arbeiten kann und wer die Liste noch verwendet.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/tenant_holiday/tenant_holidays.py
  - backend/src/modules/platform/domain/services/tenant_holiday_rules.py
lastVerified: 2026-11-10
---

Die Liste **Feiertage** enthält die Tage, an denen der ganze Betrieb nicht arbeitet, etwa gesetzliche Feiertage und den Betriebsurlaub im Sommer oder zu Weihnachten. Die Planung plant an diesen Tagen keine Arbeit ein, daher rutschen Liefertermine von selbst darüber hinaus.

## Einen Feiertag hinzufügen

**Feiertag hinzufügen** öffnet das Formular. **Name** ist Pflicht und darf bis zu 200 Zeichen lang sein. **Art** ist entweder Feiertag oder Betriebsurlaub. **Von** ist Pflicht. **Bis** ist optional und zeigt leer Gleicher Tag, für einen einzelnen Tag reicht also **Von**. Beide Tage zählen mit, **Bis** darf nicht vor **Von** liegen, und ein Eintrag umfasst höchstens 366 Tage.

Ein Feiertag wiederholt sich nicht. Jeder Eintrag ist ein Zeitraum, also leg die Feiertage des nächsten Jahres als neue Einträge an. **Neu laden** holt die Liste neu, etwa nachdem eine Kollegin sie geändert hat.

## Was ein Feiertag schließt

Beide Arten wirken gleich. Sie schließen jede Maschine und den Standardkalender, in dem Handarbeit geplant wird. Die Art sagt nur, warum der Betrieb zu hat. Nach jeder Änderung an der Liste wird der Zeitplan sofort neu berechnet.

Eine Maschine kann an einem Feiertag trotzdem arbeiten. Leg unter **Kalender verwalten** bei der Maschine eine Kalenderausnahme für dieses Datum an, dann gilt für diese eine Maschine die Ausnahme statt des Feiertags.

Ein Infoscreen kann die Bildschirme, die ihn zeigen, an Feiertagen ausschalten und den nächsten Feiertag anzeigen, beides aus dieser Liste.

## Die Liste verwalten

Die Tabelle zeigt **#**, **Name**, **Art**, **Von**, **Bis** und **Tage**, die Zahl der Kalendertage, die der Eintrag umfasst. Zum Hinzufügen, Bearbeiten und Löschen von Feiertagen brauchst du die Berechtigung **Fertigungsmaschinen schreiben**. Ohne sie sind die Schaltflächen deaktiviert und zeigen einen Hinweis. Feiertage werden nach einer Rückfrage gelöscht, nicht archiviert, ein gelöschter Feiertag ist also weg, und seine Tage folgen wieder den normalen Arbeitszeiten.

## Beispiele

**Ein Feiertag.** Leg Staatsfeiertag als Feiertag mit **Von** 1. Mai an und lass **Bis** leer. **Tage** zeigt 1, und an diesem Tag wird keine Arbeit eingeplant.

**Betriebsurlaub zu Weihnachten.** Leg Weihnachtsurlaub als Betriebsurlaub von 24. Dezember bis 6. Jänner an. **Tage** zeigt 14, und die Planung schiebt die Arbeit aus diesem Zeitraum auf die Arbeitstage danach.

**Wartung im Betriebsurlaub.** Die Instandhaltung braucht die Fräsmaschine am 28. Dezember. Leg bei der Fräsmaschine für dieses Datum eine Kalenderausnahme mit Beginn und den Minuten an, die sie arbeitet. Nur diese Maschine ist an dem Tag offen.
