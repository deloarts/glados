---
title: So plant Auto-Planen Aufträge ein
summary: Welche Aufträge Auto-Planen bewegen darf, in welcher Reihenfolge es sie betrachtet und auf welcher Maschine oder in welchem Pool jeder landet.
sourceRefs:
  - backend/src/modules/fulfillment/application/use_cases/production_schedule/auto_plan.py
  - backend/src/modules/fulfillment/domain/services/scheduling/candidate_ordering.py
  - backend/src/modules/fulfillment/domain/services/scheduling/machine_selection.py
lastVerified: 2026-11-26
---

[Auto-Planen](/handbook/production/auto-plan) arbeitet die wartenden Aufträge einen nach dem anderen ab. Jeder eingeplante Auftrag bekommt die früheste freie Zeit, die er kriegen kann, also entscheidet die Reihenfolge, wer die frühen Plätze bekommt. Alles, was der Lauf nicht bewegen darf, bleibt, wo es ist, und wird zum fixen Punkt, um den herum der Rest geplant wird. Die Termine selbst ergeben sich aus den Regeln unter [Wann ein Auftrag starten kann](/handbook/production/auto-plan-timing).

## Welche Aufträge bewegt werden dürfen {#scope}

Nur wartende Aufträge werden bewegt. Laufende, pausierte, abgeschlossene oder stornierte Aufträge nie. Ein angehefteter Auftrag bleibt, wo er ist, außer **Überschreiben von manuell geplanten Terminen erlauben** ist an, und ein angehefteter Auftrag, den der Lauf tatsächlich verschiebt, verliert seine Anpinnung. Ist **Heute geplante Aufträge ausschließen** an, bleibt auch ein Auftrag, dessen Zeitfenster den heutigen Tag berührt, an seinem Platz, selbst wenn er noch nicht begonnen hat.

Aufträge auf Maschinen, die du unter **Einzubeziehende Maschinen** nicht angehakt hast, behalten ihre Planung. Ein Auftrag ohne Maschine bleibt unangetastet, wenn ihn nur nicht angehakte Maschinen übernehmen könnten, damit ein Lauf für ein Team keinem anderen Team die Arbeit wegnimmt. Auto-Planen verschiebt auch Aufträge, die innerhalb des **Fixierter Zeitraum (Stunden)** aus den Produktionseinstellungen starten, die eine normale Neuberechnung an ihrem Platz lassen würde. Manuelle Schritte sind nicht Teil des Laufs, weil sie keine Maschine brauchen.

Die Aufträge, die bleiben, behalten ihre Plätze in der Warteschlange, und die verschobenen Aufträge werden dahinter angehängt, nie dazwischen eingeschoben.

## In welcher Reihenfolge {#ordering}

Das Zieldatum eines Loses gehört zu seinem letzten Schritt. Jeder frühere Schritt ist fällig, wenn der nächste beginnen muss, zurückgerechnet mit einer groben Durchlaufzeit. Ein interner Schritt zählt seine geschätzten Minuten in ganzen Arbeitstagen zu acht Stunden, mindestens einen. Ein externer Schritt zählt die Durchlaufzeit des Lieferanten, sonst die seiner Fertigungsverfahren, sonst die **Standard-Vorlaufzeit extern (Tage)**. Müssen die Teile nach einem Schritt warten, etwa zum Aushärten oder auf ein Laborergebnis, ist der Schritt so viele ganze Tage früher fällig, damit seine Wartezeit trotzdem rechtzeitig endet. Ein Los ohne Zieldatum gibt seinen Schritten kein Fälligkeitsdatum, und diese landen überall dort hinten, wo der Algorithmus nach Fälligkeit sortiert.

Danach sortiert der Algorithmus die Aufträge, und bei Gleichstand entscheidet die Erstellungsreihenfolge. Egal welcher Algorithmus, die Schritte eines Loses behalten ihre Reihenfolge, ein späterer Schritt wird also nie vor seinen eigenen vorherigen Schritt gelegt.

## Welche Maschine {#eligibility}

Eine Maschine kommt nur in Frage, wenn sie jedes Fertigungsverfahren abdeckt, das der Auftrag braucht. Ist **Maschinenzuweisung erlauben** aus, bleibt der Auftrag auf seiner Maschine und nur sein Platz in der Warteschlange ändert sich. Ist es an, kommt jede angehakte Maschine in Frage, die den Auftrag abdeckt. Die meisten Algorithmen wählen die Maschine, die den Auftrag am schnellsten fertigstellt. **Ausgeglichene Auslastung** wählt die Maschine mit den bisher wenigsten verplanten Minuten. Jede Wahl sieht alles, was davor eingeplant wurde, der Lauf trifft also für jeden Auftrag der Reihe nach die beste Wahl, statt den insgesamt besten Plan zu suchen.

## Beispiele {#examples}

Ein Los ist am Freitag fällig und hat zwei interne Schritte zu je sechs Stunden. Der letzte Schritt ist am Freitag fällig, der erste also am Donnerstag, und mit **Dringend zuerst** wird dieser erste Schritt vor einem gleich dringenden Auftrag betrachtet, der nächste Woche fällig ist.

Eine Maschine hat einen angehefteten Auftrag mitten in ihrer Warteschlange und zwei wartende Aufträge dahinter. Ist **Überschreiben von manuell geplanten Terminen erlauben** aus, bleibt der angeheftete Auftrag, wo er ist, und beide wartenden Aufträge kommen dahinter, in der Reihenfolge, die der Algorithmus ihnen gibt.
