---
title: Angebotsanfragen
summary: Wie du mehrere Lieferanten nach Preisen fragst, ihre Angebote vergleichst, die Positionen auf Bestellungen vergibst und was Abschließen, Stornieren, Ersatz und aufgehobene Vergaben bewirken.
sourceRefs:
  - backend/src/modules/fulfillment/domain/services/lifecycle/quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/edit_quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/award_quote_request.py
  - backend/src/modules/fulfillment/application/use_cases/quote_request/_lines.py
lastVerified: 2026-11-10
---

<script setup lang="ts">
import StateMachineEmbed from '@/features/handbook/state-machines/components/StateMachineEmbed.vue'
</script>

Eine Angebotsanfrage fragt mehrere Lieferanten nach Preisen für dieselben Positionen, damit du beim günstigsten bestellst. Der Reiter **Angebote** unter **Beschaffung** listet die offenen Anfragen, und **Abgeschlossene anzeigen** nimmt die beendeten dazu. Die meisten Anfragen beginnen mit **Angebote verwalten** in einer Bedarfsliste, und **Neue Angebotsanfrage** legt eine mit **Anzufragende Lieferanten**, einem Termin bei **Angebote bis** und einer **Notiz** an. Nichts auf einer Anfrage ändert eine Bestellung oder einen Bedarf, bis du vergibst. Jede Änderung braucht **Bestellungen schreiben**, und eine deaktivierte Schaltfläche nennt in ihrem Tooltip die fehlende Berechtigung oder den Grund.

<StateMachineEmbed machine-key="quote_request_status" />

Jede Statusänderung mit ihrem Auslöser steht in [Statusübergänge einer Angebotsanfrage](/handbook/procurement/quote-request-transitions).

## Die Lieferanten anfragen {#send}

**Lieferanten hinzufügen** nimmt weitere Lieferanten auf. Für jeden Lieferanten stellt **Anfrage senden** die Anfrage-Mail zusammen, wofür du auch **E-Mails versenden** brauchst, und **Als versendet markieren** hält eine Anfrage fest, die du auf anderem Weg geschickt hast. Sobald ein Lieferant angefragt ist, steht die Anfrage auf **Versendet**. Eine danach hinzugefügte Position zeigt bei den Lieferanten, die die Anfrage schon haben, **Noch nicht angefragt**.

## Angebote erfassen {#offers}

**Angebot erfassen** hält fest, was ein Lieferant angeboten hat: **Stückpreis**, **Lieferzeit in Tagen** und **Mindestmenge** je Position, oder **Kein Angebot** für eine Position, die er auslässt. **Alternative anbieten** hält einen anderen Artikel fest, den der Lieferant stattdessen anbietet. **Zusatzkosten**, **Dokumente**, **Gültig bis** und **Notiz** gelten für das ganze Angebot, und **Der Lieferant hat kein Angebot abgegeben** markiert eine Absage. Die Tabelle markiert den besten Preis je Position und das Angebot **Insgesamt am günstigsten**.

## Vergeben {#award}

Klick auf eine Angebotszelle, um diesen Lieferanten für die Position zu wählen, oder nutze **Günstigste wählen**. **Auswahl vergeben** vergibt die gewählten Positionen, und **Alles vergeben an** gibt jede offene Position einem Lieferanten. Der Dialog **Positionen vergeben** nennt je gewinnendem Lieferanten eine **Bestellung**, entweder eine **Neue Entwurfsbestellung** oder eine seiner Bestellungen im Entwurf oder teilweise bestellt, und die **Zusatzkosten auf der Bestellung**, die aus dem Angebot übernommen werden. Jede Position kommt mit den Bedarfen, für die sie angefragt wurde, auf diese Bestellung, gekürzt auf das, was jeder Bedarf noch braucht.

## Abschließen, stornieren und verwerfen {#close}

**Verwerfen** nimmt eine Position aus der Vergabe, und **Zurückholen** holt sie zurück. **Entfernen** löscht eine Position mit ihren Angeboten. **Abschließen** beendet eine Anfrage mit einer vergebenen Position und verwirft die noch offenen Positionen, während **Anfrage stornieren** eine Anfrage beendet, die nichts vergeben hat, und ihre Bedarfe bleiben offen.

**Ersetzen** ersetzt eine Position für ein Zukaufteil oder einen Rohblock für jeden Lieferanten durch einen anderen Artikel derselben Art. Die alte Position wird verworfen, und die neue übernimmt Menge und Bedarfe. Schick die Anfrage an die bereits angefragten Lieferanten noch einmal. Entfernst du die neue Position, kommt die alte zurück.

## Aufgehobene Vergaben und Wieder öffnen {#reopen}

Stornierst oder entfernst du eine Bestellposition aus einer Vergabe, gibt sie die Vergabe zurück. Die Position der Anfrage ist wieder offen, zeigt **Aufgehoben** und lässt sich neu vergeben. Eine Anfrage, die jemand abgeschlossen hat, bleibt abgeschlossen und hält die aufgehobene Vergabe nur fest, deshalb hebt **Wieder öffnen** den Abschluss auf. Die Angebote bleiben, und die Anfrage steht wieder auf versendet oder Entwurf.

## Beispiele

**Drei Lieferanten angefragt.** Du schickst die Anfrage an drei Lieferanten und erfasst ihre Angebote. **Günstigste wählen** wählt je Position einen Lieferanten, und **Auswahl vergeben** legt die Positionen auf zwei neue Entwurfsbestellungen.

**Ein alternativer Artikel.** Ein Lieferant bietet stattdessen ein ähnliches Lager an. Du hältst es mit **Alternative anbieten** fest, und gewinnt es, trägt die Bestellposition den alternativen Artikel.

**Eine aufgehobene Vergabe.** Nach dem Abschließen kann der Lieferant nicht liefern, und du stornierst die Bestellposition. Öffne die Anfrage mit **Wieder öffnen** wieder und vergib die Position an den zweitgünstigsten Lieferanten.
