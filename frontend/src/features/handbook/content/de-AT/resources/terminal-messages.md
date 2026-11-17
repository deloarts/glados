---
title: Nachrichten an Terminals
summary: Wie du eine kurze Nachricht auf vielen Wandbildschirmen gleichzeitig zeigst, wer sie sieht und wie lange sie bleibt.
sourceRefs:
  - backend/src/modules/operations/domain/services/terminal_broadcast_rules.py
  - backend/src/modules/operations/domain/value_objects/terminal_broadcast.py
  - backend/src/modules/operations/application/use_cases/terminal/terminal_broadcasts.py
lastVerified: 2026-11-10
---

Eine Nachricht an Terminals bringt einen kurzen Text auf viele Wandbildschirme gleichzeitig, etwa eine Brandschutzübung oder einen Besuch, ohne einen Infoscreen zu ändern. Du sendest sie unter Ressourcen, **Terminals** mit **Nachricht an Terminals**, und die Zahl am Knopf zeigt, wie viele Nachrichten gerade laufen. Die laufenden Nachrichten darf jede und jeder ansehen. Zum Senden und Beenden brauchst du **Terminals verwalten**, ohne die Berechtigung sind die Schaltflächen deaktiviert und zeigen einen Hinweis.

## Die Nachricht schreiben

Gib den **Text** ein, bis zu 2000 Zeichen. Er kann Markdown verwenden: zwei Sterne um ein Wort machen es fett, ein Stern kursiv, eine Raute am Zeilenanfang macht eine Überschrift, und ein Strich beginnt eine Liste. Ein Link zeigt nur seinen Text, und Bilder werden weggelassen, denn einen Wandbildschirm klickt niemand an. Wähl die **Dringlichkeit**, Information, Warnung oder Alarm, sie bestimmt die Farbe. Die **Darstellung** ist **Banner**, ein Streifen über dem Bildschirm, während die Seiten weiterlaufen, oder **Vollbild**, das den ganzen Bildschirm abdeckt.

## Wie lange sie bleibt

**Anzeigen bis** musst du ausfüllen, höchstens 30 Tage voraus. **15 Min.**, **1 Stunde** und **Tagesende** tragen eine Zeit ein, und die Datumsauswahl nimmt jede andere. Jeder Bildschirm blendet die Nachricht zu dieser Zeit von selbst aus. **Jetzt beenden** in der Liste der laufenden Nachrichten beendet eine früher.

## Wer sie sieht

Die **Empfänger** sind **Alle Terminals**, außer du wählst aus. **Terminals wählen** erreicht die Bildschirme, die du auswählst, **Infoscreens wählen** erreicht jeden Bildschirm, der einen der gewählten Infoscreens zeigt, und **Beides wählen** erreicht beide. Du kannst bis zu 500 Terminals und 500 Infoscreens auswählen. Eine Auswahl von Infoscreens folgt den Bildschirmen: Ein Bildschirm, der auf einen gewählten Infoscreen wechselt, zeigt die Nachricht ab dann, und einer, der wegwechselt, nicht mehr. Es zählen nur freigegebene Bildschirme, mit oder ohne Infoscreen. Der Dialog sagt, wie viele Bildschirme deine Auswahl gerade erreicht.

Mehrere Nachrichten können gleichzeitig für verschiedene Empfänger laufen. Ein Bildschirm zeigt die neueste, die ihn erreicht. Ein Bildschirm, den seine Anzeigezeiten ausgeschaltet haben, bleibt aus, und die Vorschau eines gewählten Infoscreens zeigt die Nachricht auch. Die Liste zeigt, wer eine Nachricht gesendet hat, ein Bildschirm zeigt aber nie einen Namen.

## Beispiele

**Eine Brandschutzübung.** Du tippst Brandschutzübung um **10:00**, wählst Warnung und Vollbild, nimmst **1 Stunde** und lässt **Alle Terminals**. Jeder Bildschirm zeigt sie in wenigen Sekunden.

**Nur Halle 2.** Du wählst **Infoscreens wählen** und Hallentafel 2, dazu Banner und **Tagesende**. Der Dialog sagt, dass die Nachricht drei Bildschirme erreicht.

**Zu früh gesendet.** Du klickst neben der Nachricht auf **Jetzt beenden**, und die Bildschirme blenden sie sofort aus.
