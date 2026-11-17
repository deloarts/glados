---
title: Zugriffstoken
summary: Wie ein persönlicher Zugriffstoken ein Skript oder das SolidWorks-Add-in mit den von dir gewählten Berechtigungen in deinem Namen arbeiten lässt und wie du ihn widerrufst.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/pat/create_pat.py
  - backend/src/modules/platform/application/use_cases/pat/revoke_pat.py
  - backend/src/modules/platform/domain/services/pat_rules.py
  - backend/src/modules/platform/domain/services/token_permission_rules.py
  - backend/src/modules/platform/domain/services/token_lifetime.py
  - backend/src/modules/platform/application/services/token_lifetime_cap.py
  - frontend/src/shared/components/tokens/TokenFormDialog.vue
  - frontend/src/shared/components/tokens/TokenManagementControls.vue
lastVerified: 2026-11-13
---

Ein persönlicher Zugriffstoken lässt ein Programm in deinem Namen in Glados arbeiten, ohne dein Passwort. Das SolidWorks-Add-in oder ein Skript verwendet ihn statt einer Anmeldung. Alles, was ein Token tut, wird unter deinem Namen festgehalten, und er hört auf zu wirken, sobald dein Konto deaktiviert wird. Deine Token findest du unter Konto, **Zugriffstoken**.

## Was ein Token ist {#what}

Ein Token ist ein langer geheimer Text. Glados zeigt ihn ein einziges Mal, gleich nach dem Erstellen, also kopier ihn in das Programm, das ihn braucht, bevor du den Dialog schließt. Später kann ihn niemand mehr anzeigen, auch keine Administration; geht er verloren, widerrufst du ihn und erstellst einen neuen. Die Tabelle zeigt unter **Präfix** nur die ersten Zeichen, genug, um deine Token auseinanderzuhalten.

## Einen Token erstellen {#create}

Klick auf **Token erstellen** und gib ihm einen **Name**, der sagt, was ihn verwendet, etwa Wöchentlicher Bestellexport. Unter **Berechtigungen** hakst du an, was der Token darf. **Läuft ab in (Tage)** beginnt bei 30 und reicht bis zur **Maximale Token-Gültigkeit (Tage)**, die eine Administration im Tab Sicherheit festgelegt hat. **Läuft nie ab** gibt es nur, solange der Tab Sicherheit kein Maximum festlegt. Zuletzt gibst du dein **Aktuelles Passwort** ein: Ein Token funktioniert auch nach dem Abmelden weiter, daher darf eine offene Sitzung auf einem fremden Bildschirm nicht reichen, um einen zu erstellen. Ein falsches Passwort zählt wie eine fehlgeschlagene Anmeldung. Zum Erstellen brauchst du **Zugriffstoken erstellen**; ohne die Berechtigung sind **Token erstellen** und die Add-in-Schaltflächen deaktiviert, und ein Tooltip nennt die Berechtigung.

## Die Add-in-Token {#addin}

Solange SolidWorks PDM eingeschaltet ist, füllen zwei Schaltflächen das Formular für ein Add-in aus. **SolidWorks-Add-in-Token erstellen** ist für das SolidWorks-Add-in. Der Name wird SW Addin mit dem heutigen Datum, die Berechtigungen des Add-ins **Rohblock schreiben** und **EPLAN Data Portal verwenden** sind angehakt, und der Ablauf ist das Ende dieses Jahres, oder früher, wenn der Tab Sicherheit weniger erlaubt. Die erste braucht das Add-in zum Anlegen von Rohblöcken, die zweite für seine Suche im Data Portal. Hat dein eigenes Konto eine davon nicht, sagt der Dialog das, und der Token wird ohne sie erstellt; frag zuerst eine Administration nach der Berechtigung.

**PDM-Add-in-Token erstellen** ist für das PDM-Tresor-Add-in, das Glados meldet, wenn sich eine Datei im Tresor ändert. Der Name wird PDM Addin mit dem heutigen Datum, seine einzige Berechtigung **PDM-Add-in verwenden** ist angehakt, und der Ablauf ist derselbe. Den Token fügst du im Tab Glados einer Tresoransicht im Datei-Explorer ein. Der Token kann nichts außer Glados bitten, eine Datei neu anzusehen, und zeigen, was Glados mit den ausgewählten Dateien gemacht hat. Hat dein Konto **PDM-Add-in verwenden** nicht, sagt der Dialog das; frag eine Administration danach.

## Was ein Token darf {#scope}

Ein Token darf nur, was du angehakt hast, und anhaken kannst du nur Berechtigungen, die du selbst hast. Die Berechtigungen eines Tokens stehen beim Erstellen fest. Um sie zu ändern, erstellst du einen neuen Token und widerrufst den alten. Verlierst du später eine Berechtigung, verlieren deine Token sie auch. Manche Berechtigungen kommen nie auf einen Token, auch wenn du sie hast: **Einstellungen lesen**, **Einstellungen schreiben**, **API-Schlüssel verwalten** und **Terminals verbinden**. Ein Token mit **KI-Agenten nutzen** gilt nur so lange, wie es für Agenten-Token festgelegt ist. Token, die du im Tab **KI-Agenten** erstellst, stehen auch hier. Das Systemkonto kann keine Token erstellen.

## Widerrufen {#revoke}

**Widerrufen** in einer Zeile stoppt diesen Token sofort und endgültig. **Alle widerrufen** stoppt alle deine Token. Änderst du dein Passwort, werden ebenfalls alle deine Token widerrufen, genauso wenn eine Administration es ändert oder dein Konto überall abmeldet, und die Programme, die sie verwendet haben, brauchen neue. Für deine eigenen Token brauchst du keine Berechtigung, **Widerrufen** und **Alle widerrufen** gehen also auch ohne **Zugriffstoken erstellen**. Außer dir können nur Personen mit **Einstellungen schreiben** deine Token widerrufen.

## Das Nutzungsprotokoll {#usage}

**Nutzungsprotokoll anzeigen** in einer Zeile listet jeden Aufruf des Tokens mit der Zeit, was aufgerufen wurde und ob es geklappt hat. So siehst du, ob ein Token noch verwendet wird. Ein Aufruf, den du nicht kennst, oder einer in der Nacht, wenn niemand arbeitet, ist ein Grund, den Token zu widerrufen.

## Beispiele

**Ein Skript für den Bestellexport.** Du erstellst Wöchentlicher Bestellexport mit nur der Berechtigung, die er braucht, und 90 unter **Läuft ab in (Tage)**. Du fügst den Token in das Skript ein und schließt den Dialog.

**Das Add-in auf einem neuen PC.** Du klickst auf **SolidWorks-Add-in-Token erstellen**, behältst die Werte und fügst den Token in die Einstellungen des Add-ins ein. Er läuft bis zum Jahresende.

**Ein verlorener Laptop.** Du klickst auf **Alle widerrufen**. Jedes Programm, das deine Token verwendet hat, stoppt sofort, und du erstellst neue Token für die, die du noch brauchst.
