// Messages for productionQueue, merged into the de-AT locale.
export default {
  tabLabel: 'Warteschlange',
  board: {
    title: 'Fertigungswarteschlange',
    empty: 'Keine Fertigungsmaschinen gefunden.',
    machineEmpty: 'Keine Aufträge eingeplant.',
    loadError: 'Fertigungswarteschlange konnte nicht geladen werden.',
    showCompleted: 'Abgeschlossene anzeigen',
    hideNotReady: 'Nicht bereite ausblenden',
    hideNotReadyTooltip: 'Blendet die wartenden Aufträge aus, die noch nicht gestartet werden können',
    dateRange: 'Zeitraum',
    modeHorizontal: 'Horizontal',
    modeVertical: 'Vertikal',
    noMachine: 'Keine Maschine zugewiesen',
    noMachineSubtitle: 'Aufträge ohne Maschine und ohne Pool',
    manualWork: 'Manuelle Arbeit',
    inspection: 'Prüfung',
    poolMachineCount: 'Keine Maschinen | 1 Maschine | {count} Maschinen',
    groups: {
      active: 'In Bearbeitung',
      overdue: 'Überfällig',
      today: 'Heute',
      terminal: 'Abgeschlossen / Storniert',
    },
  },
  status: {
    queued: 'Eingeplant',
    in_progress: 'In Bearbeitung',
    paused: 'Pausiert',
    completed: 'Abgeschlossen',
    canceled: 'Storniert',
  },
  priority: {
    low: 'Niedrig',
    normal: 'Normal',
    high: 'Hoch',
    critical: 'Kritisch',
  },
  card: {
    pin: 'Nach oben anheften',
    unpin: 'Lösen',
    printLabel: 'Etikett drucken',
    printLabelSent: 'Etikett an Drucker gesendet.',
    printLabelFailed: 'Druck fehlgeschlagen.',
    printDocket: 'Laufzettel drucken',
    printDocketSent: 'An den Drucker gesendet.',
    printDocketFailed: 'Der Laufzettel konnte nicht gedruckt werden.',
    pinError: 'Anheften konnte nicht aktualisiert werden.',
    cancelError: 'Auftrag konnte nicht storniert werden.',
    cancelConfirm: {
      header: 'Fertigungsauftrag stornieren',
      message:
        'Willst du {number} stornieren? Der Auftrag endet und nimmt keine weitere Arbeit an. Das kann nicht rückgängig gemacht werden.',
      accept: 'Auftrag stornieren',
    },
    cancelOthersTooltip:
      'Diesen Auftrag hat jemand anderer angelegt, zum Stornieren brauchst du deshalb die Berechtigung {permission}.',
    startError: 'Fertigungsauftrag konnte nicht gestartet werden.',
    reorderError: 'Warteschlange konnte nicht neu sortiert werden.',
    reassignError: 'Auftrag konnte nicht auf diese Maschine verschoben werden.',
    dragHint: 'Ziehen, um innerhalb dieser Maschine neu zu ordnen.',
    lockedPinned: 'Angeheftete Aufträge können nicht umsortiert werden. Zuerst lösen.',
    lockedInProgress: 'Aufträge in Bearbeitung können nicht umsortiert werden.',
    waitingOnRawMaterial: 'Wartet auf Rohmaterial',
    waitingOnRawMaterialTooltip:
      'Für dieses Los ist noch kein Rohmaterial eingetroffen, Fertigmeldungen sind erst möglich, sobald welches eingetroffen ist.',
    noMachine: 'Keine Maschine zugewiesen',
    noMachineTooltip: 'Weise eine Maschine zu, bevor dieser Auftrag gestartet werden kann.',
    inspectionPermissionTooltip:
      'Für einen Prüfschritt brauchst du die Berechtigung Qualitätsprüfungen erfassen.',
    cannotStartTooltip:
      'Dieser Auftrag kann noch nicht gestartet werden, weil der vorgelagerte Schritt noch nichts bereitgestellt hat oder das Los pausiert ist.',
    poolTag: 'Pool: {pool}',
    poolUnresolvedTooltip:
      'Diesem Maschinenpool zugewiesen, beim Starten wird nach der zu verwendenden Maschine gefragt.',
    poolResolvedTooltip: 'Dieser Auftrag wurde über diesen Maschinenpool zugewiesen.',
    productionOrderTooltip: 'Fertigungsauftragsnummer',
    quantity: 'Menge',
    processMethod: 'Verfahren',
    material: 'Material',
    mass: 'Masse',
    massValue: '{kg} kg',
    sourceMaterial: 'Ausgangsmaterial',
    materialMismatch: 'Materialabweichung',
    materialMismatchTooltip:
      'Das Ausgangsmaterial ({actual}) weicht vom angegebenen Material des Artikels ({expected}) ab.',
    sourceDelivered: 'Geliefert am {date}',
    sourceExpected: 'Erwartet am {date}',
    sourceOrdered: 'Bestellung {number}',
    actions: {
      start: 'Starten',
      resume: 'Fortsetzen',
      pause: 'Pausieren',
      complete: 'Abschließen',
      split: 'Teilen',
      merge: 'Zusammenführen',
      scrap: 'Teile verschrotten',
      cancel: 'Stornieren',
      more: 'Weitere Aktionen',
    },
  },
  conflicts: {
    no_machine_assigned: 'Keine Maschine zugewiesen',
    no_machine_assignedTooltip: 'Für diesen Auftrag wurde noch keine Maschine gewählt.',
    capability_mismatch: 'Fähigkeitskonflikt',
    capability_mismatchTooltip:
      'Die zugewiesene Maschine deckt das für diesen Schritt erforderliche Fertigungsverfahren nicht ab.',
    uncategorized_step: 'Nicht kategorisierter Schritt',
    uncategorized_stepTooltip: 'Diesem Schritt ist kein Fertigungsverfahren zugewiesen.',
    position_not_fully_queued: 'Nicht vollständig eingeplant',
    position_not_fully_queuedTooltip:
      'Die eingeplanten Aufträge dieser Position ergeben noch nicht die volle Menge.',
    waiting_on_predecessor: 'Wartet auf Vorgänger',
    waiting_on_predecessorTooltip:
      'Dieser Auftrag kann erst starten, wenn der vorherige Schritt bereit ist.',
    waiting_on_material: 'Wartet auf Material',
    waiting_on_materialTooltip:
      'Dieser Auftrag kann erst starten, wenn das Rohmaterial eingetroffen ist.',
    estimate_from_time_budget: 'Aus Projektbudget geschätzt',
    estimate_from_time_budgetTooltip:
      'Diese Dauer enthält mindestens einen Schritt mit der Projektzeitbudget-Schätzung anstelle einer echten Messung.',
    missing_time_estimate: 'Keine Zeitschätzung',
    missing_time_estimateTooltip:
      'Für diesen Schritt gibt es weder eine echte Zeitschätzung noch ein Projektbudget als Ersatz, der Beitrag zur Dauer ist schlicht 0.',
    past_target_date: 'Zieltermin überschritten',
    past_target_dateTooltip:
      'Das geplante Ende dieses Auftrags liegt nach dem Zieltermin des Loses.',
    external_date_before_predecessor: 'Lieferantentermin vor Vorgänger',
    external_date_before_predecessorTooltip:
      'Der beim externen Schritt eingetragene Lieferantentermin liegt vor dem Schritt, der ihn versorgt. Prüf die Termine der Bestellposition.',
    machine_down: 'Maschine ausgefallen',
    machine_downTooltip:
      'Die diesem Auftrag zugewiesene Maschine hat gerade eine offene Ausfallzeit.',
    no_working_time: 'Keine Arbeitszeit',
    no_working_timeTooltip:
      'Die Maschine dieses Auftrags hat in ihrem Kalender keine Arbeitszeit, deshalb hat der Auftrag keine Termine.',
    window_overlap: 'Überlappendes Zeitfenster',
    window_overlapTooltip:
      'Dieser Auftrag behält sein angeheftetes Zeitfenster oder das im fixierten Planungszeitraum, und es beginnt, bevor der Auftrag davor auf der Maschine endet.',
    window_before_predecessor: 'Zeitfenster vor dem Vorgänger',
    window_before_predecessorTooltip:
      'Dieser Auftrag behält sein angeheftetes Zeitfenster oder das im fixierten Planungszeitraum, und es beginnt, bevor der vorige Schritt seines Loses fertig ist.',
    chain_cycle: 'Vor dem Vorgänger eingereiht',
    chain_cycleTooltip:
      'Ein Schritt dieses Loses wartet auf einen Schritt, der auf derselben Maschine dahinter eingereiht ist, deshalb kann keiner von beiden terminiert werden. Reih den früheren Schritt in der Warteschlange vor den späteren.',
  },
  operators: {
    label: 'Bediener',
    placeholderRequired: 'Bediener auswählen',
    required: 'Bitte wähl einen Bediener aus, bevor du fortfährst.',
    noneAssigned:
      'Diesem gemeinsamen Konto sind noch keine Bediener zugewiesen. Bitte einen Administrator, Mitglieder zuzuweisen, bevor du fortfährst.',
  },
  split: {
    title: 'Fertigungsauftrag teilen',
    explain: 'So funktioniert das Teilen',
    description: 'Teile diesen Auftrag (Menge {quantity}) in zwei oder mehr Teile.',
    part: 'Teil {index}',
    addPart: 'Teil hinzufügen',
    removePart: 'Teil entfernen',
    sum: 'Summe: {sum} / {quantity}',
    errors: {
      invalid: 'Mengen müssen positiv sein und der ursprünglichen Menge entsprechen.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  merge: {
    title: 'Fertigungsaufträge zusammenführen',
    explain: 'So funktioniert das Zusammenführen',
    description:
      'Führe diesen Auftrag mit anderen eingeplanten Aufträgen derselben Losposition auf dieser Maschine zusammen.',
    noSiblings: 'Keine weiteren eingeplanten Aufträge zum Zusammenführen verfügbar.',
    qty: 'Menge {qty}',
    submit: 'Zusammenführen',
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  start: {
    title: 'Fertigungsauftrag starten',
    explain: 'So funktioniert das Starten',
    submit: 'Starten',
    selectMachine: 'Maschine',
    selectMachinePlaceholder: 'Maschine auswählen',
    poolHint:
      'Dieser Auftrag wurde dem Pool {pool} zugewiesen, wähle, auf welcher Maschine er laufen soll.',
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
      machineRequired: 'Bitte wähl eine Maschine aus, bevor du fortfährst.',
    },
  },
  pause: {
    title: 'Fertigungsauftrag pausieren',
    explain: 'So funktioniert das Pausieren',
    reason: 'Grund',
    submit: 'Pausieren',
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  completion: {
    title: 'Fertigstellung erfassen',
    explain: 'So funktionieren Fertigmeldungen',
    quantity: 'Fertiggestellte Menge',
    date: 'Fertigstellungsdatum',
    note: 'Notiz',
    submit: 'Erfassen',
    accepted: 'Angenommen',
    rejected: 'Zurückgewiesen',
    rejectReason: 'Grund der Zurückweisung',
    rejectReasonPlaceholder: 'Warum sind die Teile durchgefallen?',
    perUnitTitle: 'Zurückgewiesene Stücke klassifizieren',
    perUnitPiece: 'Stück {n}',
    rework: 'Nacharbeit',
    replacement: 'Neufertigung',
    reworkQuantity: 'Nacharbeits-Menge',
    scrapQuantity: 'Ausschuss-Menge',
    dispositionSummary:
      'Erstellt ein Nacharbeits-Los von {rework} und ein Neufertigungs-Los von {scrap}, und die Bedarfsdeckung wird automatisch übertragen.',
    evidenceRequired:
      'Vor dem Erfassen dieser Fertigstellung muss mindestens ein Messprotokoll hochgeladen werden.',
    permissionDenied: 'Du hast keine Berechtigung, Qualitätsprüfungen zu erfassen.',
    createdLotsToast: '{lots} erstellt.',
    createdLotRework: '{lotNumber} (Nacharbeit)',
    createdLotReplacement: '{lotNumber} (Neufertigung)',
    files: {
      title: 'Nachweise',
      measurement_report: 'Messprotokolle',
    },
    errors: {
      invalid: 'Bitte füll alle Pflichtfelder aus.',
      dispositionSum:
        'Nacharbeits- und Neufertigungsmenge müssen zusammen der zurückgewiesenen Menge entsprechen.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
}
