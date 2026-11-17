---
title: Vollständigkeit der Geräte
summary: Wie die Ansicht Vollständigkeit verfolgt, welche Pläne der Maschine jedes Gerät schon zeigen und welche Geräte noch kein Ablauf verwendet.
sourceRefs:
  - backend/src/modules/workspace/application/use_cases/product_device/completeness.py
  - backend/src/modules/workspace/domain/value_objects/device_plan.py
  - frontend/src/features/product-devices/components/ProductDeviceCompletenessTable.vue
lastVerified: 2026-11-10
---

**Vollständigkeit** in der Ansichtsleiste des Reiters **Geräte** zeigt eine Zeile je Gerät und ein Häkchen je Plan, den die Maschine braucht. Sie beantwortet, ob jeder Plan schon die aktuellen Gerätenamen trägt, bevor die Maschine gebaut und in Betrieb genommen wird. Wie Geräte benannt und umbenannt werden, steht unter [Geräte eines Produkts](/handbook/workspace/product-devices).

## Welche Pläne zählen

Die Spalte **CAD-Baugruppe** gibt es immer. **EPLAN**, **Pneumatikplan**, **Hydraulikplan** und **Roboterprogramm** folgen dem, was im Formular des Produkts unter **Gewerke** angehakt ist: Elektrik, Pneumatik, Hydraulik und Robotik. Änderst du die Gewerke, ändern sich die Spalten mit, eine Maschine ohne Hydraulik verlangt also nie einen Hydraulikplan.

## Einen Plan abhaken

Hake einen Plan ab, sobald das Gerät unter seinem aktuellen Namen darin gezeichnet ist. Fährst du über ein Häkchen, siehst du, wer es wann gesetzt hat. Ein Gerät mit allen Häkchen zeigt neben seinem Namen ein grünes Häkchen, und **Nur unvollständige** blendet diese Geräte aus, sodass die Liste zeigt, was noch offen ist. Eine Umbenennung nimmt dem Gerät alle Häkchen, weil jeder Plan den neuen Namen erst wieder zeigen muss. Abhaken darf, wer das Produkt bearbeiten darf, also seine zuständige Person und jede Person mit **Projekte verwalten**. Ohne diese Rechte sind die Kästchen ausgegraut, und der Tooltip sagt das.

## Die Spalte Ablauf

**Ablauf** sagt, ob eine freigegebene Revision eines Ablaufs das Gerät bewegt oder prüft (**Freigegeben**), nur ein Entwurf (**Nur in Entwürfen**) oder keiner (**In keinem**). Eine als ungültig markierte Revision zählt nicht. Ein angetriebenes Gerät zählt über seinen Antreiber, weil ein Ablauf den Antreiber bewegt. Die Spalte erscheint nur, solange Abläufe eingeschaltet sind.

## Beispiele

**Vor der Elektrikprüfung.** Die Maschine hat Pneumatik und Elektrik. Der Konstrukteur hakt **EPLAN** bei jedem Gerät ab, das der Elektroplan zeigt, und schaltet dann **Nur unvollständige** ein, um zu sehen, welche Geräte noch in einem Plan fehlen.

**Eine Umbenennung nach dem Zeichnen.** Aus B01 Hubzylinder P1 wird B01 Hebezylinder P1. Seine Häkchen verschwinden, das Gerät erscheint wieder unter **Nur unvollständige**, und jeder Plan wird neu abgehakt, sobald er den neuen Namen zeigt.

**Ein Gerät ohne Ablauf.** Ein neuer Teilesensor zeigt **In keinem**. Entweder fehlt er im Automatikzyklus, oder er wird nicht gebraucht, und wer die Abläufe baut, prüft das.
