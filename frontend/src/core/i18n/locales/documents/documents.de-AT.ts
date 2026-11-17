// Messages for the document control every controlled document shares,
// merged into the de-AT locale.
export default {
  permissionMissing: 'Dafür brauchst du die Berechtigung {permission}.',
  reference: '{number} Rev. {revision}',
  status: {
    draft: 'Entwurf',
    released: 'Freigegeben',
    invalid: 'Ungültig',
    editing: 'In Bearbeitung',
  },
  revision: {
    draft: '{revision} (Entwurf)',
    tag: 'Rev. {revision}',
  },
  lock: {
    edit: 'Bearbeiten',
    discard: 'Verwerfen',
    editedBy: '{name} bearbeitet das gerade.',
    editedBySince: '{name} bearbeitet das seit {since}.',
    end: 'Bearbeitung beenden',
    endConfirm:
      '{name} bearbeitet das gerade. Wenn du die Bearbeitung beendest, hält niemand den Entwurf und die nicht gespeicherten Änderungen bleiben nur auf dem Gerät dieser Person.',
    takeOver: 'Übernehmen',
    takeOverConfirm:
      '{name} bearbeitet das gerade. Wenn du übernimmst, bleiben die nicht gespeicherten Änderungen nur auf dem Gerät dieser Person.',
    lost: '{name} hat die Bearbeitung übernommen. Deine nicht gespeicherten Änderungen bleiben auf diesem Gerät.',
    lostUnknown: 'Du bearbeitest das nicht mehr. Deine nicht gespeicherten Änderungen bleiben auf diesem Gerät.',
    idle: 'Die Bearbeitung wurde beendet, weil eine Weile nichts passiert ist. Deine nicht gespeicherten Änderungen bleiben auf diesem Gerät.',
    discardConfirm: 'Deine nicht gespeicherten Änderungen verwerfen?',
  },
  table: {
    revision: 'Revision',
    released: 'Freigegeben',
    editing: '{name} bearbeitet das gerade.',
  },
  menu: {
    open: 'Öffnen',
    openInNewTab: 'In neuem Tab öffnen',
    edit: 'Bearbeiten',
    history: 'Verlauf',
    print: 'Drucken',
    copyLink: 'Link kopieren',
    linkCopied: 'Link kopiert.',
    revise: 'Neue Revision',
    release: 'Freigeben',
    invalidate: 'Als ungültig markieren',
    delete: 'Löschen',
    unavailable: 'Das ist für dieses Dokument gerade nicht möglich.',
  },
  leave: {
    header: 'Nicht gespeicherte Änderungen',
    message:
      'Deine Änderungen sind nicht gespeichert. Wenn du die Seite verlässt, bleiben sie auf diesem Gerät und werden dir beim nächsten Öffnen angeboten.',
    accept: 'Verlassen',
  },
  draft: {
    header: 'Nicht gespeicherte Änderungen wiederherstellen?',
    message: 'Du hast das am {date} auf diesem Gerät geändert, ohne zu speichern.',
    stale: 'Es wurde seitdem erneut gespeichert. Beim Wiederherstellen ersetzen deine Änderungen die neuere Fassung.',
    staleSince: 'Es wurde am {date} erneut gespeichert. Beim Wiederherstellen ersetzen deine Änderungen diese Fassung.',
    blocked:
      'Es kann nicht mehr geändert werden, zum Beispiel weil es freigegeben wurde. Deine Änderungen können nur verworfen werden.',
    lockedBy:
      '{name} bearbeitet das gerade. Stelle deine Änderungen wieder her, sobald die Bearbeitung beendet ist; bis dahin bleiben sie auf diesem Gerät.',
    restore: 'Wiederherstellen',
    discard: 'Verwerfen',
    restored: 'Nicht gespeicherte Änderungen wiederhergestellt. Speichere, um sie zu behalten.',
  },
  invalid: {
    action: 'Als ungültig markieren',
    title: 'Revision {revision} als ungültig markieren',
    intro:
      'Die Revision bleibt freigegeben und dokumentiert, mit deiner Begründung als ungültig markiert. Berichte daraus tragen einen Warnhinweis. Korrigiere sie in einer neuen Revision.',
    submit: 'Als ungültig markieren',
    done: 'Als ungültig markiert.',
    notice: 'Von {name} am {date} als ungültig markiert: {reason}. Korrigiere das in einer neuen Revision.',
  },
  report: {
    invalid:
      'Diese Revision wurde von {name} am {date} als ungültig markiert: {reason}. Verwende sie nicht; sie wird in einer neuen Revision korrigiert.',
    superseded: 'Diese Revision wurde am {date} durch eine neuere ersetzt. Prüfe über den QR-Code die aktuelle Revision.',
    notLatest: 'Eine neuere Revision dieses Dokuments ist in Arbeit. Diese hier ist noch die gültige Revision.',
  },
  reason: {
    label: 'Begründung',
    required: 'Gib eine Begründung ein.',
  },
}
