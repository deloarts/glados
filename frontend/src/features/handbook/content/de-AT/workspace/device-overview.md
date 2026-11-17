---
title: Geräteübersicht
summary: Wie du die Geräte eines Produkts auf einem Bild der Maschine von oben platzierst und dort wiederfindest.
sourceRefs:
  - frontend/src/features/product-devices/components/ProductDeviceOverview.vue
  - frontend/src/features/product-devices/components/DeviceOverviewCanvas.vue
  - frontend/src/features/product-devices/components/ProductDeviceOverviewList.vue
  - backend/src/modules/workspace/application/use_cases/product_device/images.py
lastVerified: 2026-11-10
---

**Übersicht** in der Ansichtsleiste des Reiters **Geräte** zeigt ein Bild der Maschine von oben, mit einer nummerierten Markierung für jedes Gerät. So findest du ein Gerät an der Maschine, und du siehst, welche Geräte noch niemand platziert hat. Eine Markierung trägt die Nummer des Geräts in der Geräteliste. Wie Geräte benannt und beschrieben werden, steht unter [Geräte eines Produkts](/handbook/workspace/product-devices).

## Das Übersichtsbild

**Übersicht hochladen** lädt ein Bild der Maschine als PNG, JPG, WEBP oder SVG, und **Übersicht ersetzen** tauscht es gegen ein neues. Eine Markierung behält ihren Platz relativ zum Bild, ein neues Rendering mit demselben Ausschnitt behält also jede Markierung, wo sie war. Die Übersicht ändern darf, wer das Produkt bearbeiten darf, also seine zuständige Person und jede Person mit **Projekte verwalten**. Ohne diese Rechte sind die Schaltflächen ausgegraut und zeigen einen Tooltip. Die Übersicht eines archivierten Produkts lässt sich nicht ändern.

## Sich bewegen

Scrolle, um rund um den Mauszeiger zu zoomen, und zieh das Bild, um es zu verschieben. **Vergrößern**, **Verkleinern** und **Ganzes Bild zeigen** tun dasselbe mit Schaltflächen, und auch die Tasten Plus, Minus und Null funktionieren. **Punktraster** schaltet das Raster hinter dem Bild ein und aus.

## Ein Gerät platzieren

Wähle das Gerät unter **Gerät zum Platzieren wählen** oder klick es in der Liste neben dem Bild an, und klick dann im Bild auf die Stelle, an der das Gerät sitzt. Die Markierung wird sofort gespeichert. Wählst du ein Gerät, das schon eine Markierung hat, holt das Bild sie ins Blickfeld, und ein Klick an eine andere Stelle verschiebt sie dorthin. **Markierung entfernen** nimmt die Markierung wieder weg. Ohne Bearbeitungsrechte heißt die Auswahl **Gerät suchen** und holt Markierungen nur ins Blickfeld.

## Die Geräteliste

Das Feld **Geräte** neben dem Bild listet jedes Gerät mit seiner Nummer. Ein durchgestrichenes Markierungssymbol heißt, dass das Gerät noch nicht platziert ist. Der Augen-Knopf blendet eine Markierung für diesen Besuch aus, und **Alle ausblenden** und **Alle einblenden** tun das für alle Markierungen; ein gewähltes Gerät zeigt seine Markierung immer. Zeigst du auf ein Gerät, werden seine Markierung und die Geräte, die sich mit ihm bewegen, hervorgehoben. **Details ausblenden** schaltet die kleinen Karten mit Name, Typ und Rendering an jeder Markierung ab, was bei einem vollen Bild hilft. Zieh den Rand des Felds, um es breiter zu machen.

## Beispiele

**Eine neue Maschine.** Du lädst das aus dem CAD exportierte Layout als SVG hoch, wählst B01 Hubzylinder P1 und klickst auf die Stelle, an der er sitzt. Das wiederholst du für jedes Gerät, bis die Liste kein durchgestrichenes Symbol mehr zeigt.

**Ein geändertes Layout.** Nach einer Konstruktionsänderung klickst du auf **Übersicht ersetzen** und wählst ein neues Rendering derselben Ansicht. Jede Markierung behält ihren Platz, und du verschiebst nur die Geräte, die sich geändert haben.

**Einen Sensor vor Ort finden.** Ein Monteur ohne Bearbeitungsrechte tippt den Gerätenamen in **Gerät suchen**, und das Bild holt die Markierung ins Blickfeld.
