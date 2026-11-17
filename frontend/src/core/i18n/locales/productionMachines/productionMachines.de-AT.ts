// Messages for productionMachines, merged into the de-AT locale.
export default {
  controls: {
    new: 'Neue Maschine',
    search: 'Maschinen suchen…',
  },
  views: {
    sortByItems: {
      nameAsc: 'Name (A → Z)',
      nameDesc: 'Name (Z → A)',
      createdDesc: 'Erstellt (neueste zuerst)',
      createdAsc: 'Erstellt (älteste zuerst)',
    },
    groupByItems: {
      capability: 'Fähigkeit',
    },
  },
  columns: {
    internalName: 'Interner Name',
    status: 'Status',
    vendor: 'Hersteller',
    model: 'Modell',
    capabilities: 'Fähigkeiten',
    maxPartDimension: 'Max. Bauteilgröße',
    note: 'Notiz',
    created: 'Erstellt',
    actions: 'Aktionen',
  },
  table: {
    empty: 'Noch keine Produktionsmaschinen vorhanden.',
  },
  filters: {
    filterBy: 'Filtern',
    any: 'Beliebig',
  },
  viewMachine: 'Maschine ansehen',
  editMachine: 'Maschine bearbeiten',
  archiveBlocked:
    'Auf dieser Maschine ist noch {n} Fertigungsauftrag eingeplant, in Arbeit oder pausiert. Verschiebe oder beende ihn zuerst. | Auf dieser Maschine sind noch {n} Fertigungsaufträge eingeplant, in Arbeit oder pausiert. Verschiebe oder beende sie zuerst.',
  qaMachineTag: 'QS / Messmaschine',
  qaMachineTooltip:
    'Dedizierte Messmaschine, nur für QS-Prüfschritte auswählbar, nie für Fertigungsarbeit.',
  errors: {
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
  create: {
    createTitle: 'Neue Produktionsmaschine',
    editTitle: 'Produktionsmaschine bearbeiten',
    fields: {
      internalName: 'Interner Name',
      vendor: 'Hersteller',
      model: 'Modell',
      capabilities: 'Fähigkeiten',
      capabilitiesPlaceholder: 'Fähigkeiten auswählen…',
      capabilitiesHint:
        'Die Fertigungsmethoden, die diese Maschine kann. Nur Schritte mit einer dieser Methoden können auf ihr laufen.',
      capabilitiesQaDisabledHint:
        'QS-/Messmaschinen übernehmen keine Fertigungsarbeit; Fähigkeiten sind hier nicht relevant.',
      maxPartDimension: 'Max. Bauteilgröße',
      note: 'Notiz',
      isQaMachine: 'QS- / Messmaschine',
      isQaMachineHint:
        'Dedizierte hausinterne Messmaschine (z. B. ein Koordinatenmessgerät). Nur für QS-Prüfschritte auswählbar und von jeder Fertigungsarbeit ausgeschlossen.',
    },
    errors: {
      required: 'Bitte alle Pflichtfelder ausfüllen.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  calendar: {
    manage: 'Kalender verwalten',
    title: 'Kalender, {name}',
    workingHours: {
      title: 'Arbeitszeiten',
      useDefault: 'Globalen Standard verwenden',
      useCustom: 'Eigene Überschreibung',
    },
    exceptions: {
      title: 'Kalenderausnahmen',
      add: 'Hinzufügen',
      empty: 'Noch keine Kalenderausnahmen vorhanden.',
      columns: {
        date: 'Datum',
        availableMinutes: 'Verfügbar',
        note: 'Notiz',
      },
      edit: 'Bearbeiten',
      window: 'Ab {start} für {minutes} min',
      deleteConfirm: 'Kalenderausnahme für {date} löschen?',
      errors: {
        dateRequired: 'Bitte ein Datum auswählen.',
      },
    },
    editDefault: 'Standardkalender',
    defaultTitle: 'Standardkalender',
    defaultHint:
      'Wochenstunden, auf die Maschinen zurückfallen, sofern keine eigene Überschreibung besteht.',
  },
  downtime: {
    button: 'Stillstände',
    addDowntime: 'Stillstand hinzufügen',
    badge: 'Steht seit {time}',
    reasons: {
      breakdown: 'Defekt',
      maintenance: 'Wartung',
      tooling: 'Werkzeugwechsel',
      no_operator: 'Kein Bediener',
      no_material: 'Kein Material',
      other: 'Sonstiges',
    },
    form: {
      addTitle: 'Stillstand hinzufügen',
      explain: 'Stillstände erklären',
      fields: {
        machine: 'Maschine',
        startedAt: 'Beginn',
        endedAt: 'Ende',
        endedAtHint: 'Leer lassen für einen laufenden Stillstand.',
        reason: 'Grund',
        reasonPlaceholder: 'Grund auswählen…',
        note: 'Notiz',
      },
      errors: {
        required: 'Bitte alle Pflichtfelder ausfüllen.',
        unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
      },
    },
    list: {
      title: 'Maschinenstillstände',
      explain: 'Stillstände erklären',
      machineFilter: 'Maschine',
      machineFilterPlaceholder: 'Alle Maschinen',
      periodFrom: 'Von',
      periodTo: 'Bis',
      empty: 'Keine Stillstände in diesem Zeitraum.',
      loadError: 'Stillstände konnten nicht geladen werden.',
      endError: 'Stillstand konnte nicht beendet werden.',
      deleteError: 'Stillstand konnte nicht gelöscht werden.',
      deleteConfirm: 'Diesen Stillstand für {machine} löschen?',
      open: 'Offen',
      end: 'Beenden',
      columns: {
        machine: 'Maschine',
        startedAt: 'Beginn',
        endedAt: 'Ende',
        reason: 'Grund',
      },
    },
  },
  status: {
    down: 'Steht',
    running: 'Läuft',
    paused: 'Pausiert',
    idle: 'Leerlauf',
    downTooltip: 'Steht seit {time}: {reason}',
    noOrderTooltip: 'Kein Auftrag aktiv',
  },
}
