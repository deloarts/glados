// Messages for productionSchedule, merged into the de-AT locale.
export default {
  tabLabel: 'Kapazität',
  dateRange: 'Zeitraum',
  weekPrefix: 'KW',
  empty: 'Keine Maschinen für diesen Zeitraum.',
  machinesSectionTitle: 'Maschinen',
  staleSince:
    'Änderungen seit {time} werden noch in die gespeicherten Plantermine eingearbeitet. Diese Übersicht ist bereits aktuell.',
  poolsSectionTitle: 'Maschinenpools',
  poolsEmpty: 'Keine Maschinenpools für diesen Zeitraum.',
  machineOrdersEmpty: 'Keine Aufträge in diesem Zeitraum.',
  overbookedTooltip: '+{hours} überbucht',
  floatingTag: 'Ungelöst',
  floatingTooltip:
    'Dieser Auftrag ist im Pool eingeplant, aber noch keiner bestimmten Maschine zugewiesen; die Termine sind vorläufig und können sich noch ändern.',
  floatingTooltipReserved: 'Auf {machine} reserviert.',
  columns: {
    machine: 'Maschine',
    orders: 'Aufträge',
    order: 'Auftrag',
    lot: 'Los',
    project: 'Projekt',
    item: 'Artikel',
    step: 'Schritt',
    window: 'Zeitfenster',
    conflicts: 'Konflikte',
  },
  autoPlan: {
    trigger: 'Auto-Planen',
    title: 'Zeitplan automatisch planen',
    description:
      'Schlägt eine an Priorität und Liefertermin orientierte Neu-Reihung für alle geeigneten, wartenden Aufträge vor und wendet sie an. Laufende Aufträge werden nie verändert; angeheftete Aufträge bleiben unangetastet, außer du erlaubst unten, sie zu überschreiben.',
    algorithm: 'Planungsalgorithmus',
    algorithms: {
      urgentFirst: {
        label: 'Dringend zuerst',
        description:
          'Platziert dringende Aufträge zuerst, danach den am frühesten fälligen; jeder Auftrag geht an die Maschine, die ihn am schnellsten fertigstellt. Das Standardverhalten.',
        ordering:
          'Zuerst die Dringlichkeitsklasse (dringendste zuerst), dann das früheste Fälligkeitsdatum der Position, dann die Erstellungsreihenfolge.',
        selection:
          'Frühester Fertigstellungstermin, jene geeignete Maschine, die den Auftrag am schnellsten fertigstellt.',
        bestFor:
          'Die tägliche Planung, bei der ein ausdrücklich als dringend markierter Auftrag die Warteschlange tatsächlich überholen soll.',
        watchOut:
          'Ein stetiger Strom dringender Aufträge schiebt alles andere immer weiter nach hinten, egal wie nah dessen eigener Termin ist.',
      },
      strictDeadline: {
        label: 'Strikte Frist',
        description:
          'Ignoriert Dringlichkeitsmarkierungen vollständig, Aufträge werden immer strikt nach Fälligkeitsdatum eingeordnet, um die maximale Verspätung zu minimieren.',
        ordering:
          'Ausschließlich das früheste Fälligkeitsdatum der Position; Dringlichkeitsmarkierungen werden vollständig ignoriert. Gleichstand entscheidet die Erstellungsreihenfolge.',
        selection:
          'Frühester Fertigstellungstermin, jene geeignete Maschine, die den Auftrag am schnellsten fertigstellt.',
        bestFor:
          'Termintreue, diese Reihung minimiert nachweislich, wie spät der schlechteste einzelne Auftrag ausfällt.',
        watchOut:
          'Ein als dringend markierter Auftrag überholt einen früher fälligen Auftrag nicht mehr.',
      },
      fairQueue: {
        label: 'Faire Warteschlange',
        description:
          'Keine Neupriorisierung, Aufträge werden in der Reihenfolge ihrer Erstellung eingeplant, vollständig vorhersehbar.',
        ordering: 'Ausschließlich die Erstellungsreihenfolge, sonst nichts.',
        selection:
          'Frühester Fertigstellungstermin, jene geeignete Maschine, die den Auftrag am schnellsten fertigstellt.',
        bestFor:
          'Eine neutrale, vollständig vorhersehbare Ausgangsbasis, auch nützlich, um zu sehen, was die anderen Algorithmen tatsächlich verändern.',
        watchOut:
          'Ignoriert sowohl Dringlichkeit als auch Fälligkeitsdaten; ein spät erstellter, aber dringender Auftrag wird dadurch überhaupt nicht bevorzugt.',
      },
      balancedLoad: {
        label: 'Ausgeglichene Auslastung',
        description:
          'Gleiche Dringlichkeits-/Fälligkeitsreihenfolge wie bei Dringend zuerst, verteilt die Arbeit aber gleichmäßig auf die Maschinen, statt immer die schnellste zu wählen.',
        ordering:
          'Identisch zu Dringend zuerst, Dringlichkeit, dann Fälligkeitsdatum, dann Erstellungsreihenfolge.',
        selection:
          'Geringste Auslastung, jene geeignete Maschine mit den bisher wenigsten verplanten Minuten, bei Gleichstand entscheidet die Maschinen-ID.',
        bestFor:
          'Alle Maschinen ausgelastet halten und verhindern, dass eine einzelne Maschine den gesamten Rückstau aufnimmt.',
        watchOut:
          'Ein einzelner Auftrag kann später fertig werden als sonst, denn die am wenigsten ausgelastete Maschine ist nicht zwingend die schnellste verfügbare.',
      },
      criticalRatio: {
        label: 'Kritisches Verhältnis',
        description:
          '(Tage bis zur Fälligkeit) / (verbleibende Arbeitstage), niedriger = dringender. Passt sich automatisch mit der Zeit an, kann sich aber ungewöhnlich verhalten, sobald ein Fälligkeitsdatum bereits verstrichen ist.',
        ordering:
          '(Tage bis zur Fälligkeit) geteilt durch (verbleibende Arbeitstage), niedrigster Wert zuerst, bei jedem Durchlauf neu gegen das heutige Datum berechnet.',
        selection:
          'Frühester Fertigstellungstermin, jene geeignete Maschine, die den Auftrag am schnellsten fertigstellt.',
        bestFor:
          'Dringlichkeit und Auftragslänge von selbst gegeneinander abzuwägen, das Verhältnis schrumpft automatisch, je länger ein Auftrag wartet.',
        watchOut:
          'Sobald ein Fälligkeitsdatum bereits verstrichen ist, wird das Verhältnis negativ und die Reihung unintuitiv. Aufträge ohne Fälligkeitsdatum werden nie kritisch und landen ganz hinten.',
      },
      shortestProcessingTime: {
        label: 'Kürzeste Bearbeitungszeit',
        description:
          'Kürzeste Aufträge zuerst, unabhängig von Dringlichkeit oder Fälligkeitsdatum. Maximiert den Durchsatz, kann aber einen langen Auftrag unbegrenzt verzögern.',
        ordering:
          'Kürzeste geschätzte Dauer zuerst, unabhängig von Dringlichkeit oder Fälligkeitsdatum. Gleichstand entscheidet die Erstellungsreihenfolge.',
        selection:
          'Frühester Fertigstellungstermin, jene geeignete Maschine, die den Auftrag am schnellsten fertigstellt.',
        bestFor:
          'Einen Rückstau kleiner Aufträge rasch abbauen, es werden in kürzester Zeit die meisten Aufträge fertig.',
        watchOut:
          'Ein langer Auftrag kann unbegrenzt hintangestellt werden, solange immer wieder kürzere vor ihm eintreffen.',
      },
    },
    explain: {
      trigger: 'Erklären',
      tooltip: 'Zeigen, wie der Planungsalgorithmus arbeitet',
      // The prose lives in the handbook page
      // features/handbook/content/*/production/auto-plan.md. Only these
      // stay: the picker above reads the same per-algorithm labels.
      selected: 'Ausgewählt',
      facts: {
        ordering: 'Reihung',
        selection: 'Maschinenwahl',
        bestFor: 'Gut geeignet für',
        watchOut: 'Zu beachten',
      },
    },
    machines: 'Einzubeziehende Maschinen',
    assignMachines: 'Maschinenzuweisung erlauben',
    assignMachinesHint:
      'Standardmäßig deaktiviert: Aufträge werden nur innerhalb ihrer bereits zugewiesenen Maschine neu gereiht. Wenn aktiviert, kann auch einem nicht zugewiesenen Auftrag eine Maschine zugewiesen oder ein Auftrag auf eine andere Maschine verschoben werden, je nachdem, welche geeignete Maschine ihn am schnellsten fertigstellt.',
    planningLevel: 'Planungsebene',
    planningLevelOptions: {
      machines: 'Maschinen',
      pools: 'Pools',
    },
    overwritePinned: 'Überschreiben von manuell geplanten Terminen erlauben',
    overwritePinnedHint:
      'Standardmäßig deaktiviert: ein manuell angehefteter Auftrag wird nicht verändert und dient als fester Ankerpunkt. Wenn aktiviert, wird er ebenfalls zum Kandidaten, und ein tatsächlich verschobener angehefteter Auftrag wird dabei gelöst und wieder zu einem normalen, automatisch verwalteten Auftrag.',
    excludeTodaysPlanned: 'Heute geplante Aufträge ausschließen',
    excludeTodaysPlannedHint:
      'Standardmäßig aktiviert: ein Auftrag, der bereits für heute geplant ist, bleibt unangetastet, auch wenn er noch nicht begonnen hat, so wird die Warteschlange der Werkstatt für heute nicht durcheinandergebracht. Deaktivieren, um auch die heutige Warteschlange neu zu planen.',
    responseTimeDays: 'Reaktionszeit für geplanten Start (Tage)',
    responseTimeDaysHint:
      'Puffer, der auf die Ankunft eines Fremdbearbeitungsschritts und von Rohmaterial aufgeschlagen wird, bevor eines davon den frühesten Start des nächsten Schritts einschränken kann. Wird aus der Admin-Einstellung vorbefüllt; eine Änderung hier gilt nur für diesen Durchlauf.',
    run: 'Auto-Plan ausführen',
    before: 'Vorher',
    after: 'Nachher',
    noProposals: 'Keine Aufträge mussten neu geplant werden.',
    skipped:
      'Keine angehefteten oder laufenden Aufträge übersprungen. | 1 angehefteter oder laufender Auftrag übersprungen. | {count} angeheftete oder laufende Aufträge übersprungen.',
    skippedTodaysPlanned:
      'Keine bereits für heute geplanten Aufträge unangetastet gelassen. | 1 bereits für heute geplanter Auftrag unangetastet gelassen. | {count} bereits für heute geplante Aufträge unangetastet gelassen.',
    redated: {
      title: 'Vom Terminlauf neu datiert',
      hint: 'Aufträge, die dieser Lauf nicht eingeplant hat, deren Tag sich aber im Terminlauf danach geändert hat.',
      kept: 'Alle anderen offenen Aufträge haben ihren Tag behalten. | 1 weiterer offener Auftrag hat seinen Tag behalten. | {count} weitere offene Aufträge haben ihren Tag behalten.',
      none: 'Der Terminlauf hat keinen anderen Auftrag auf einen anderen Tag verschoben.',
      walkFailed: 'Der Zeitplan konnte nach diesem Lauf nicht aktualisiert werden. Die Termine folgen mit dem nächsten Terminlauf.',
      filter: {
        all: 'Alle',
        earlier: 'Früher',
        later: 'Später',
      },
      columns: {
        column: 'Spalte',
        before: 'Vorher',
        after: 'Nachher',
        shift: 'Verschiebung',
        reason: 'Grund',
      },
      shift: {
        earlier: '1 Tag früher | {count} Tage früher',
        later: '1 Tag später | {count} Tage später',
        dated: 'Jetzt datiert',
        undated: 'Kein Termin',
      },
      reason: {
        readyNow: 'Jetzt bereit',
        readyNowDetail: 'Nichts hält ihn auf.',
        queue: 'Nach {order}',
        queueRunning: 'Hinter laufendem {order}',
        queueDetail: 'Der endet {moment}.',
        queueOverrunDetail: 'Überzieht: {processed} von {quantity} gemeldet, {left} offen, endet etwa {moment}.',
        predecessor: 'Nach Position {sequence}',
        predecessorDetail: '{order} endet {moment}.',
        waitAfter: 'Wartezeit nach dem Schritt, {duration}',
        waitAfterDetail: 'Position {sequence} ist {moment} bereit.',
        orderLine: 'Wartet auf Bestellposition #{line}',
        orderLineDetail: 'Erwartet am {date}, plus {days} Tag Reaktionszeit. | Erwartet am {date}, plus {days} Tage Reaktionszeit.',
        orderLineLate: 'Bestellposition #{line} ist überfällig',
        orderLineLateDetail:
          'Erwartet am {date}, nicht geliefert: zählt als heute, plus {days} Tag Reaktionszeit. | Erwartet am {date}, nicht geliefert: zählt als heute, plus {days} Tage Reaktionszeit.',
        rawMaterial: 'Wartet auf Rohmaterial',
        rawMaterialDetail: 'Bereit am {date}, Reaktionszeit eingerechnet.',
        notBefore: 'Nicht vor {date}',
        running: 'Läuft',
        runningDetail: '{processed} von {quantity} gemeldet.',
        runningOverrunDetail: 'Überzieht: {processed} von {quantity} gemeldet, {left} offen.',
        pinned: 'Angeheftet',
        frozen: 'Im fixierten Zeitraum',
        undated: 'Noch kein Termin',
        undatedDetail: 'Ein früherer Schritt oder das Rohmaterial hat noch keinen Termin.',
        walkedMeanwhile: 'Von einem zwischenzeitlichen Terminlauf datiert',
      },
    },
    skippedOrders: {
      title:
        '1 Auftrag konnte nicht eingeplant werden: | {count} Aufträge konnten nicht eingeplant werden:',
      reasons: {
        waiting_on_material: 'Wartet auf Material',
        waiting_on_materialTooltip:
          'Das Rohmaterial dieses Auftrags ist weder eingetroffen noch mit einem Liefertermin bestellt, daher bleibt er unangetastet, bis der Bedarf zugeordnet oder bestellt wurde.',
        no_eligible_machine: 'Keine geeignete Maschine',
        no_eligible_machineTooltip:
          'Innerhalb des ausgewählten Bereichs ist keine für diesen Auftrag geeignete Maschine verfügbar.',
        no_eligible_pool: 'Kein geeigneter Pool',
        no_eligible_poolTooltip:
          'Auf Planungsebene "Pools" ist kein für diesen Auftrag geeigneter Maschinenpool verfügbar.',
        no_eligible_pool_member: 'Kein Pool-Mitglied im Bereich',
        no_eligible_pool_memberTooltip:
          'Ein geeigneter Pool existiert, aber keine seiner Maschinen liegt im ausgewählten Bereich dieses Laufs.',
        machine_down: 'Maschine ausgefallen',
        machine_downTooltip:
          'Eine geeignete Maschine (oder ein Pool-Mitglied) existiert, hat aber gerade eine offene Ausfallzeit und wurde deshalb bei diesem Lauf ausgeschlossen.',
        changed_while_planning: 'Während der Planung geändert',
        changed_while_planningTooltip:
          'Ein Auftrag in der Warteschlange, aus der dieser Auftrag kam oder in die er gehen sollte, hat sich während des Laufs geändert, daher blieb die Warteschlange, wie sie war. Starte Auto-Plan erneut, um ihn einzuplanen.',
        unknown: 'Nicht eingeplant',
        unknownTooltip: 'Der Planer konnte diesen Auftrag nicht einplanen.',
      },
    },
    progress: {
      preparing: 'Vorbereitung…',
      loading_orders: 'Fertigungsaufträge werden geladen…',
      scoring: 'Aufträge werden priorisiert…',
      placing: 'Aufträge werden eingeplant…',
      recomputing: 'Maschinenpläne werden neu berechnet…',
      finalizing: 'Ergebnis wird erstellt…',
      counter: '{current} / {total}',
      skippedTag: 'übersprungen',
      backgroundHint: 'Der Lauf läuft im Hintergrund weiter, wenn du diesen Dialog schließt.',
    },
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
      connectionLost:
        'Verbindung unterbrochen, der Lauf wird am Server fortgesetzt. Prüfe in Kürze die Plantafel.',
    },
    observer: {
      title: 'Auto-Planung läuft',
      startedBy: 'Gestartet von {user}',
      startedAt: 'um {time}',
      blocked: 'Ein neuer Lauf kann erst gestartet werden, wenn dieser abgeschlossen ist.',
      finished: 'Der von {user} gestartete Lauf ist abgeschlossen.',
    },
  },
}
