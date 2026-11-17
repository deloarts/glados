---
title: KI-Agenten
summary: Wie du einen KI-Agenten wie Claude mit Glados verbindest, wozu du vorher einwilligst und wie du verfolgst, was er tut.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/agent/agent_consent.py
  - backend/src/modules/platform/application/use_cases/agent/authenticate_agent.py
  - backend/src/modules/platform/application/use_cases/agent/sweep_agent_tokens.py
  - backend/src/modules/platform/domain/services/agent_policy.py
  - backend/src/modules/platform/domain/entities/admin_settings/agents.py
  - backend/src/modules/fulfillment/adapters/inbound/mcp/draft_tools.py
lastVerified: 2026-11-12
---

Ein KI-Agent wie Claude Code kann dir Fragen zu Glados beantworten und Routinearbeit als Entwurf vorbereiten. Er arbeitet mit einem Agenten-Token, das du im Reiter **KI-Agenten** deines Kontos erstellst, und handelt als du, mit deinen Berechtigungen oder weniger. Der Reiter zeigt auch deine Einwilligung und jeden Aufruf deiner Agenten.

## Bevor du beginnst {#before}

Drei Dinge müssen stimmen. Dein Unternehmen hält die Freigabe der erlaubten KI-Anbieter fest, deine Administration gibt dir die Berechtigung **KI-Agenten nutzen**, und du willigst selbst ein. Ohne die Berechtigung bleiben die Schaltflächen im Reiter gesperrt, und ihr Tooltip nennt, was fehlt. Ein Agenten-Token ist ein [Zugriffstoken](/handbook/account/access-tokens), darum brauchst du zum Erstellen auch **Zugriffstoken erstellen**.

## Einwilligen und widerrufen {#consent}

**Einwilligen** öffnet einen Dialog, der die freigegebenen Anbieter nennt und sagt, ob Namen von Personen und Preise Glados verlassen. Setze das Häkchen und bestätige. Die Karte **Einwilligung** zeigt dann **Erteilt** mit dem Datum.

Ändert deine Administration die freigegebenen Anbieter, die KI-Richtlinie oder was Glados verlässt, zeigt die Karte **Bedingungen geändert**. Dein Agent wird abgewiesen, bis du die neuen Bedingungen gelesen und erneut eingewilligt hast.

**Einwilligung widerrufen** sperrt alle deine Agenten-Token auf einmal. Das geht auch, wenn der Zugriff für Agenten ausgeschaltet ist.

## Ein Agenten-Token erstellen {#token}

**Neues Agenten-Token** fragt zuerst nach deiner Einwilligung, wenn sie fehlt. Wähle den **Zugriff**: **Lesen** lässt den Agenten lesen und Fragen beantworten, **Lesen und Entwürfe** lässt ihn auch Entwürfe von Bestellungen, Angebotsanfragen und Losen vorbereiten. Lege **Läuft ab in (Tagen)** fest; ein Agenten-Token gilt höchstens so lange, wie deine Administration erlaubt, meist 30 Tage. Gib dein **Aktuelles Passwort** ein, wie bei jedem Zugriffstoken.

Glados zeigt das Token einmal an, zusammen mit einem Befehl, den du in ein Terminal einfügst, um Claude Code zu verbinden. Kopiere beides, bevor du den Dialog schließt. **Zugriffstoken** listet das Token auch, und **Widerrufen** stoppt dort nur dieses eine.

## Was der Agent kann und was nicht {#scope}

Der Agent liest, was du lesen darfst. Ein Entwurf, den er vorbereitet, wartet auf dich: Du öffnest ihn, prüfst ihn und bestellst, versendest, planst oder löschst ihn wie gewohnt. Der Agent bestellt, versendet, plant oder löscht nie selbst etwas. In den Listen der Bestellungen, Angebotsanfragen und Lose markiert ein Tag **Agent** einen Entwurf, den ein Agent erstellt hat, und sein Tooltip nennt das Token.

## Agenten-Aufrufe prüfen {#calls}

Die Tabelle **Agenten-Aufrufe** listet jeden Aufruf, den neuesten zuerst, mit Werkzeug, **Ergebnis** und **Details**. Die Spalte **Erstellt** verlinkt die Entwürfe, die ein Aufruf angelegt hat. Standardmäßig darf jedes Token 120 Aufrufe pro Minute und 20 Entwürfe pro Stunde machen, und ein Aufruf darüber steht als **Abgelehnt** da.

## Wenn ein Token nicht mehr funktioniert {#stops}

Ein Token endet, wenn es abläuft, wenn es so viele Tage ungenutzt bleibt, wie deine Administration festgelegt hat, meist 14, oder wenn deine Einwilligung die aktuellen Bedingungen nicht mehr abdeckt. Drei Tage bevor ein Token abläuft, bekommst du eine Benachrichtigung, und eine weitere, nachdem ein ungenutztes Token gesperrt wurde.

## Beispiele {#examples}

1. Du erstellst ein Token mit **Lesen**, verbindest Claude Code und fragst, warum Los L-1042 verspätet ist. Der Agent liest das Los und seine Schritte und antwortet.
2. Mit einem Token mit **Lesen und Entwürfe** bittest du um eine Bestellung für die offenen Bedarfe eines Projekts. Der Entwurf erscheint mit einem Tag **Agent**. Du öffnest ihn über **Erstellt**, prüfst die Mengen und bestellst.
3. Deine Administration lässt Preise aus Glados hinaus. Deine Karte zeigt **Bedingungen geändert**, und dein Agent wird abgewiesen, bis du erneut einwilligst.
4. Du nutzt ein Token nicht mehr. Nach 14 Tagen ohne Aufruf wird es gesperrt, und eine Benachrichtigung sagt dir das.
