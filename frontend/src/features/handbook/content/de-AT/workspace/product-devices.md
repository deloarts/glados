---
title: Geräte eines Produkts
summary: Wie die Geräte einer Maschine benannt, für die SPS beschrieben und in der Geräteliste eines Produkts gepflegt werden.
sourceRefs:
  - backend/src/modules/workspace/domain/policies/product_device_naming.py
  - backend/src/modules/workspace/domain/policies/product_device_rules.py
  - backend/src/modules/workspace/application/use_cases/product_device/assembler.py
  - backend/src/modules/workspace/application/use_cases/product_device/devices.py
  - backend/src/modules/workspace/application/use_cases/product_device/images.py
lastVerified: 2026-11-10
---

Der Reiter **Geräte** eines Produkts listet seine Geräte: Zylinder, Greifer, Achsen und Taster, jeweils eine Gruppe von Teilen, etwa ein Zylinder mit seinem Ventil und zwei Sensoren. Jeder Plan der Maschine verwendet diese Namen. Die Ansichtsleiste wechselt zur [Geräteübersicht](/handbook/workspace/device-overview), zur [Vollständigkeit der Geräte](/handbook/workspace/device-completeness) und zu den [SPS-Variablen](/handbook/workspace/plc-tags), und die [Gerätelisten](/handbook/resources/product-devices) enthalten, woraus Geräte wählen.

## Wie ein Gerätename entsteht

Ein Name besteht aus **Ort**, **Name**, dem Buchstaben der **Antriebsart** und einer **Nummer**: B01, Hubzylinder, Pneumatik mit dem Buchstaben P und die Nummer 1 ergeben B01 Hubzylinder P1. Lässt du **Nummer** auf **Nächste freie**, nimmt Glados die nächste für diesen Ort, Namen und Buchstaben. Die Vorschau zeigt den Namen schon beim Tippen, mit seiner ASCII-Form, in der Umlaute ausgeschrieben und andere Sonderzeichen zu Unterstrichen werden. Die Maschinennummer gehört nicht zum Namen; **Namen mit Maschinennummer zeigen** ergänzt sie in der Liste.

Ein Gerät eines Typs ohne Antriebsart, etwa ein Taster, hat keinen Buchstaben, und das erste auch keine Nummer: B00 Taster Start, dann B00 Taster Start 2.

## Was der Dialog enthält

Der **Typ** legt fest, in welchen Stellungen ein Gerät sein kann. **Grundstellung** ist, wo es startet, **Bei Energieausfall** und **Bei Energiewiederkehr** sagen, was es tut, wenn der Strom weg ist und wiederkommt, und **Überwachungszeit** ist, wie lange die SPS wartet, bevor sie einen Fehler meldet. **Eigene Stellungsnamen**, **Verfahrzeiten** und **Technische Parameter** sind optional; die Verfahrzeiten fließen in die geschätzte Taktzeit der Abläufe ein. **Bilder** enthält ein Bild unter **Rendering** für das Gerät und eines unter **Übergeordnete Baugruppe** für die Baugruppe, in der es sitzt. Unter **Komponenten** trägst du die Teile mit **Rolle**, **EPLAN-BMK**, **Katalogartikel** und Signalen ein. Ein Eingangssignal sagt, welche Stellung es bestätigt, ein Ausgang, in welche Stellung er fährt, und beide können eine **Adresse** haben. **Berechnungen** listet die Berechnungen, die auf das Gerät verweisen.

## Geräte, die sich gemeinsam bewegen

Hängt ein zweiter Klemmzylinder am Ventil des ersten, wählst du den ersten unter **Angetrieben von**. Das angetriebene Gerät behält nur seine Sensoren, und ein Ablauf bewegt stattdessen den Antreiber. Ein Antreiber eines anderen Typs braucht **Stellungen**, die sagen, wohin das angetriebene Gerät bei jeder Stellung des Antreibers fährt.

## Ein Gerät umbenennen

Änderst du Ort, Name, Antriebsart oder Nummer, wird das Gerät umbenannt. Glados fragt vorher und nennt die Pläne, die nachgezogen werden müssen, ausgewählt nach dem, was unter **Gewerke** des Produkts angehakt ist: den EPLAN-Plan, den SPS-Code, den Pneumatik- oder Hydraulikplan, das Roboterprogramm und den Namen der CAD-Baugruppe. Die Häkchen des Geräts unter **Vollständigkeit** werden entfernt.

## Die Geräteliste

Ein Klick auf eine Zeile öffnet das Gerät, und ein Rechtsklick bietet außerdem **Name kopieren**, **ASCII-Namen kopieren** und **Archivieren** oder **Wiederherstellen** an. **Archivierte anzeigen** listet archivierte Geräte wieder auf. Ein Symbol markiert ein Gerät, das noch kein Ablauf verwendet. Geräte ändern darf, wer das Produkt bearbeiten darf, also seine zuständige Person und jede Person mit **Projekte verwalten**. Ohne diese Rechte ist **Neues Gerät** ausgegraut und zeigt einen Tooltip, und der Dialog öffnet sich schreibgeschützt.

## Beispiele

**Zwei Klemmen an einem Ventil.** B01 Klemmzylinder P2 wird von B01 Klemmzylinder P1 angetrieben. Er bekommt kein eigenes Ventil, und ein Ablauf, der die Klemmen schließt, bewegt P1.

**Eine späte Umbenennung.** Aus Hubzylinder wird Hebezylinder. Glados nennt EPLAN, den SPS-Code, den Pneumatikplan und die CAD-Baugruppe, und das Gerät braucht seine Häkchen wieder.
