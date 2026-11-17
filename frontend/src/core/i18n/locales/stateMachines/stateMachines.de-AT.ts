// Messages for stateMachines, merged into the de-AT locale.
export default {
  liveHint: 'Diese Seite wird live aus den Regeln des Systems gelesen und zeigt daher immer, was das System gerade durchsetzt.',
  asOf: 'Stand {time}, live vom Backend abgerufen',
  refresh: 'Aktualisieren',
  missing: 'Dieser Lebenszyklus ist (noch) nicht in der Antwort des Backends enthalten.',
  legend: {
    initial: 'Anfangszustand',
    terminal: 'Endzustand',
    backEdge: 'Rückwärtskante',
  },
  errors: {
    loadFailed: 'Die Zustandsautomaten konnten nicht geladen werden.',
  },
  kind: {
    derived: 'Ergibt sich aus dem, was passiert ist',
    intent: 'Wird durch Aktionen gesetzt',
  },
  rules: {
    title: 'So ergibt sich der Status',
    intro: 'Die Zeilen werden von oben geprüft. Die erste passende Zeile bestimmt den Status.',
    columns: {
      number: '#',
      condition: 'Wenn',
      result: 'Status',
    },
  },
  intents: {
    title: 'Was du tun kannst',
    anyStatus: 'Jeder Status',
    setStatus: 'Auf {status} setzen',
    columns: {
      action: 'Aktion',
      allowedFrom: 'Erlaubt bei',
      condition: 'Braucht außerdem',
      permission: 'Berechtigung',
      effect: 'Was passiert',
    },
  },
  transitions: {
    title: 'Statusänderungen',
    intro: 'Jede Statusänderung, die das System in diesem Lebenszyklus macht, gefunden durch das Zusammenspiel seiner echten Aktionen. Eine Zeile, die einen anderen Datensatz nennt, wurde durch eine Aktion an diesem Datensatz geändert.',
    computedHint: 'Diese Tabelle wird aus dem System selbst ermittelt: Ein Test schlägt fehl, sobald das System eine Änderung macht, die hier fehlt, oder die Tabelle eine nennt, die das System nicht machen kann.',
    created: 'Neu',
    via: 'Aktion an: {machine}',
    change: '{machine}: {from} → {to}',
    columns: {
      from: 'Von',
      to: 'Nach',
      trigger: 'Auslöser',
      condition: 'Bedingung',
      permission: 'Berechtigung',
      implications: 'Ändert außerdem',
    },
  },
  cascades: {
    title: 'Was eine Aktion anderswo ändert',
    intro: 'Für jede Aktion die Statusänderungen, die sie an anderen Datensätzen machen kann. Eine einzelne Aktion ändert nur die, die auf die betroffenen Datensätze zutreffen.',
    columns: {
      record: 'Aktion an',
      trigger: 'Aktion',
      changes: 'Statusänderungen',
    },
  },
  machines: {
    lot_status: 'Los',
    lot_position_status: 'Losposition',
    lot_position_kind: 'Art der Losposition',
    production_order_status: 'Fertigungsauftrag',
    order_status: 'Bestellung',
    order_item_status: 'Bestellposition',
    bought_item_demand_status: 'Zukaufteile-Bedarf',
    made_item_demand_status: 'Fertigungsteile-Bedarf',
    source_item_demand_status: 'Rohblock-Bedarf',
    quote_request_status: 'Angebotsanfrage',
  },
  triggers: {
    allocate: 'Bestellposition zuteilen',
    allocate_source: 'Rohblock-Bestellposition zuteilen',
    assign_external: 'Extern bestellen',
    assign_internal: 'Intern einplanen',
    award: 'Anfrage vergeben',
    cancel_bought_demand_request: 'Bedarf stornieren',
    cancel_line: 'Position stornieren',
    cancel_lot_request: 'Los stornieren',
    cancel_made_demand_request: 'Bedarf stornieren',
    cancel_order: 'Bestellung stornieren',
    cancel_production_order: 'Fertigungsauftrag stornieren',
    cancel_source_demand_request: 'Bedarf stornieren',
    close_short: 'Restmenge ausbuchen',
    complete: 'Fertigmeldung buchen',
    correct: 'Lieferung korrigieren',
    create_lot_for_demand: 'Los für den Bedarf anlegen',
    deliver: 'Wareneingang buchen',
    deliver_all: 'Alle Positionen liefern',
    force_complete: 'Los zwangsweise abschließen',
    fulfil_bought_demand: 'Bedarf als erfüllt markieren',
    fulfil_made_demand: 'Bedarf als erfüllt markieren',
    fulfil_source_demand: 'Bedarf als erfüllt markieren',
    hold: 'Los anhalten',
    mark_ordered: 'Position als bestellt markieren',
    mark_requested: 'Position als angefragt markieren',
    merge: 'Fertigungsaufträge zusammenführen',
    move: 'In andere Bestellung verschieben',
    pause: 'Pausieren',
    release: 'Zuteilung aufheben',
    reopen: 'Position wieder öffnen',
    request_order: 'Bestellung als angefragt markieren',
    resume_lot: 'Los fortsetzen',
    reverse_completion: 'Fertigmeldung stornieren',
    scrap: 'Teile verschrotten',
    source_from_stock: 'Aus dem Lager nehmen',
    split: 'Fertigungsauftrag teilen',
    start: 'Starten oder fortsetzen',
    submit_order: 'Bestellung als bestellt markieren',
    take_from_stock: 'Aus dem Lager nehmen',
    unassign_external: 'Lieferantenposition entfernen',
    update_allocation: 'Zuteilung ändern',
  },
  actions: {
    deliver: 'Wareneingang buchen',
    correct_delivery: 'Lieferung korrigieren',
    close_short: 'Restmenge ausbuchen',
    reopen: 'Wieder öffnen',
    mark_ready_for_pickup: 'Als abholbereit markieren',
    cancel: 'Stornieren',
    hold: 'Anhalten',
    resume: 'Fortsetzen',
    force_complete: 'Zwangsweise abschließen',
    start: 'Starten',
    pause: 'Pausieren',
    record_completion: 'Fertigmeldung buchen',
    reverse_completion: 'Fertigmeldung stornieren',
    mark_requested: 'Als angefragt markieren',
    mark_ordered: 'Als bestellt markieren',
    fulfil: 'Als erfüllt markieren',
    allocate: 'Zuteilen',
    edit_quantity: 'Menge ändern',
    edit_structure: 'Arbeitsschritte ändern',
    reorder_positions: 'Positionen umsortieren',
    move: 'In andere Bestellung verschieben',
    remove: 'Löschen',
    scrap: 'Teile verschrotten',
    split: 'Aufteilen',
    merge: 'Zusammenführen',
    assign_external: 'Extern bestellen',
    assign_internal: 'Intern einplanen',
    unassign_external: 'Lieferantenposition entfernen',
    record_provision: 'Beistellung buchen',
    set_status: 'Status setzen',
    send: 'Als versendet markieren',
    award: 'Vergeben',
    close: 'Abschließen',
    approve_source: 'Quelle freigeben',
    reject_source: 'Quelle ablehnen',
    switch_source: 'Materialquelle ändern',
    complete: 'Abschließen',
    archive: 'Archivieren',
    edit: 'Bearbeiten',
    add_item: 'Position hinzufügen',
  },
  rows: {
    order_status: {
      r1: 'Jemand hat die Bestellung storniert.',
      r2: 'Die Bestellung hat keine Positionen.',
      r2Result: 'Bestellt, sobald abgeschickt, angefragt, sobald angefragt, sonst Entwurf',
      r3: 'Alle Positionen sind storniert.',
      r4: 'Alle nicht stornierten Positionen sind geliefert.',
      r5: 'Eine nicht stornierte Position ist ganz oder teilweise geliefert.',
      r6: 'Die Bestellung wurde abgeschickt, oder alle nicht stornierten Positionen sind bestellt.',
      r7: 'Eine nicht stornierte Position ist bestellt.',
      r8: 'Die Bestellung wurde angefragt, oder alle nicht stornierten Positionen sind angefragt.',
      r9: 'In allen anderen Fällen.',
    },
    order_item_status: {
      r1: 'Jemand hat die Position storniert.',
      r2: 'Gelieferte und verlorene Stück erreichen die Positionsmenge.',
      r3: 'Ein Teil wurde geliefert oder ist verloren gegangen.',
      r4: 'Die Position wurde als bestellt markiert.',
      r5: 'Die Position wurde als angefragt markiert.',
      r6: 'In allen anderen Fällen.',
    },
    production_order_status: {
      r1: 'Jemand hat den Fertigungsauftrag storniert.',
      r2: 'Die bearbeiteten Stück erreichen die Auftragsmenge.',
      r3: 'Der Auftrag wurde noch nie gestartet.',
      r4: 'Der Auftrag hat eine offene Unterbrechung.',
      r5: 'In allen anderen Fällen.',
    },
    lot_position_kind: {
      r1: 'Die Position hat eine Lieferantenposition und dazu Fertigungsaufträge oder eigenen Fortschritt.',
      r2: 'Die Position hat eine Lieferantenposition.',
      r3: 'Die Position hat einen nicht stornierten Fertigungsauftrag oder eigenen Fortschritt.',
      r4: 'In allen anderen Fällen.',
    },
    lot_position_status: {
      r1: 'Das Los wurde storniert.',
      r2: 'Die fertigen Stück erreichen die Menge der Position.',
      r3: 'Ein Teil ist fertig.',
      r4: 'Ein Fertigungsauftrag läuft oder ist pausiert.',
      r5: 'Die Lieferantenposition ist bestellt oder teilweise geliefert, oder ein Fertigungsauftrag wartet in der Warteschlange.',
      r6: 'In allen anderen Fällen.',
    },
    lot_status: {
      r1: 'Jemand hat das Los storniert.',
      r2: 'Es ist nichts mehr zu fertigen.',
      r3: 'Jemand hat das Los zwangsweise abgeschlossen, oder alle Positionen sind fertig.',
      r4: 'Jemand hat das Los angehalten.',
      r5: 'Eine Position hat begonnen oder hat fertige Stück.',
      r6: 'Alle Positionen sind eingeplant.',
      r7: 'Einige Positionen sind eingeplant.',
      r8: 'In allen anderen Fällen.',
    },
    demand_status: {
      r1: 'Jemand hat den Bedarf storniert.',
      r2: 'Jemand hat ihn von Hand als erfüllt markiert.',
      r3: 'Gelieferte Stück und Lager decken die Menge.',
      r4: 'Zuteilungen und Lager decken die Menge, und jede Bestellung oder jedes Los dahinter ist platziert.',
      r5: 'Etwas ist zugeteilt oder aus dem Lager genommen.',
      r6: 'In allen anderen Fällen.',
    },
    quote_request_status: {
      r1: 'Jemand hat die Anfrage storniert.',
      r2: 'Jemand hat die Anfrage abgeschlossen.',
      r3: 'Jede Position ist vergeben oder verworfen, mindestens eine ist vergeben.',
      r4: 'Jede Position wurde verworfen.',
      r5: 'Die Anfrage ging an mindestens einen Lieferanten.',
      r6: 'In allen anderen Fällen.',
    },
  },
  intentRows: {
    order: {
      mark_requested: {
        effect: 'Fragt die Bestellung und ihre offenen Positionen an.',
      },
      mark_ordered: {
        effect: 'Schickt die Bestellung ab und markiert ihre offenen und angefragten Positionen als bestellt.',
      },
      cancel: {
        effect: 'Gelieferte Positionen bleiben, teilweise gelieferte werden mit Restmenge abgeschlossen, die übrigen storniert und ihre Bedarfe freigegeben.',
        permission: 'Bestellungen verwalten, sobald die Bestellung abgeschickt ist',
      },
      deliver: {
        effect: 'Bucht alle lieferbaren Positionen in einem Schritt.',
      },
      edit: {
        condition: 'Niemand hat die Bestellung storniert.',
        effect: 'Ändert Lieferant, Termine, Notizen und die übrigen Kopfdaten.',
        permission: 'Bestellungen verwalten, sobald die Bestellung abgeschickt ist',
      },
      add_item: {
        condition: 'Niemand hat die Bestellung storniert.',
        effect: 'Fügt eine neue offene Position hinzu.',
        permission: 'Bestellungen verwalten, sobald die Bestellung über angefragt hinaus ist',
      },
    },
    order_item: {
      mark_requested: {
        effect: 'Hält die Anfrage fest.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
      },
      mark_ordered: {
        effect: 'Hält das Bestelldatum fest.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
      },
      deliver: {
        condition: 'Die Bestellung ist nicht storniert, und bei einer Los-Position ist das Los nicht storniert.',
        effect: 'Bucht die erhaltenen Stück.',
      },
      mark_ready_for_pickup: {
        condition: 'Die Bestellung ist nicht storniert.',
        effect: 'Hält fest, wann die Ware abholbereit ist, nie ein Zeitpunkt in der Zukunft.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
      },
      edit: {
        effect: 'Ändert Notiz, Termine, Preis und Lagerplatz; Einheit, Artikel und Projekt nur, bis Ware eingegangen ist.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
      },
      correct_delivery: {
        condition: 'Keine Position für ein Los, Restmenge nicht ausgebucht und die Bestellung nicht storniert.',
        effect: 'Nimmt Stück aus einer Lieferung als falsch gezählt oder als nach dem Wareneingang zurückgewiesen zurück, nie unter das, was Bedarfe schon verbraucht haben.',
      },
      close_short: {
        condition: 'Es wurde etwas geliefert oder ist verloren gegangen.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Senkt die Menge auf das Gelieferte oder Verlorene; der Lieferant liefert nichts mehr.',
      },
      reopen: {
        condition: 'Restmenge ausgebucht, keine Position für ein Los und die Bestellung nicht storniert.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Holt die Menge von vor dem Ausbuchen zurück; die Position wartet wieder auf den Rest.',
      },
      cancel: {
        condition: 'Es wurde nichts geliefert und nichts ist verloren gegangen.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Storniert die Position und gibt ihre Bedarfe frei.',
      },
      edit_quantity: {
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Nie unter das Gelieferte oder Verlorene und nie unter das, was Bedarfe zugeteilt haben.',
      },
      move: {
        condition: 'Es wurde nichts geliefert oder zurückgewiesen, und niemand hat die Zielbestellung storniert.',
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Verschiebt die Position in die andere Bestellung.',
      },
      remove: {
        permission: 'Bestellungen verwalten, sobald die Position oder ihre Bestellung über angefragt hinaus ist',
        effect: 'Löscht die Position und gibt ihre Bedarfe frei.',
      },
    },
    production_order: {
      start: {
        condition: 'Das Los ist nicht angehalten oder abgeschlossen, eine Maschine steht fest, und der vorige Schritt hat Stück bereit.',
        effect: 'Hält den Start und die Bedienperson fest.',
      },
      resume: {
        condition: 'Jemand hat ihn von Hand pausiert, das Los ist nicht angehalten, und der vorige Schritt hat Stück bereit.',
        effect: 'Beendet die Pause.',
      },
      pause: {
        effect: 'Beginnt eine Pause.',
      },
      cancel: {
        effect: 'Storniert den Auftrag und beendet eine laufende Pause.',
      },
      record_completion: {
        condition: 'Das Los ist nicht angehalten.',
        effect: 'Bucht fertige Stück, höchstens die Auftragsmenge; Ausschuss nur bei einem Prüfschritt.',
      },
      reverse_completion: {
        condition:
          'Das Los ist nicht angehalten, die Fertigmeldung hat nichts ausgeschieden und ist noch nicht storniert, das Los ist nicht abgeschlossen, und die nächste Position hat ihre Stück noch nicht verwendet.',
        permission: 'Fertigmeldungen stornieren',
        effect:
          'Bucht die Stück der Fertigmeldung mit einem Grund zurück; beide bleiben erhalten, und die fertige Menge sinkt.',
      },
      scrap: {
        condition: 'Das Los ist nicht angehalten.',
        effect: 'Bucht verschrottete Stück und verkleinert das Los.',
      },
      split: {
        effect: 'Teilt den Auftrag auf derselben Maschine und im selben Pool.',
      },
      merge: {
        effect: 'Fasst wartende Aufträge derselben Maschine und desselben Pools zusammen.',
      },
    },
    lot_position: {
      assign_external: {
        condition:
          'Das Los ist nicht abgeschlossen, es gibt noch keine Lieferantenposition oder nur solche mit ausgebuchter Restmenge, und es ist noch Menge frei.',
        effect:
          'Legt eine Lieferantenposition für höchstens die freie Menge an; eine Position mit ausgebuchter Restmenge bleibt daneben bestehen.',
      },
      unassign_external: {
        condition: 'Die Position wird zugekauft, und ihre Lieferantenposition ist offen oder angefragt.',
        effect: 'Löscht die Lieferantenposition.',
      },
      assign_internal: {
        condition: 'Das Los ist nicht abgeschlossen, und es ist noch Menge frei.',
        effect: 'Legt Fertigungsaufträge für höchstens die freie Menge an.',
      },
      record_provision: {
        condition: 'Das Los ist nicht abgeschlossen und die Position wird zugekauft.',
        effect: 'Bucht beigestelltes Material, höchstens so viel, wie der vorige Schritt bereitgestellt hat.',
      },
    },
    lot: {
      hold: {
        effect: 'Pausiert die laufenden Fertigungsaufträge.',
      },
      resume: {
        effect: 'Setzt die Aufträge fort, die das Anhalten pausiert hat.',
      },
      cancel: {
        condition: 'Noch keine Position hat ein Gutteil fertig; sonst schließ das Los zwangsweise ab.',
        permission: 'Lose verwalten',
        effect:
          'Storniert die offene Arbeit des Loses, lässt bestellte Lieferantenpositionen offen, gibt seine Bedarfe frei und rechnet sein Rohmaterial ab.',
      },
      force_complete: {
        condition: 'Eine Position hat ein Gutteil fertig.',
        permission: 'Lose verwalten',
        effect:
          'Schließt das Los bei der gefertigten Menge ab, beendet seine offene Arbeit und rechnet sein Rohmaterial ab.',
      },
      scrap: {
        effect:
          'Verkleinert die Position und die Arbeit danach. Beim Wareneingang als verloren gebuchte Stück sind eine erfasste Tatsache, keine Verschrottung, und bleiben auch bei einem angehaltenen Los erlaubt.',
      },
      edit_structure: {
        effect: 'Ändert Schritte von Positionen, die nicht zugewiesen sind und keinen Fortschritt haben.',
      },
      reorder_positions: {
        effect: 'Verschiebt nur Positionen, die nicht zugewiesen sind und nichts Fertiges haben.',
      },
      edit_quantity: {
        effect:
          'Die Positionen und ein offener Rohmaterialbedarf ziehen mit; nie unter das, was Bedarfe zugeteilt haben.',
      },
      approve_source: {
        condition:
          'Die Materialquelle wartet auf Freigabe oder wurde abgelehnt, das Projekt ist aktiv und der Rohblock ist noch verwendbar.',
        effect: 'Gibt die Materialquelle frei und legt ihren Rohmaterialbedarf an.',
      },
      reject_source: {
        condition: 'Die Materialquelle wartet auf Freigabe.',
        effect: 'Lehnt die Materialquelle mit einem Grund ab; es entsteht kein Bedarf.',
      },
      switch_source: {
        condition: 'Der Rohmaterialbedarf, falls es einen gibt, ist nicht erfüllt.',
        effect:
          'Ersetzt den Rohmaterialbedarf und behält, was schon eingetroffen ist; die neue Quelle wartet auf Freigabe oder bekommt einen Bedarf für das Fehlende.',
      },
    },
    demand: {
      cancel: {
        condition: 'Bei einem Rohmaterialbedarf hat sein Los die Fertigung noch nicht begonnen.',
        effect:
          'Storniert den Bedarf und gibt seine Zuteilungen frei. Bei einem Rohmaterialbedarf wählst du, was mit seinem Los passiert: Es wird mitstorniert, oder es bleibt ohne Bedarf und wartet auf Rohmaterial.',
      },
      fulfil: {
        effect:
          'Markiert den Bedarf von Hand als erfüllt. Ein Zukaufteile- oder Rohblock-Bedarf behält auf seinen Bestellpositionen nur die Teile, die für ihn eingetroffen sind; der Rest dieser Zuteilungen wird freigegeben.',
      },
      allocate: {
        effect: 'Teilt aus Bestellungen, Losen oder dem Lager zu, nie mehr als der Bedarf braucht.',
      },
      edit_quantity: {
        effect: 'Nie unter das Zugeteilte.',
      },
      remove: {
        condition: 'Nichts ist zugeteilt.',
        effect: 'Löscht den Bedarf.',
      },
    },
    catalogue_item: {
      to_active: {
        effect: 'Nennt keinen Nachfolger; ein gespeicherter fällt weg.',
      },
      to_inactive: {
        effect: 'Nennt keinen Nachfolger; ein gespeicherter fällt weg.',
      },
      to_replaced: {
        effect: 'Braucht einen Nachfolger, der existiert, nicht archiviert ist und nicht zurückführt.',
      },
    },
    project: {
      hold: {
        effect: 'Hält das Projekt an. Es nimmt keine neue Arbeit an; offene Arbeit läuft weiter.',
      },
      resume: {
        effect: 'Macht das Projekt wieder aktiv, damit es neue Arbeit annimmt.',
      },
      complete: {
        condition: 'Keine offenen Lose, Fertigungsaufträge, Bestellpositionen, Bedarfe oder Anfragen.',
        effect: 'Schließt das Projekt ab.',
      },
      archive: {
        condition: 'Keine offenen Lose, Fertigungsaufträge, Bestellpositionen, Bedarfe oder Anfragen.',
        effect: 'Archiviert das Projekt.',
      },
      reopen: {
        effect: 'Macht das Projekt wieder aktiv, damit es neue Arbeit annimmt.',
      },
      remove: {
        condition: 'Keine offenen Lose, Fertigungsaufträge, Bestellpositionen, Bedarfe oder Anfragen.',
        effect: 'Löscht das Projekt.',
      },
    },
    quote_request: {
      send: {
        condition: 'Mindestens eine Position und ein Lieferant.',
        effect: 'Hält fest, dass die Anfrage an den Lieferanten ging, der damit für jede Position angefragt ist.',
      },
      award: {
        condition: 'Mindestens eine offene Position.',
        effect: 'Legt jede gewählte Position auf eine Entwurfsbestellung des Lieferanten, der sie gewonnen hat.',
      },
      close: {
        condition: 'Mindestens eine vergebene Position.',
        effect: 'Verwirft die noch offenen Positionen und schließt die Anfrage ab.',
      },
      cancel: {
        condition: 'Keine vergebene Position.',
        effect: 'Storniert die Anfrage. Die Bedarfe darin bleiben offen.',
      },
      reopen: {
        condition: 'Jemand hat die Anfrage abgeschlossen, und seither wurde eine Vergabe darauf aufgehoben.',
        effect: 'Hebt den Abschluss auf, sodass die Anfrage wieder versendet oder ein Entwurf ist und die aufgehobene Position neu vergeben werden kann. Die Angebote bleiben, und die beim Abschluss verworfenen Positionen bleiben verworfen, bis du sie zurückholst.',
      },
    },
  },
}
