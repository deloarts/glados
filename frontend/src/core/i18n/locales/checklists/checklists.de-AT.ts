// Messages for checklists, merged into the de-AT locale.
export default {
  type: 'Prüfliste',
  types: {
    hydraulics: 'Hydraulik',
    pneumatics: 'Pneumatik',
    robotics: 'Robotik',
  },
  savedTitle: 'Prüfliste {type}, {subject}',
  savedTitlePlain: 'Neue Prüfliste ({type})',
  title: 'Prüflisten',
  revisionLabel: 'Rev. {revision}',
  changedBadge: 'Geändert',
  sectionChanges: 'Geändert: {count}',
  owner: {
    personal: 'Persönlich',
    project: 'Projekt',
    product: 'Produkt',
  },
  status: {
    draft: 'Entwurf',
    done: 'Abgeschlossen',
    released: 'Freigegeben',
    superseded: 'Ersetzt',
    unsaved: 'Nicht gespeichert',
    releasedBy: 'Freigegeben von {name} am {date}',
    supersededOn: 'Am {date} durch eine neuere Revision ersetzt',
  },
  list: {
    number: 'Nummer',
    empty: 'Noch keine Prüflisten.',
    type: 'Art',
    title: 'Titel',
    owner: 'Gehört zu',
    result: 'Ergebnis',
    completion: '{percent} %',
    completionHeader: 'Fortschritt',
    findings: 'Befunde',
    designation: 'Maschine',
    status: 'Status',
    author: 'Erstellt von',
    changed: 'Geändert',
  },
  actions: {
    new: 'Neue Prüfliste',
    open: 'Öffnen',
    save: 'Speichern',
    revise: 'Neue Revision',
    compare: 'Vergleichen',
    history: 'Verlauf',
    print: 'Drucken',
    printBlocked: 'Speichere deine Änderungen vor dem Drucken.',
    owner: 'Zuordnung ändern',
    release: 'Freigeben',
    done: 'Fertig',
  },
  releaseBlocked: {
    incomplete: 'Jeder Punkt braucht eine Antwort.',
    remarks: 'Jeder Befund braucht eine Bemerkung.',
    ownRevision: 'Freigeben muss eine andere Person als die, die diese Revision erstellt hat.',
  },
  dialog: {
    createTitle: 'Neue Prüfliste',
    ownerTitle: 'Zuordnung ändern',
    create: 'Erstellen',
    owner: 'Gehört zu',
    ownerHint: {
      personal: 'Eine persönliche Prüfliste siehst nur du (und wer Prüflisten verwalten darf).',
      project: 'Die Prüflisten eines Projekts sieht jede Person im Reiter Prüflisten des Projekts.',
      product: 'Die Prüflisten eines Produkts sieht jede Person im Reiter Prüflisten des Produkts.',
    },
    ownerRequired: 'Wähle aus, wozu die Prüfliste gehört.',
  },
  revise: {
    title: 'Neue Revision',
    intro:
      'Die neue Revision übernimmt die Antworten und Bemerkungen von Revision {revision}. Revision {revision} bleibt unverändert erhalten.',
    reason: 'Grund für die neue Revision',
    reasonRequired: 'Gib einen Grund an.',
    submit: 'Revision beginnen',
  },
  history: {
    title: 'Revisionen',
    revision: 'Revision',
    reason: 'Grund',
    firstRevision: 'Erste Revision',
    compareWith: 'Mit dieser Revision vergleichen',
  },
  compare: {
    title: 'Revisionen vergleichen',
    back: 'Zurück zur Prüfliste',
    from: 'Vergleichen von',
    to: 'Vergleichen mit',
    nothing: 'Das ist die erste Revision, es gibt nichts zum Vergleichen.',
    findings: 'Befunde: {count}',
  },
  diff: {
    none: 'Die beiden Revisionen unterscheiden sich nicht.',
    header: 'Prüflistendaten',
    field: 'Feld',
    unanswered: 'Unbeantwortet',
    removedItems: 'Punkte, die es in der Prüfliste nicht mehr gibt',
    fields: {
      ownerNumber: 'Nummer',
      ownerCustomer: 'Kunde',
      ownerProduct: 'Produkt',
      ownerManager: 'Zuständige Person',
      designation: 'Bezeichnung',
      machineType: 'Typ',
      placingOnMarket: 'Geplantes Inverkehrbringen',
      installationSite: 'Montageort',
      installationLocation: 'Montagestelle',
      legalBasis: 'Rechtsgrundlage',
      assessedBy: 'Beurteilt von',
      assessedOn: 'Beurteilt am',
      reason: 'Begründung, falls nicht bestanden',
      notes: 'Anmerkungen',
    },
  },
  confirm: {
    release: {
      header: 'Prüfliste freigeben',
      message:
        'Mit der Freigabe zeichnest du die Prüfliste ab. Danach kann sie nicht mehr geändert werden, Änderungen gehen über eine neue Revision.',
      accept: 'Freigeben',
      saveFirst: 'Deine ungespeicherten Änderungen werden vorher gespeichert.',
    },
    delete: {
      header: 'Prüfliste löschen',
      message:
        'Diese Revision wird endgültig gelöscht. Die Revision davor, falls es eine gibt, ist dann wieder die neueste.',
      accept: 'Löschen',
    },
  },
  toasts: {
    saved: 'Prüfliste gespeichert.',
    release: 'Prüfliste freigegeben.',
    delete: 'Prüfliste gelöscht.',
    revised: 'Revision {revision} begonnen.',
  },
  errors: {
    unknown: 'Etwas ist schiefgelaufen. Bitte versuch es noch einmal.',
    notFound: 'Die Prüfliste wurde nicht gefunden, oder du darfst sie nicht öffnen.',
    loadList: 'Die Prüflisten konnten nicht geladen werden.',
    unknownType: 'Diese Prüfliste hat eine Art, die diese Glados-Version nicht kennt.',
  },
  notices: {
    dropped:
      'Die Prüflistenart hat sich seit dem Speichern geändert. Antworten und Bemerkungen zu Punkten, die es nicht mehr gibt, fallen beim Speichern weg ({count}).',
    notLatest: 'Das ist nicht die neueste Revision, Revision {revision} ist neuer.',
    openLatest: 'Neueste Revision öffnen',
    changesSince:
      'Seit Revision {revision} geänderte Punkte: {count}. Die geänderten Punkte sind markiert, und der Filter „Geändert“ zeigt nur diese.',
  },
  info: {
    typeTitle: 'Prüfliste {type}',
    created: 'Erstellt von {name} am {date}',
    changed: 'Geändert am {date}',
  },
  report: {
    revision: 'Revision',
    owner: 'Gehört zu',
    createdBy: 'Erstellt von',
    status: 'Status',
    draft: 'Entwurf, nicht freigegeben',
    number: 'Nr.',
    position: 'Punkt',
    requirement: 'Anforderung',
    answer: 'Antwort',
    hintsOption: 'Erläuterungen zu den Punkten anfügen',
  },
  header: {
    title: 'Prüflistendaten',
    owner: {
      project: 'Projekt',
      product: 'Produkt',
      customer: 'Kunde',
      manager: 'Zuständige Person',
      personal: 'Eine persönliche Prüfliste, sie gehört zu keinem Projekt und keinem Produkt.',
    },
    designation: 'Bezeichnung',
    machineType: 'Typ',
    placingOnMarket: 'Geplantes Inverkehrbringen',
    installationSite: 'Montageort',
    installationLocation: 'Montagestelle',
    legalBasis: 'Rechtsgrundlage',
    machineDataHint: 'Die Maschinendaten kommen vom Produkt. Du änderst sie auf der Produktseite.',
    legalBasisOutdated:
      'Die Richtlinie 2006/42/EG gilt nicht mehr für Maschinen, die ab 2027-01-20 in Verkehr gebracht werden. Es gilt die Verordnung (EU) 2023/1230.',
    confirmationTitle: 'Bestätigung',
    confirmation:
      'Die Beurteilung wurde von allen unten angeführten Beteiligten bestätigt und auf Richtigkeit geprüft. Alle zur Vermeidung von Gefahren angeführten Punkte werden zur Erhöhung der Sicherheit am Arbeitsplatz eingehalten.',
    assessedBy: 'Beurteilt von',
    assessedOn: 'Beurteilt am',
    checkedBy: 'Geprüft und freigegeben von',
    notReleased: 'Noch nicht freigegeben',
    reason: 'Begründung, falls nicht bestanden',
    notes: 'Anmerkungen',
  },
  legalBases: {
    directive: 'Richtlinie 2006/42/EG',
    regulation: 'Verordnung (EU) 2023/1230',
  },
  answers: {
    na: 'Entfällt',
    yes: 'Ja',
    no: 'Nein',
    defect: 'Mangel',
  },
  answerTitles: {
    na: 'Trifft nicht zu',
    yes: 'Erfüllt',
    no: 'Nicht erfüllt',
    defect: 'Mangel festgestellt',
  },
  answerGroup: 'Antwort zu {position}',
  verdicts: {
    passed: 'Bestanden',
    open: 'Offen',
    failed: 'Nicht bestanden',
  },
  verdictHints: {
    passed: 'Alle Punkte sind beantwortet und keiner mit „Nein“ oder „Mangel“.',
    open: 'Es sind noch Punkte unbeantwortet, bisher ohne Befund.',
    failed: 'Mindestens ein Punkt ist mit „Nein“ oder „Mangel“ beantwortet.',
  },
  filters: {
    label: 'Anzeigen',
    all: 'Alle Punkte',
    unanswered: 'Unbeantwortet',
    problems: 'Befunde',
    changes: 'Geändert',
    any: 'Beliebig',
    anyone: 'Beliebig',
    me: 'Ich',
    status: {
      released: 'Freigegeben',
      unreleased: 'Nicht freigegeben',
    },
    search: 'Titel durchsuchen',
  },
  views: {
    sortByItems: {
      changedDesc: 'Geändert (neueste)',
      changedAsc: 'Geändert (älteste)',
      createdDesc: 'Erstellt (neueste)',
      createdAsc: 'Erstellt (älteste)',
      numberDesc: 'Nummer (neueste zuerst)',
      numberAsc: 'Nummer (älteste zuerst)',
      titleAsc: 'Titel (A → Z)',
      titleDesc: 'Titel (Z → A)',
      typeAsc: 'Art (A → Z)',
      verdictAsc: 'Ergebnis (A → Z)',
      releasedDesc: 'Freigegeben (neueste)',
    },
    groupByItems: {
      type: 'Art',
      owner: 'Gehört zu',
      verdict: 'Ergebnis',
      status: 'Status',
    },
  },
  expandAll: 'Alle aufklappen',
  collapseAll: 'Alle zuklappen',
  sectionProgress: '{answered} von {total} beantwortet',
  sectionProblems: 'Befunde: {count}',
  remark: 'Bemerkung',
  addRemark: 'Bemerkung hinzufügen',
  removeRemark: 'Bemerkung ausblenden',
  noMatches: 'Keine Punkte entsprechen dem Filter.',
  see: 'Siehe {items}',
  itemReference: '{section}, Pos. {item}',
  methodsLabel: 'Validierung',
  methodsLegend: 'Validierungsverfahren',
  methods: {
    A: 'Sichtprüfung',
    B: 'Praktische Prüfung',
    C: 'Messung',
    D: 'Beobachtung während des Betriebs',
    E: 'Prüfung anwendungsspezifischer Schaltpläne und Pläne',
    F: 'Prüfung der sicherheitsbezogenen Software',
    G: 'Überprüfung der aufgabenbasierten Risikobeurteilung',
    H: 'Prüfung der Anordnungszeichnungen und Dokumente',
    I: 'Überprüfung von Spezifikationen und Benutzerinformationen',
  },
  references: {
    introduction: 'Einleitung',
    table: 'Tabelle {table}',
    article: 'Art. {article}',
    annex: 'Anhang {annex}',
    annexPoint: 'Anhang {annex} {point}',
    machinery: 'Anhang {annex} {point}',
  },
  documents: {
    iso4413: 'ISO 4413:2010',
    iso4414: 'ISO 4414:2010',
    iso12100: 'ISO 12100:2010',
    iso13850: 'ISO 13850:2015',
    iso1219_1: 'ISO 1219-1',
    iso1219_2: 'ISO 1219-2',
    iec81346_2: 'IEC 81346-2',
    iec60204_1: 'IEC 60204-1',
    ped: 'Richtlinie 2014/68/EU',
    spvd: 'Richtlinie 2014/29/EU',
    en14359: 'EN 14359',
    en286_1: 'EN 286-1',
    en856: 'EN 856',
    iso13732_1: 'ISO 13732-1',
    ifaValves: 'IFA-Prüfgrundsätze für Ventile',
    iso10218_1: 'ISO 10218-1',
    iso10218_2: 'ISO 10218-2',
    iso13849_1: 'ISO 13849-1',
    iec62061: 'IEC 62061',
    iso13854: 'ISO 13854',
    iso13855: 'ISO 13855',
    iso13857: 'ISO 13857',
    iso14119: 'ISO 14119',
    iso14120: 'ISO 14120',
    iso14122: 'ISO 14122',
    iso11161: 'ISO 11161',
    iec61496_1: 'IEC 61496-1',
    isoTs15066: 'ISO/TS 15066',
  },
  summaryCard: {
    title: 'Ergebnis',
    completion: '{percent} % beantwortet',
    open: 'Offen',
    problems: 'Befunde',
    noProblems: 'Bisher keine Befunde.',
  },
  hydraulics: {
    parts: {
      documentation: 'Prüfung der Dokumentation',
      machine: 'Prüfung an der gebauten Maschine',
      instructions: 'Betriebsanleitung',
    },
    sections: {
      assessment: 'Beurteilung der hydraulischen Ausrüstung',
      circuit: 'Schaltpläne',
      sizing: 'Dimensionierung',
      cleanliness: 'Reinhaltung der Druckflüssigkeit',
      emergencyStop: 'Not-Halt',
      accumulatorDesign: 'Hydrospeicher',
      servoValves: 'Steuerungen mit Servo- oder Proportionalventilen',
      reservoir: 'Flüssigkeitsbehälter',
      marking: 'Kennzeichnung',
      assembly: 'Aufbau',
      piping: 'Rohr- und Schlauchleitungen',
      bleeding: 'Entlüftung und Messanschlüsse',
      maintenance: 'Instandhaltungsgerechte Gestaltung',
      electrical: 'Elektrische Ausrüstung (Prüfung durch eine Elektrofachkraft)',
      energySupply: 'Energieversorgung',
      fluctuations: 'Energieschwankungen (Druck und Volumenstrom)',
      actuators: 'Stellteile',
      indicators: 'Mess- und Anzeigeeinrichtungen',
      adjustments: 'Verstelleinrichtungen an sicherheitsrelevanten Bauteilen',
      cylinders: 'Hubendanschläge und Schutz der Kolbenstange',
      temperature: 'Oberflächentemperatur und Brandgefahr',
      rescue: 'Befreien von Personen',
      accumulatorCheck: 'Hydrospeicher',
      tests: 'Prüfungen',
      manual: 'Hydraulischer Teil der Betriebsanleitung',
    },
    items: {
      assessment: {
        documents:
          'Liegen folgende Unterlagen vor: Schaltpläne, Stücklisten, Datenblätter aller Bauteile, Betriebsanleitung, Sicherheitsdatenblätter der Druckflüssigkeit und weitere erforderliche Unterlagen?',
        circuitFunctions: 'Sind die hydraulischen Bauteile geeignet, die Funktionen dieser Schaltung zu erfüllen?',
        typeCStandard: 'Wurde geprüft, ob für die Maschine eine C-Norm gilt? Titel in der Bemerkung festhalten.',
        typeCRequirements:
          'Falls eine C-Norm gilt: Sind deren Anforderungen an die hydraulische Ausrüstung, die über ISO 4413 hinausgehen, berücksichtigt?',
        riskAssessment:
          'Wurde die Risikobeurteilung der Maschine nach ISO 12100 auf Gefährdungen ausgewertet, aus denen sich Sicherheitsanforderungen an die hydraulische Ausrüstung ergeben, und sind diese Anforderungen berücksichtigt?',
      },
      circuit: {
        iso1219: 'Sind die Schaltpläne nach ISO 1219-2 dargestellt?',
        layout: 'Ist die Leitungsführung einfach gezeichnet, sodass alle Schaltwege verfolgt werden können, und möglichst kreuzungsfrei?',
        symbols: 'Sind Schaltzeichen nach ISO 1219-2 verwendet und folgen die Betriebsmittelkennzeichen IEC 81346-2?',
        restPosition: 'Sind die Symbole unbetätigt im energielosen Zustand (Ruhestellung) dargestellt?',
        assemblies: 'Sind Baugruppen durch Umrahmungslinien abgegrenzt?',
        crossDesignations:
          'Stimmen die Kennzeichnungen der relevanten Betriebsmittel in den hydraulischen, elektrischen und elektronischen Schaltplänen überein?',
        portMarking: 'Sind alle Leitungsanschlüsse gekennzeichnet?',
        sheetTransitions: 'Sind die Übergänge der Leitungen zwischen den einzelnen Schaltplänen gekennzeichnet?',
        partsList: 'Ist auf dem Schaltplan eine Stückliste dargestellt?',
        supplementary: 'Sind bei Bedarf ergänzende Unterlagen wie Funktionsdiagramm, Lageplan oder Funktionsplan vorhanden?',
        unexpectedStart:
          'Kann das System zur Verhinderung eines unerwarteten Anlaufs vollständig von den Energiequellen getrennt und die gespeicherte Energie abgebaut werden?',
        circuitFunction: 'Erfüllt die im Schaltplan dargestellte Schaltung alle geforderten Funktionen?',
        isolation:
          'Ist die vollständige Trennung von der Energiequelle und der Druckabbau der Druckflüssigkeit sichergestellt, durch Trennen der elektrischen Energieversorgung (Hauptschalter) und durch mechanische Sicherung, etwa in Sperrstellung abgeschlossene Sperrventile, bei abgebautem Druck in der Anlage?',
        safePositionValves:
          'Sind die Ventile ermittelt, die beim Versagen der Steuerung eine bestimmte Sicherheitsstellung einnehmen oder beibehalten müssen? In der Bemerkung auflisten.',
        safePositionMeans: 'Werden diese Ventile durch Federvorspannung oder Arretierung (Raste) in dieser Stellung gehalten?',
        overpressure:
          'Sind alle Teile der Anlage gegen unzulässig hohe Drücke geschützt, auch infolge Druckübersetzung, etwa durch Druckbegrenzungsventile oder Druckregelung an der Pumpe (Letztere nur in den Grenzen von ISO 4413, 5.2.2.2)?',
        pressureLoss:
          'Falls Druckverlust oder Leckagen zu einer Gefährdung führen können: Sind Maßnahmen dagegen getroffen, etwa entsperrbare Rückschlagventile oder mechanische Sicherungen?',
        fluctuations:
          'Falls Energieschwankungen (Energieabfall, kritisches Absinken des Drucks) zu einer Gefährdung führen können: Sind die zulässigen Grenzen festgelegt, etwa im Schaltplan und in der Betriebsanleitung, und werden Schwankungen angezeigt, der Druck etwa durch Manometer oder Warnleuchte, der Volumenstrom durch Durchflussmessgerät oder Warnleuchte?',
        switching: 'Ist sichergestellt, dass das Ein- und Ausschalten der Energieversorgung zu keiner Gefährdung führt?',
        failureReturn:
          'Ist sichergestellt, dass Ausfall oder Wiederkehr der Energieversorgung zu keiner Gefährdung führt, etwa durch Überwachung des Drucks?',
        pressureSurges: 'Ist die Anlage so ausgelegt, dass Druckstöße und Druckverstärkungen zu keiner Gefährdung führen?',
        surgeConfirmation:
          'Liegt eine Bestätigung des Herstellers der Anlage oder Maschine über die gewählten Maßnahmen gegen Druckstöße und Druckverstärkungen vor?',
        testPoints: 'Sind die erforderlichen Messanschlüsse dargestellt?',
        bleedPoints: 'Sind die erforderlichen Entlüftungsanschlüsse und Ablassstellen dargestellt?',
        sequenceHazard:
          'Falls die Anlage Ablaufsteuerungen hat: Ist sichergestellt, dass eine Fehlfunktion in der Schrittfolge einer Druck- oder Zeitsteuerung zu keiner Gefährdung führt?',
        sequencePosition: 'Wo eine solche Fehlfunktion zu einer Gefährdung führen kann: Werden stattdessen wegabhängige Steuerungen verwendet?',
        linkedComponents:
          'Falls das Versagen verketteter Bauteile, automatisch oder von Hand betätigt, zu einer Gefährdung führen kann: Sind Verriegelungen oder andere Sicherheitsmaßnahmen vorgesehen?',
        interlockInterruption:
          'Unterbrechen die Verriegelungen alle Arbeitsschritte, ohne dass die Unterbrechung selbst eine Gefährdung nach sich zieht?',
        externalForces:
          'Wird ein unzulässig hoher Druck infolge äußerer Kräfte auf die Antriebe verhindert, etwa durch zusätzliche Druckbegrenzungsventile oder mechanische Maßnahmen?',
        drainBack:
          'Wird bei abgeschalteter Anlage das Abfließen der Druckflüssigkeit verhindert, wo dadurch eine Gefährdung entstünde, etwa durch Vorspannventile?',
      },
      sizing: {
        designData:
          'Sind die der Auslegung zugrunde gelegten Daten dokumentiert: maximaler Betriebsdruck, Drücke in Teilsystemen, Steuerdruck, Betriebstemperaturbereich, Reinheitsgrad und Druckflüssigkeit (Normbezeichnung)? Werte in der Bemerkung festhalten.',
        componentRatings:
          'Sind alle Teile der Anlage so ausgewählt, dass sie den zu erwartenden Betriebsdrücken und -temperaturen standhalten und für die vorgesehene Druckflüssigkeit geeignet sind, oder liegt dafür eine Bestätigung des Herstellers vor?',
        cylinderSizing:
          'Falls die Anlage Zylinder enthält: Sind diese für Druck, Biegung und Knickung ausreichend dimensioniert, nachgewiesen durch Berechnung oder Datenblatt?',
        cylinderFasteners:
          'Sind die Befestigungsschrauben der Zylinder und ihrer Anbauteile (etwa Fußplatten) ausreichend dimensioniert und so weit wie möglich frei von Scherkräften?',
        valveMisassembly:
          'Ist der falsche Einbau von Ventilen verhindert, etwa durch das Lochbild, einen Orientierungsstift oder Hinweise im Schaltplan und in der Betriebsanleitung (etwa bei 2-Wege-Einbauventilen)?',
      },
      cleanliness: {
        devices: 'Sind Einrichtungen zur Reinhaltung der Druckflüssigkeit vorhanden, etwa Filter, Partikelzähler oder Abscheider?',
        filterTypes:
          'Sind die Filter der Anlage ermittelt (Belüftungsfilter, Druckfilter, Rücklauf-, Saug- oder Nebenstromfilter)? In der Bemerkung auflisten.',
        breatherFineness:
          'Belüftungsfilter (nur bei offenen Systemen): Ist die Filterfeinheit mindestens so fein wie die von den Bauteilherstellern auf der Flüssigkeitsseite geforderte Filterung?',
        breatherConditions: 'Belüftungsfilter: Entspricht die Ausführung den Umgebungs- und Einsatzbedingungen?',
        breatherFlow: 'Belüftungsfilter: Ist der zulässige Volumenstrom des Filters größer als der Gesamtvolumenstrom zum und vom Tank?',
        pressureFilter:
          'Druckfilter: Entspricht die Filterung den Anforderungen der Bauteilhersteller, ist der Nenndruck ausreichend und ist der Filter für Volumenstrom, Druckflüssigkeit und Betriebstemperaturbereich geeignet?',
        pressureFilterIndicator: 'Druckfilter: Ist eine Verschmutzungsanzeige vorhanden?',
        returnFilter:
          'Rücklauf- und sonstige Filter: Entspricht die Filterung den Anforderungen der Bauteilhersteller, ist der Nenndruck ausreichend und ist der Filter für Volumenstrom, Druckflüssigkeit und Betriebstemperaturbereich geeignet?',
        returnFilterIndicator: 'Rücklauf- und sonstige Filter: Ist eine Verschmutzungsanzeige vorhanden?',
        returnBackPressure:
          'Rücklauffilter: Falls erhöhte Rücklaufdrücke zu einer Gefährdung führen können, sind Maßnahmen dagegen getroffen, etwa eine Verschmutzungsanzeige mit Bypass oder eine elektrische Anzeige mit Abschaltung oder Bypass?',
      },
      emergencyStop: {
        equipped: 'Ist die Maschine mit einer Not-Halt-Funktion ausgerüstet?',
        devices:
          'Wird der Not-Halt durch eine bewusste Handbetätigung geeigneter Einrichtungen ausgelöst, etwa Not-Halt-Taster, Reißleine, Fußschalter ohne Schutzhaube oder den Hauptschalter, wo dieser für Not-Halt ausgelegt ist? Einrichtungen in der Bemerkung festhalten.',
        effect:
          'Hat das Betätigen des Not-Halts die vorgesehene Wirkung, etwa Abschalten des Pumpenantriebs, Absperren des Volumenstroms zu den Antrieben, Entlasten oder Absperren der Hydrospeicher, druckloser Umlauf des Pumpenstroms, Spanndruckerhaltung oder Freifahren? Wirkungen in der Bemerkung festhalten.',
        valves:
          'Sind die im Not-Halt-Kreis eingesetzten Ventile geeignet, diese Wirkungen zu erreichen, etwa ein 4/3-Wegeventil mit gesperrter Mittelstellung zum Anhalten einer Bewegung oder Ventile, die im stromlosen Zustand ihre Sicherheitsstellung einnehmen?',
        allModes: 'Wirkt der Not-Halt in allen Betriebsarten, etwa Automatik, Halbautomatik und Einrichten?',
        servoSuitable: 'Erfüllen auch Servo- oder Proportionalventile im Not-Halt-Kreis diese Anforderungen?',
        manualValves:
          'Falls nicht: Können zusätzliche handbetätigte Ventile die Antriebe im Gefahrenfall in eine definierte sichere Stellung bringen?',
      },
      accumulatorDesign: {
        data: 'Falls die Anlage Hydrospeicher enthält: Sind Volumen V in Litern und Druckliterprodukt p × V in bar × Liter dokumentiert? Werte in der Bemerkung festhalten.',
        directive:
          'Wurde festgestellt, ob der Hydrospeicher unter die Richtlinie 2014/68/EU (Druckgeräte) oder die Richtlinie 2014/29/EU (einfache Druckbehälter) fällt?',
        category:
          'Bei Hydrospeichern nach Richtlinie 2014/68/EU: Ist die Kategorie für die Konformitätsbewertung ermittelt? In der Bemerkung festhalten.',
        certificates:
          'Liegen die für den Hydrospeicher erforderlichen Bescheinigungen vor, etwa EU-Konformitätserklärung und EU-Baumusterprüfbescheinigung?',
        inspectionBeforeUse:
          'Liegt eine Bescheinigung über die Prüfung vor der ersten Inbetriebnahme vor, durchgeführt von einer zugelassenen Stelle oder einer fachkundigen Person nach den nationalen Vorschriften?',
        safetyDevices:
          'Sind folgende Sicherheitseinrichtungen vorhanden und im Schaltplan dargestellt: Manometer, Sicherheitsventil, Absperrventil und Druckentlastungsventil?',
        switchedOff:
          'Wird der Hydrospeicher bei abgeschalteter Anlage flüssigkeitsseitig automatisch entlastet oder flüssigkeitsseitig sicher abgesperrt?',
        holdPressure: 'Ist festgelegt, ob der Druck nach dem Abschalten der Anlage erhalten bleiben muss?',
        gasRelief: 'Ist, wo erforderlich, eine Druckbegrenzung auf der Gasseite vorhanden?',
      },
      servoValves: {
        controlHazard:
          'Falls Antriebe mit Servo- oder Proportionalventilen gesteuert werden, bei denen Fehlfunktion oder Fehlansteuerung eine Gefährdung verursachen kann: Sind Maßnahmen vorgesehen, um die Kontrolle über diese Antriebe beizubehalten oder wiederherzustellen?',
        unintendedMotion:
          'Falls Geschwindigkeiten von Antrieben mit Servo- oder Proportionalventilen gesteuert werden und eine unbeabsichtigte Bewegung eine Gefährdung verursachen kann: Sind Maßnahmen vorgesehen, um die Antriebe in einer sicheren Lage zu halten oder in eine sichere Lage zu bewegen?',
        mainFilter:
          'Ist in der Zuleitung zu allen Servo- oder Proportionalventilen, bei denen eine durch Verschmutzung verursachte Fehlfunktion eine Gefährdung herbeiführen kann, ein Hauptstromfilter eingebaut?',
        filterNoBypass: 'Ist dieser Filter ohne Bypass ausgeführt und mit einer Verschmutzungsanzeige versehen?',
        filterCollapse: 'Liegt die Differenzdruckfestigkeit des Filterelements über dem maximalen Betriebsdruck der Anlage?',
        filterBlocking: 'Ist eine Gefährdung durch einen blockierten Filter mit geeigneten Maßnahmen verhindert, etwa durch ein Druckbegrenzungsventil?',
      },
      reservoir: {
        capacity:
          'Ist der Flüssigkeitsbehälter so ausgelegt, dass er die gesamte Flüssigkeit aufnimmt, die im Betrieb und bei der Instandhaltung zurückfließen kann, der Flüssigkeitsstand in allen Arbeitszyklen auf sicherem Niveau bleibt und im Normalbetrieb ausreichend Wärme abgeführt wird, falls kein Wärmetauscher eingebaut ist?',
        pressurised:
          'Bei druckbeaufschlagten Flüssigkeitsbehältern: Sind die besonderen Anforderungen erfüllt, insbesondere ein ausreichend dimensioniertes Druckbegrenzungsventil auf der Luftseite?',
        accessories:
          'Ist der Tank ausgerüstet mit einer Füllstandsanzeige mit Markierung für maximale und minimale Füllmenge, einem dicht schließenden Deckel auf der Einfüllöffnung und einem Belüftungsfilter?',
      },
      marking: {
        positionMarks:
          'Sind die Bauteile an oder neben dem Bauteil mit ihrer Positionsnummer oder ihrem Kennbuchstaben aus dem Schaltplan gekennzeichnet?',
        componentData:
          'Sind die funktionalen Bauteile dauerhaft und gut leserlich gekennzeichnet mit Name und Kurzanschrift des Herstellers oder Lieferanten, Produktidentifizierung und Bemessungsdruck (mindestens der maximale Betriebsdruck der Anlage), mit Symbolen nach ISO 1219-1 und korrekt gekennzeichneten Anschlüssen?',
        stackOrder: 'Bei Höhenverkettungen: Ist die Reihenfolge der Elemente neben der Verkettung angegeben, nicht aber auf den Verkettungselementen?',
        accumulatorData:
          'Sind Hydrospeicher zusätzlich gekennzeichnet mit Herstelldatum (Monat und Jahr), Gasart und Vorfülldruck, Seriennummer, zulässigem Überdruck, Volumen in Litern, zulässigem Temperaturbereich und, falls zutreffend, CE-Kennzeichnung?',
        valveOperators:
          'Bei nichtelektrischen Ventilbetätigungen: Stimmen die Kennzeichnung der Betätigung und ihrer Funktionen mit dem Schaltplan überein?',
        testDrainPoints: 'Sind Mess- und Ablassstellen gemäß Schaltplan gekennzeichnet und leicht zugänglich?',
        accumulatorWarning:
          'Ist an einer Anlage mit Hydrospeicher an gut sichtbarer Stelle ein Warnschild angebracht mit der Aufschrift: „Achtung, Anlage enthält Hydrospeicher. Vor Beginn von Instandhaltungsarbeiten muss die Anlage druckentlastet werden.“?',
        accumulatorMaintenanceNote:
          'Bei Hydrospeichern, deren Flüssigkeitsseite bei abgeschalteter Anlage unter Druck bleibt: Ist auf oder nahe dem Hydrospeicher gut sichtbar ein Hinweis zur sicheren Instandhaltung angebracht?',
        interchangeableLines: 'Sind Leitungsenden, die vertauscht werden könnten, gemäß Schaltplan gekennzeichnet?',
      },
      assembly: {
        conformsToDiagram: 'Ist das Hydrauliksystem gemäß Schaltplan aufgebaut?',
        mountingPosition: 'Entspricht die Einbaulage der Bauteile den Angaben ihrer Hersteller?',
        cylinderFasteners:
          'Sind alle Befestigungsschrauben der Zylinder und ihrer Anbauteile (etwa Fußplatten) ausreichend dimensioniert und frei von Scherkräften?',
        fastenersSecured: 'Sind sie so befestigt, dass sie einem Lösen durch Stöße und Schwingungen widerstehen?',
        mechanicalValves:
          'Sind mechanisch betätigte Ventile so eingebaut, dass ihre Betätigungseinrichtung, etwa ein Nocken, sie nicht beschädigen kann?',
        intensification: 'Sind Maßnahmen gegen unbeabsichtigte Druckübersetzung vorhanden und wirksam?',
        returnPressure:
          'Sind Gefährdungen durch erhöhten Rücklaufdruck und durch die abdichtende Funktion von Schnelltrennkupplungen verhindert?',
      },
      piping: {
        pipeSupport:
          'Sind Rohrleitungen ausreichend befestigt, mit Rohrhalterungen an beiden Enden und an Punkten entlang ihrer ganzen Länge, und sind die empfohlenen Abstände zwischen Haltern, Bögen und Verbindungen eingehalten?',
        supportDamage: 'Ist die Befestigung so ausgeführt, dass die Rohrleitungen nicht beschädigt werden? Befestigen durch Schweißen ist nicht zulässig.',
        componentsOnPipes:
          'Falls Rohrleitungen zur Befestigung von Bauteilen dienen: Ist sichergestellt, dass die Masse der Bauteile keine Stöße oder Schwingungen verursacht, die die Rohrleitungen unzulässig belasten?',
        notAStep: 'Sind Rohr- und Schlauchleitungen so verlegt, dass sie nicht als Stufe oder Leiter verwendet werden können?',
        wrongConnection:
          'Sind Rohr- und Schlauchleitungen einschließlich ihrer Anschlüsse so angeordnet oder ausgeführt, dass eine falsche Verbindung, die zu einer Gefährdung führt, nicht hergestellt werden kann, etwa durch verschiedene Gewinde oder die Formgebung der Leitung?',
        wrongConnectionMarking: 'Falls nicht: Sind sie eindeutig und dauerhaft gemäß Schaltplan gekennzeichnet?',
        protectedRouting:
          'Sind Rohr- und Schlauchleitungen so angeordnet, dass sie gegen alle vorhersehbaren Beschädigungen geschützt sind und den Zugang für Einstellung, Reparatur und Austausch von Bauteilen oder den Betrieb der Anlage nicht behindern?',
        hoseAssemblyMarking:
          'Sind Schlauchleitungen, etwa auf der Pressfassung, gekennzeichnet mit Name oder Kurzzeichen des Herstellers, maximal zulässigem Betriebsdruck in bar (etwa PN 350) sowie Jahr und Monat der Herstellung?',
        hoseMarking:
          'Ist der Schlauch gekennzeichnet mit Name oder Kurzzeichen des Herstellers, Norm und Typ (etwa EN 856 4SP), Nenngröße sowie Quartal und Jahr der Herstellung?',
        notReused:
          'Sind die Schlauchleitungen, soweit erkennbar, nicht aus Schläuchen hergestellt, die bereits Teil einer anderen Schlauchleitung waren?',
        serviceLife: 'Haben Schlauchleitungen und Schläuche die vom Hersteller empfohlene Lager- und Verwendungsdauer nicht überschritten?',
        hoseInstallation:
          'Sind die Schlauchleitungen so eingebaut, dass sie die nötige Länge haben, um schädigende Belastungen wie Knicken oder Zug im Betrieb zu vermeiden, der Mindestbiegeradius eingehalten ist, ein Verdrehen bei Einbau und Betrieb auf ein Minimum beschränkt ist, keine Scheuerstellen vorhanden sind, die Kennzeichnungen lesbar bleiben (nicht überlackiert) und Beschichtungen mit dem Schlauchmaterial verträglich sind (Herstellernachweis)?',
        whipProtection:
          'Wo das Versagen einer Schlauchleitung (Ausreißen, Platzen) eine Gefährdung wie Aufpeitschen oder Austritt von Druckflüssigkeit verursachen würde, etwa an Bedienplätzen oder Verkehrswegen: Sind geeignete Schutzmaßnahmen vorhanden, etwa Befestigung, Fangvorrichtung oder Abschirmung?',
        quickCouplings: 'Wo Schnellkupplungen verwendet werden: Dichten Auslass- und Einlassöffnung beim Entkuppeln selbsttätig ab?',
      },
      bleeding: {
        bleedPoints: 'Wo Entlüften erforderlich ist: Sind Entlüftungsmöglichkeiten vorhanden?',
        bleedMarked: 'Sind sie deutlich und unverwechselbar gekennzeichnet?',
        bleedAccess: 'Wirken sie selbsttätig oder sind sie leicht und gefahrlos zugänglich?',
        bleedSafe: 'Kann die eingeschlossene Luft ohne Gefährdung von Personen entweichen?',
        singleActing:
          'Falls einfach wirkende Zylinder vorhanden sind: Sind deren Luftauslassöffnungen so ausgelegt oder angeordnet, dass die eingeschlossene Luft ohne Gefährdung von Personen entweicht?',
        testPoints: 'Sind die erforderlichen Messanschlüsse vorhanden?',
        testPointsAccess: 'Sind sie leicht zugänglich?',
        testPointsMarked: 'Sind sie deutlich und unverwechselbar gekennzeichnet?',
      },
      maintenance: {
        access:
          'Sind die Bauteile so angeordnet, dass sie für Instandhaltungsarbeiten leicht und gefahrlos zugänglich sind, einschließlich leichten und gefahrlosen Entleerens und Befüllens des Flüssigkeitsbehälters?',
        removal:
          'Sind Maßnahmen getroffen oder die Bauteile so angeordnet und verbunden, dass ihr Ausbau den Flüssigkeitsverlust gering hält, keine Entleerung des Behälters erfordert und keinen unnötigen Abbau angrenzender Bauteile nötig macht?',
      },
      electrical: {
        solenoidVoltage: 'Sind die Elektromagnete der Hydraulikventile für zuverlässigen Betrieb innerhalb der Toleranz der Nennspannung ausgelegt?',
        solenoidProtection: 'Haben die Elektromagnete die erforderliche Schutzart (IP-Code) gegen eindringende Flüssigkeit und Staub?',
        terminalBoxes:
          'Haben die Klemmenkästen eine geeignete Schutzart, unverlierbare Befestigungsmittel für die Abdeckung und Kabeleinführungen mit Zugentlastung?',
        coversSecured:
          'Sind die Abdeckungen von Klemmenleisten und Klemmenkästen an elektrisch betätigten Ventilen gegen Verlieren gesichert, etwa mit einer Kette?',
      },
      energySupply: {
        switching: 'Führt das Einschalten, Ausschalten oder die Wiederkehr der Energieversorgung zu keiner Gefährdung?',
      },
      fluctuations: {
        indicators: 'Sind die für Energieschwankungen erforderlichen Anzeige- und Warneinrichtungen vorhanden und geeignet?',
      },
      actuators: {
        design:
          'Sind die Stellteile deutlich sichtbar angeordnet, eindeutig und dauerhaft gekennzeichnet, in ihrer Bewegungsrichtung mit der Steuerwirkung übereinstimmend, gegen unbeabsichtigtes Betätigen ausgelegt oder geschützt sowie ergonomisch gestaltet und angeordnet?',
        multiFunction: 'Wo ein Stellteil mehrere verschiedene Wirkungen hat: Wird die jeweilige Steuerwirkung eindeutig angezeigt?',
      },
      indicators: {
        visible: 'Wo Messeinrichtungen vorhanden sind: Sind deren Anzeigen gut sichtbar angeordnet und zugänglich?',
        gauges:
          'Bei Manometern zusätzlich: Ist der Anzeigebereich ausreichend, sind Grenzwerte gekennzeichnet, ist eine Dämpfung vorhanden, wo erforderlich, ist die Anzeige gut lesbar und sind bei Messeinrichtungen mit Kontaktgebern die Verstelleinrichtungen ausreichend gesichert, wo sie sicherheitsrelevant sind?',
      },
      adjustments: {
        tamperProof:
          'Sind Verstelleinrichtungen an sicherheitsrelevanten Bauteilen so gestaltet oder geschützt, dass sie nicht ohne absichtliches Betätigen verstellt werden können, etwa Verstellung nur mit Werkzeug, Verplombung oder feste Begrenzung des Verstellbereichs?',
      },
      cylinders: {
        endStops:
          'Wo Hubendanschläge erforderlich sind: Sind sie vorhanden, richtig positioniert und ausreichend dimensioniert, nachgewiesen durch einen Versuch am Baumuster, etwa durch Anfahren mit maximaler Geschwindigkeit?',
        rodProtection: 'Wo vorhersehbare Beschädigungen wie Kerben, Kratzer oder Korrosion es erfordern: Ist die Kolbenstange geschützt?',
      },
      temperature: {
        hotSurfaces:
          'Wo im Betrieb heiße Oberflächen im Arbeits- und Verkehrsbereich auftreten: Sind diese geschützt? Grenztemperaturen sind in ISO 13732-1 festgelegt.',
        hoseFire: 'Sind Schlauchleitungen so befestigt oder abgeschirmt, dass keine Brandgefahr besteht, etwa im Bereich heißer Oberflächen?',
      },
      rescue: {
        rescuePossible:
          'Falls die Risikobeurteilung Restrisiken ergibt, die ein Befreien von Personen notwendig machen können: Ist ein Befreien möglich, etwa durch Betätigen von Ventilen oder Stellteilen, Druckentlastung des Systems oder Demontage von Bauteilen?',
        rescueNotes:
          'Sind, wo erforderlich, Hinweise zum Befreien von Personen vorhanden, etwa Schilder an Ventilen, an anderen Betätigungselementen oder an der Maschine?',
      },
      accumulatorCheck: {
        shutdown:
          'Wird der Hydrospeicher beim Abschalten der Anlage automatisch druckentlastet oder über eine abschließbare Hauptbefehlseinrichtung abgesperrt?',
        manualRelease: 'Ist eine manuelle Druckentlastungseinrichtung vorhanden?',
        warningSign: 'Ist ein Warnschild vorhanden mit der Aufschrift: „Vorsicht, Druckspeicher. Vor Reparatur oder Demontage drucklos machen.“?',
        remoteLines:
          'Sind Leitungen, die direkt mit dem Hydrospeicher verbunden sind, aber nicht in seiner unmittelbaren Nähe liegen, mit einem Gefahrenhinweis versehen?',
        gasNote: 'Sind Gasvorfülldruck und Gasart (etwa Stickstoff) am Hydrospeicher angegeben?',
        noModifications: 'Ist der Hydrospeicher frei von sichtbaren unzulässigen Veränderungen wie mechanischer Bearbeitung oder Schweißen?',
      },
      tests: {
        functions: 'Werden alle Funktionen der Anlage bestimmungsgemäß ausgeführt?',
        safetyDevices: 'Funktionieren alle Sicherheitseinrichtungen bestimmungsgemäß?',
        emergencyStop: 'Wirkt der Not-Halt wie vorgesehen?',
        noNewHazards: 'Entstehen beim Betätigen des Not-Halts keine zusätzlichen Gefahren, auch bei verketteten Anlagen?',
        restart: 'Muss die Anlage nach dem Entriegeln des Not-Halts neu gestartet werden?',
        pressureTest: 'Verläuft eine Druckprüfung mit maximalem Betriebsdruck ohne Störungen wie Leckagen?',
        speedLimits: 'Werden die festgelegten Geschwindigkeits- und Drehzahlgrenzen von Zylindern und Motoren nicht überschritten?',
        noBending: 'Treten bei der Funktionsprüfung keine Biegungen oder Verwindungen von Kolbenstangen und Zylindern auf (nur Sichtkontrolle)?',
      },
      manual: {
        contents:
          'Enthält die Betriebsanleitung die bestimmungsgemäße Verwendung, die vernünftigerweise vorhersehbare Fehlanwendung, eine Beschreibung der hydraulischen Ausrüstung, die Betriebsdruckgrenzen, die Betriebstemperaturgrenzen von Druckflüssigkeit und Bauteilen, den Einsatztemperaturbereich und sonstige Umgebungseinflüsse wie Brand- und Explosionsgefahr, den Hydraulikschaltplan, die Hydraulikstückliste und, wo erforderlich, den Funktionsplan?',
        transport:
          'Sind Angaben zum sicheren Transport vorhanden: Erläuterungen zum Transport, Gewicht, Transportsicherung und Verpackung, Zeichnungen der Anschlagpunkte für Hebezeuge, Verschließen von Anschlussöffnungen, Schutz von Außengewinden, besondere Vorkehrungen wie das Einfahren von Kolbenstangen und Kennzeichnung der Leitungen und Verbindungen, die für den Transport getrennt werden müssen?',
        commissioning:
          'Sind Angaben zu Inbetriebnahme und Betrieb vorhanden: Platzbedarf einschließlich Sicherheitsabständen, zulässige Umgebungsbedingungen wie Feuchtigkeit, Temperatur und Vibration, Montageanweisungen, Befestigung für den sicheren Betrieb, Gefahrenhinweise wie besondere Sicherheitseinrichtungen und Anschlüsse an die Energieversorgung?',
        fluid: 'Nennt die Betriebsanleitung Typ und Kenngröße der Hydraulikflüssigkeit?',
        safetyDataSheet:
          'Weist sie darauf hin, dass die Angaben im Sicherheitsdatenblatt der Druckflüssigkeit in der Betriebsanweisung zu beachten sind, etwa zu physikalischen und sicherheitstechnischen Schutzmaßnahmen, Lagerung und Handhabung, Maßnahmen bei Unfällen und Bränden, Toxikologie und Ökologie?',
        disposal: 'Enthält sie Angaben zur Entsorgung der Druckflüssigkeit?',
        maintenance:
          'Sind Angaben zu Instandhaltung und Prüfung vorhanden: Anforderungen an das Personal, erforderliche persönliche Schutzausrüstung, Restdrücke bei abgeschalteter Anlage, Fehlererkennung und -beseitigung, Behälter- und Systementleerung, Wartungsintervalle, Sicherheitsmaßnahmen, Druckentlastung (etwa von Hydrospeichern), Einstellvorgänge, Wiederinbetriebnahme (etwa Entlüften und Einstellen) und Anbringen der Schutzeinrichtungen?',
        hoseData: 'Sind Daten der Schlauchleitungen enthalten, etwa Lager- und Verwendungsdauer?',
        periodicInspections: 'Sind regelmäßige Prüfungen festgelegt, etwa für Hydrospeicher und Schlauchleitungen?',
        emergencies:
          'Sind Angaben zum Verhalten bei Notfällen vorhanden: Betätigen des Not-Halts, Freifahren, Maßnahmen bei Energieausfall, Befreien von Personen, geeignete Feuerlöscheinrichtungen und Erste Hilfe, etwa bei Vergiftung, Erstickung und Verbrennung?',
      },
    },
    hints: {
      circuit: {
        unexpectedStart:
          'Bei Systemen mit integriertem Druckerzeuger sind andere Maßnahmen möglich, etwa das Trennen der elektrischen Energieversorgung. Muss der Druck nach dem Trennen erhalten bleiben, etwa in einem Kreis mit Hydrospeicher, sind ebenfalls andere Maßnahmen möglich.',
        pressureSurges:
          'Etwa durch eine geeignete Ausführung des Leitungssystems, Druckbegrenzungsventile, zusätzliche Dämpfung wie einen Hydrospeicher und geeignete Bauteile: Wegeventile mit passender Ausbildung des Steuerkolbens, Zylinder mit Endlagendämpfung, Stetigventile mit passender Regelcharakteristik.',
        testPoints:
          'Messanschlüsse können erforderlich sein, wo Einstellungen oder Prüfungen vorgenommen werden (etwa an Arbeits- und Steuerleitungen zum Einstellen von Druckbegrenzungsventilen oder zum Prüfen gesteuerter Rückschlagventile), wo Änderungen von Temperatur, Druck oder Volumenstrom zu Gefährdungen führen können (etwa in Tank- oder Leckageleitungen und an Wärmetauschern) und für die Instandhaltung.',
      },
      sizing: {
        componentRatings:
          'Das gilt für Pumpen und Motoren, Zylinder, Ventile, Einrichtungen zur Reinhaltung der Druckflüssigkeit, Rohre, Rohrverbindungen und Kanäle, Schlauchleitungen (genormt, etwa nach EN 853, EN 854, EN 856, EN 857 oder ISO 18752), Flüssigkeitsbehälter, Hydrospeicher und Wärmetauscher.',
      },
      emergencyStop: {
        devices:
          'Schutzeinrichtungen wie Lichtgitter, Laserscanner oder Radarsensoren lösen einen Sicherheitshalt aus, keinen Not-Halt. Ein Not-Halt wird immer durch eine bewusste Handbetätigung ausgelöst (ISO 13850).',
      },
      servoValves: {
        controlHazard:
          'Etwa durch sichere elektrische Trennung der Steuerenergie der Magnetspulen, kombiniert mit Ventilen, die durch ihre Bauart geeignet sind (in Grundstellung zu sperrende Anschlüsse mit ausreichender positiver Überdeckung, Grundstellung durch Federkraft bei Wegnahme der Steuerenergie), oder mit zusätzlichen herkömmlichen Ventilen, wo die Servo- oder Proportionalventile durch ihre Bauart nicht geeignet sind.',
        unintendedMotion: 'Die Maßnahmen können dieselben sein wie zum Beibehalten oder Wiederherstellen der Kontrolle.',
      },
      piping: {
        quickCouplings: 'Das Abdichten der Auslassöffnung darf keine Sicherheitsfunktion aufheben, etwa bei federbelasteten Bremsen.',
      },
    },
  },
  pneumatics: {
    parts: {
      documentation: 'Prüfung der Dokumentation',
      machine: 'Prüfung an der gebauten Maschine',
      instructions: 'Betriebsanleitung',
    },
    sections: {
      assessment: 'Beurteilung der pneumatischen Ausrüstung',
      circuit: 'Schaltpläne',
      sizing: 'Dimensionierung',
      airTreatment: 'Aufbereitung der Druckluft',
      emergencyStop: 'Not-Halt',
      vesselDesign: 'Druckbehälter',
      servoValves: 'Steuerungen mit Servo- oder Proportionalventilen',
      marking: 'Kennzeichnung',
      assembly: 'Aufbau',
      piping: 'Rohr- und Schlauchleitungen',
      exhaust: 'Abluft und Messanschlüsse',
      maintenance: 'Instandhaltungsgerechte Gestaltung',
      electrical: 'Elektrische Ausrüstung',
      energySupply: 'Energieversorgung und Energieschwankungen',
      actuators: 'Stellteile',
      indicators: 'Mess- und Anzeigeeinrichtungen',
      adjustments: 'Verstelleinrichtungen an sicherheitsrelevanten Bauteilen',
      cylinders: 'Hubendanschläge und Schutz der Kolbenstange',
      fire: 'Brandgefahr',
      rescue: 'Befreien von Personen',
      vesselCheck: 'Druckbehälter',
      tests: 'Prüfungen',
      manual: 'Pneumatischer Teil der Betriebsanleitung',
    },
    items: {
      assessment: {
        documents:
          'Liegen folgende Unterlagen vor: Schaltpläne, Stücklisten, Datenblätter aller Bauteile, Betriebsanleitung und weitere erforderliche Unterlagen?',
        circuitFunctions: 'Sind die pneumatischen Bauteile geeignet, die Funktionen dieser Schaltung zu erfüllen?',
        typeCStandard: 'Wurde geprüft, ob für die Maschine eine C-Norm gilt? Titel in der Bemerkung festhalten.',
        typeCRequirements:
          'Falls eine C-Norm gilt: Sind deren Anforderungen an die pneumatische Ausrüstung, die über ISO 4414 hinausgehen, berücksichtigt?',
        riskAssessment:
          'Wurde die Risikobeurteilung der Maschine nach ISO 12100 auf Gefährdungen ausgewertet, aus denen sich Sicherheitsanforderungen an die pneumatische Ausrüstung ergeben, und sind diese Anforderungen berücksichtigt?',
      },
      circuit: {
        iso1219: 'Sind die Schaltpläne nach ISO 1219-2 dargestellt?',
        layout: 'Ist die Leitungsführung einfach gezeichnet, sodass alle Schaltwege verfolgt werden können, und möglichst kreuzungsfrei?',
        symbols: 'Sind Schaltzeichen nach ISO 1219-2 verwendet und folgen die Betriebsmittelkennzeichen IEC 81346-2?',
        restPosition: 'Sind die Symbole unbetätigt im energielosen Zustand (Ruhestellung) dargestellt?',
        lineColours: 'Sind die Leitungen in den Farben der tatsächlich verwendeten Schläuche dargestellt?',
        assemblies: 'Sind Baugruppen durch Umrahmungslinien abgegrenzt?',
        crossDesignations:
          'Stimmen die Kennzeichnungen der relevanten Betriebsmittel in den pneumatischen, elektrischen und elektronischen Schaltplänen überein?',
        portMarking: 'Sind alle Leitungsanschlüsse gekennzeichnet?',
        sheetTransitions: 'Sind die Übergänge der Leitungen zwischen den einzelnen Schaltplänen gekennzeichnet?',
        partsList: 'Ist auf dem Schaltplan eine Stückliste dargestellt?',
        supplementary: 'Sind bei Bedarf ergänzende Unterlagen wie Funktionsdiagramm, Lageplan oder Funktionsplan vorhanden?',
        unexpectedStart:
          'Kann das System zur Verhinderung eines unerwarteten Anlaufs vollständig von den Energiequellen getrennt und die gespeicherte Energie abgebaut werden?',
        safePositionValves:
          'Sind die Ventile ermittelt, die beim Versagen der Steuerung oder beim Betätigen einer Schutzeinrichtung eine bestimmte Sicherheitsstellung einnehmen oder beibehalten müssen? In der Bemerkung auflisten.',
        safePositionMeans:
          'Nehmen diese Ventile im stromlosen Zustand ihre Sicherheitsstellung ein und werden sie durch Federvorspannung oder ein physikalisch ähnliches Prinzip darin gehalten?',
        manualOverride:
          'Wo elektrisch betätigte Ventile aus Sicherheitsgründen auch von Hand geschaltet werden müssen: Haben sie eine Hand-Hilfsbetätigung, die nicht unbeabsichtigt betätigt werden kann und nicht rastet?',
        overpressure: 'Sind alle Teile der Anlage gegen unzulässig hohe Drücke geschützt, etwa durch Druckregelventile?',
        pressureLoss: 'Ist sichergestellt, dass Druckverlust oder Leckagen zu keiner Gefährdung führen?',
        switching: 'Ist sichergestellt, dass das Ein- und Ausschalten der Energieversorgung zu keiner Gefährdung führt?',
        failureReturn: 'Ist sichergestellt, dass Ausfall oder Wiederkehr der Energieversorgung zu keiner Gefährdung führt?',
        fluctuations:
          'Falls Energieschwankungen zu einer Gefährdung führen können: Sind die zulässigen Grenzen festgelegt, werden Schwankungen erkannt und angezeigt, und sind geeignete Maßnahmen getroffen?',
        smoothMotion: 'Wo ein sanftes Beschleunigen oder Verzögern von Bewegungen erforderlich ist: Ist es vorgesehen?',
        pressureSurges: 'Ist die Anlage so ausgelegt, dass Druckstöße und Druckverstärkungen zu keiner Gefährdung führen?',
        testPoints: 'Sind Messanschlüsse vorgesehen, wo sie erforderlich sind?',
        sequence: 'Ist sichergestellt, dass Fehlfunktionen in der Schrittfolge von Abläufen zu keiner Gefährdung führen?',
        externalForces: 'Wird ein unzulässig hoher Druck infolge äußerer Kräfte auf die pneumatische Anlage verhindert?',
      },
      sizing: {
        designData:
          'Sind die der Auslegung zugrunde gelegten Daten dokumentiert: maximaler Betriebsdruck, Drücke in Teilsystemen, Steuerdruck, Steuerspannung und Betriebstemperaturbereich? Werte in der Bemerkung festhalten.',
        componentRatings: 'Sind alle Teile der Anlage so ausgewählt, dass sie den zu erwartenden Drücken, Temperaturen und sonstigen Belastungen standhalten?',
        cylinderSizing:
          'Sind die Zylinder für Druck, Biegung und Knickung ausreichend dimensioniert, nachgewiesen durch Berechnung oder Datenblatt?',
        cylinderFasteners:
          'Sind die Befestigungsschrauben der Zylinder und ihrer Anbauteile ausreichend dimensioniert und so weit wie möglich frei von Scherkräften?',
        valveMisassembly: 'Ist der falsche Einbau von Ventilen verhindert?',
      },
      airTreatment: {
        contaminants:
          'Sind Maßnahmen getroffen, um schädliche feste, flüssige und gasförmige Stoffe von der Druckluft fernzuhalten, etwa Filter, Abscheider, Trockner oder Öler?',
        filtration:
          'Ist der Grad der Filterung für die Bauteile und für die Umgebungsbedingungen am bestimmungsgemäßen Einbauort ausreichend?',
        filterDegradation: 'Ist ausgeschlossen, dass eine nachlassende Filterwirkung zu einer gefährlichen Situation führt?',
      },
      emergencyStop: {
        equipped: 'Ist die Maschine mit einer Not-Halt-Funktion ausgerüstet?',
        devices:
          'Wird der Not-Halt durch eine bewusste Handbetätigung geeigneter Einrichtungen ausgelöst, etwa Not-Halt-Taster, Reißleine oder den Hauptschalter, wo dieser für Not-Halt ausgelegt ist? Einrichtungen in der Bemerkung festhalten.',
        effect:
          'Hat das Betätigen des Not-Halts die vorgesehene Wirkung, etwa Abschalten des zentralen Hauptventils, Absperren des Volumenstroms zu den Antrieben, Entlüften oder Absperren der Druckbehälter, Druckerhaltung in Teilsystemen (Spanndruck, Hochhalten von Lasten) oder Freifahren? Wirkungen in der Bemerkung festhalten.',
        valves:
          'Sind die im Not-Halt-Kreis eingesetzten Ventile geeignet, diese Wirkungen zu erreichen, etwa ein 5/3-Wegeventil mit gesperrter Mittelstellung zum Anhalten einer Bewegung oder Ventile, die im stromlosen Zustand ihre Sicherheitsstellung einnehmen?',
        allModes: 'Wirkt der Not-Halt in allen Betriebsarten, etwa Automatik, Halbautomatik und Einrichten?',
        servoSuitable: 'Erfüllen auch Servo- oder Proportionalventile im Not-Halt-Kreis diese Anforderungen?',
        additionalValves:
          'Falls nicht: Können zusätzliche Ventile die Antriebe im Gefahrenfall in eine definierte sichere Stellung bringen?',
      },
      vesselDesign: {
        data: 'Falls die Anlage Druckbehälter enthält: Sind Volumen V in Litern und Druckliterprodukt p × V in bar × Liter dokumentiert? Werte in der Bemerkung festhalten.',
        directive:
          'Wurde festgestellt, ob der Druckbehälter unter die Richtlinie 2014/68/EU (Druckgeräte) oder die Richtlinie 2014/29/EU (einfache Druckbehälter) fällt?',
        category:
          'Bei Druckbehältern nach Richtlinie 2014/68/EU: Ist die Kategorie für die Konformitätsbewertung ermittelt? In der Bemerkung festhalten.',
        certificates:
          'Liegen die für den Druckbehälter erforderlichen Bescheinigungen vor, etwa EU-Konformitätserklärung und EU-Baumusterprüfbescheinigung?',
        inspectionBeforeUse:
          'Liegt eine Bescheinigung über die Prüfung vor der ersten Inbetriebnahme vor, durchgeführt von einer zugelassenen Stelle oder einer fachkundigen Person nach den nationalen Vorschriften?',
        safetyDevices:
          'Sind folgende Sicherheitseinrichtungen vorhanden und im Schaltplan dargestellt: Manometer, Sicherheitsventil, Absperrventil und Druckentlastungsventil?',
        switchedOff:
          'Wird der Druckbehälter bei abgeschalteter Anlage druckluftseitig automatisch entlüftet oder druckluftseitig sicher abgesperrt?',
        holdPressure: 'Ist festgelegt, ob der Druck nach dem Abschalten der Anlage erhalten bleiben muss?',
      },
      servoValves: {
        controlHazard:
          'Falls Antriebe mit Servo- oder Proportionalventilen gesteuert werden, bei denen Fehlfunktion oder Fehlansteuerung eine Gefährdung verursachen kann: Sind Maßnahmen vorgesehen, um die Kontrolle über diese Antriebe beizubehalten oder wiederherzustellen?',
        unintendedMotion:
          'Falls Geschwindigkeiten von Antrieben mit Servo- oder Proportionalventilen gesteuert werden und eine unbeabsichtigte Bewegung eine Gefährdung verursachen kann: Sind Maßnahmen vorgesehen, um die Antriebe in einer sicheren Lage zu halten oder in eine sichere Lage zu bewegen?',
        filtration:
          'Ist in der Zuleitung zu allen Servo- oder Proportionalventilen, bei denen eine durch Verschmutzung verursachte Fehlfunktion eine Gefährdung herbeiführen kann, eine Filterung nach den Angaben des Herstellers sichergestellt?',
      },
      marking: {
        positionMarks:
          'Sind die Bauteile an oder neben dem Bauteil mit ihrer Positionsnummer oder ihrem Kennbuchstaben aus dem Schaltplan gekennzeichnet?',
        componentData:
          'Sind die funktionalen Bauteile dauerhaft und gut leserlich gekennzeichnet mit Name des Herstellers oder Lieferanten, Produktidentifizierung und Bemessungsdruck, mit Symbolen nach ISO 1219-1?',
        stackOrder: 'Bei Höhenverkettungen: Ist die Reihenfolge der Elemente neben der Verkettung angegeben, nicht aber auf den Verkettungselementen?',
        vesselMarking:
          'Sind einfache Druckbehälter nach EN 286-1 (unter 30 bar und 10 000 bar × Liter, zylindrisch, Serienfertigung) gekennzeichnet mit Herstelldatum, CE-Kennzeichnung, Serien- oder Losnummer, zulässigem Überdruck, Volumen in Litern und zulässigem Temperaturbereich?',
        valveOperators:
          'Bei nichtelektrischen Ventilbetätigungen: Stimmen die Kennzeichnung der Betätigung und ihrer Funktionen mit dem Schaltplan überein?',
        testDrainPoints: 'Sind Mess- und Ablassstellen gemäß Schaltplan gekennzeichnet und leicht zugänglich?',
        vesselWarning:
          'Ist an einer Anlage mit Druckbehälter an gut sichtbarer Stelle ein Warnschild angebracht mit der Aufschrift: „Achtung, Anlage enthält Druckbehälter. Vor Beginn von Instandhaltungsarbeiten muss die Anlage druckentlastet werden.“?',
        vesselMaintenanceNote:
          'Falls ein Druckbehälter nach dem Abschalten der Anlage unter Druck bleibt: Sind Hinweise zur sicheren Instandhaltung gut sichtbar angebracht?',
        interchangeableLines: 'Sind Leitungsenden, die vertauscht werden könnten, gemäß Schaltplan gekennzeichnet?',
      },
      assembly: {
        conformsToDiagram: 'Ist das Pneumatiksystem gemäß Schaltplan aufgebaut?',
        mountingPosition: 'Entspricht die Einbaulage der Bauteile den Angaben ihrer Hersteller?',
        cylinderFasteners:
          'Sind alle Befestigungsschrauben der Zylinder und ihrer Anbauteile ausreichend dimensioniert und frei von Scherkräften?',
        fastenersSecured: 'Sind sie so befestigt, dass sie einem Lösen durch Stöße und Schwingungen widerstehen?',
        mechanicalValves: 'Sind mechanisch betätigte Ventile so eingebaut, dass Schaltkurven oder Nocken sie nicht beschädigen können?',
        intensification: 'Sind Maßnahmen gegen unbeabsichtigte Druckübersetzung vorhanden und wirksam?',
        backPressure:
          'Sind Gefährdungen durch Staudruck in verketteten Ventilen, in gemeinsamen Entlüftungsleitungen oder durch Schalldämpfer in Abluftöffnungen verhindert?',
        bowlGuards:
          'Haben nichtmetallische Behälter von Filtern, Abscheidern, Druckregelventilen und Ölern über 1 bar × Liter einen Berstschutz?',
      },
      piping: {
        pipeSupport: 'Sind Rohrleitungen ausreichend befestigt, mit Rohrhalterungen an beiden Enden und an Punkten entlang ihrer ganzen Länge?',
        supportDamage: 'Ist die Befestigung so ausgeführt, dass die Rohrleitungen nicht beschädigt werden? Befestigen durch Schweißen ist nicht zulässig.',
        componentsOnPipes:
          'Falls Rohrleitungen zur Befestigung von Bauteilen dienen: Ist sichergestellt, dass die Masse der Bauteile keine Stöße oder Schwingungen verursacht, die die Rohrleitungen unzulässig belasten?',
        notAStep: 'Sind Rohr- und Schlauchleitungen so verlegt, dass sie nicht als Stufe, Leiter oder Aufstiegshilfe verwendet werden können?',
        wrongConnection:
          'Sind Rohr- und Schlauchleitungen einschließlich ihrer Anschlüsse so angeordnet oder ausgeführt, dass eine falsche Verbindung, die zu einer Gefährdung führt, nicht hergestellt werden kann, etwa durch verschiedene Gewinde oder die Formgebung der Leitung?',
        wrongConnectionMarking: 'Falls nicht: Sind sie eindeutig und dauerhaft gemäß Schaltplan gekennzeichnet?',
        protectedRouting:
          'Sind Rohr- und Schlauchleitungen so angeordnet, dass sie gegen alle vorhersehbaren Beschädigungen geschützt sind und den Zugang für Einstellung, Reparatur und Austausch von Bauteilen oder den Betrieb der Anlage nicht behindern?',
        hoseMarking:
          'Sind auf dem Schlauch dauerhaft und gut leserlich angegeben: Name und Anschrift des Herstellers, Herstelldatum, Bemessungsdruck und, optional, Nenn-Innendurchmesser?',
        tubeMarking:
          'Sind auf dem Kunststoffrohr dauerhaft und gut leserlich angegeben: Name oder Kurzzeichen des Herstellers, Herstelldatum und, optional, Nenn-Innendurchmesser?',
        notReused: 'Sind die Schlauchleitungen aus Schläuchen hergestellt, die nicht bereits benutzt wurden?',
        serviceLife: 'Haben die Schlauchleitungen die vom Hersteller empfohlene Lager- und Verwendungsdauer nicht überschritten?',
        hoseInstallation:
          'Sind die Schlauchleitungen so eingebaut, dass sie die nötige Länge haben, um schädigende Belastungen wie Knicken oder Zug im Betrieb zu vermeiden, ohne unnötig lang zu sein, der Mindestbiegeradius eingehalten ist, ein Verdrehen bei Einbau und Betrieb auf ein Minimum beschränkt ist, keine Scheuerstellen vorhanden sind, die Kennzeichnung erkennbar bleibt und Beschichtungen mit dem Schlauchmaterial verträglich sind?',
        whipProtection:
          'Wo das Versagen einer Schlauchleitung (Ausreißen, Platzen) eine Gefährdung wie Aufpeitschen oder Austritt von Druckluft verursachen würde, etwa an Bedienplätzen oder Verfahrwegen: Sind geeignete Schutzmaßnahmen vorhanden, etwa Befestigung, Fangvorrichtung oder Abschirmung?',
        quickCouplings:
          'Wo Schnelltrennkupplungen verwendet werden: Dichten Aus- und Einlassöffnung beim Entkuppeln selbsttätig ab, kann kein Kupplungsteil weggeschleudert werden und keine Druckluft entweichen, und ist eine Druckentlastung vorhanden?',
      },
      exhaust: {
        exhaustAir:
          'Ist die Anlage so gebaut, dass betriebsmäßig ausströmende Luft keine Gefährdung verursacht, etwa durch geringe Ausströmgeschwindigkeit, Ort und Richtung der Austrittsöffnungen sowie Anordnung von Filtern, Filterschalldämpfern und Abschirmungen?',
        singleActing:
          'Falls einfach wirkende Zylinder vorhanden sind: Sind deren Luftauslassöffnungen so ausgelegt und angeordnet, dass die eingeschlossene Luft ohne Gefährdung von Personen ausgestoßen wird?',
        testPoints: 'Sind die erforderlichen Messanschlüsse vorhanden, leicht zugänglich sowie deutlich und unverwechselbar gekennzeichnet?',
      },
      maintenance: {
        access: 'Sind die Bauteile so angeordnet, dass sie für Instandhaltungsarbeiten leicht und gefahrlos zugänglich sind?',
        residualPressure:
          'Falls nach dem Trennen der Energiezufuhr noch Bauteile unter Druck stehen: Kann der Druck ohne Gefährdung abgebaut werden, sind erforderliche Maßnahmen wie Abstützungen vorgesehen und wird darauf hingewiesen?',
        removal:
          'Sind Maßnahmen getroffen oder die Bauteile so angeordnet und verbunden, dass ihr Ausbau keinen unnötigen Abbau angrenzender Bauteile erfordert?',
      },
      electrical: {
        solenoidVoltage: 'Sind die Elektromagnete der Pneumatikventile für zuverlässigen Betrieb bei minimaler und maximaler Spannung ausgelegt?',
        solenoidProtection: 'Haben die Elektromagnete die erforderliche Schutzart (IP-Code) gegen eindringende Flüssigkeiten und Staub?',
        terminalBoxes:
          'Haben die Klemmenkästen eine geeignete Schutzart, unverlierbare Befestigungsmittel für die Abdeckung und Kabeleinführungen mit Zugentlastung?',
        coversSecured: 'Sind die Abdeckungen von Klemmenleisten und Klemmenkästen an elektrisch betätigten Ventilen gegen Verlieren gesichert?',
      },
      energySupply: {
        switching: 'Führt das Einschalten, Ausschalten oder die Wiederkehr der Energieversorgung zu keiner Gefährdung?',
        indicators: 'Sind die für Energieschwankungen erforderlichen Anzeige- und Warneinrichtungen vorhanden?',
      },
      actuators: {
        design:
          'Sind die Stellteile deutlich sichtbar und außerhalb des Gefahrenbereichs angeordnet, eindeutig und dauerhaft gekennzeichnet, in ihrer Bewegungsrichtung mit der Steuerwirkung übereinstimmend, gegen unbeabsichtigtes Betätigen ausgelegt oder geschützt sowie ergonomisch gestaltet und angeordnet?',
        multiFunction: 'Wo ein Stellteil mehrere Wirkungen hat: Wird die jeweilige Steuerwirkung eindeutig angezeigt?',
        manualOverride:
          'Haben die relevanten elektrisch betätigten Ventile Hand-Hilfsbetätigungen, die die geforderte Funktion erzielen, nicht unbeabsichtigt betätigt werden können und nicht rasten?',
      },
      indicators: {
        visible:
          'Wo Messeinrichtungen vorhanden sind: Sind deren Anzeigen gut sichtbar und leicht zugänglich, den Messstellen eindeutig zugeordnet und funktionsfähig?',
        gauges:
          'Bei Manometern zusätzlich, soweit angemessen: Ist der Anzeigebereich ausreichend, sind Grenzwerte gekennzeichnet, ist eine Dämpfung vorhanden, wo erforderlich, ist die Anzeige gut lesbar und sind bei Messeinrichtungen mit Kontaktgebern die Verstelleinrichtungen ausreichend gesichert?',
      },
      adjustments: {
        tamperProof:
          'Sind Verstelleinrichtungen an sicherheitsrelevanten Bauteilen (etwa Druck- und Stromventile, Druckschalter, Endlagendämpfung) so gestaltet, dass sie nicht ohne absichtliches Betätigen verstellt werden können, etwa Verstellung nur mit Werkzeug, Verplombung oder feste Begrenzung des Verstellbereichs?',
      },
      cylinders: {
        endStops:
          'Wo Hubendanschläge erforderlich sind: Sind sie vorhanden, richtig positioniert, ausreichend dimensioniert und gegen Verstellen gesichert?',
        rodProtection: 'Wo vorhersehbare Beschädigungen wie Kerben, Kratzer oder Korrosion es erfordern: Ist die Kolbenstange geschützt?',
      },
      fire: {
        hoseFire:
          'Sind Schlauchleitungen und flexible Rohrleitungen so befestigt oder abgeschirmt, dass keine Brandgefahr durch äußere Einwirkung besteht, etwa im Bereich heißer Oberflächen?',
        lubricatedExhaust: 'Falls der Druckluft brennbare Schmiermittel zugesetzt sind: Ist keine Auslassöffnung auf heiße Oberflächen gerichtet?',
      },
      rescue: {
        rescuePossible:
          'Falls die Risikobeurteilung Restrisiken ergibt, die ein Befreien von Personen notwendig machen können: Ist ein Befreien möglich, etwa durch Betätigen von Ventilen oder Stellteilen, Druckentlastung des Systems oder Demontage von Bauteilen?',
        rescueNotes:
          'Sind, wo erforderlich, Hinweise zum Befreien von Personen vorhanden, etwa Schilder an Ventilen, an anderen Betätigungselementen oder an der Maschine?',
      },
      vesselCheck: {
        shutdown:
          'Wird der Druckbehälter beim Abschalten der Anlage automatisch druckentlastet, etwa durch ein 2/2-Wegeventil mit Federrückstellung, oder über eine abschließbare Hauptbefehlseinrichtung abgesperrt?',
        warningSign:
          'Falls er abgesperrt wird: Ist ein Warnschild vorhanden mit der Aufschrift: „Vorsicht, Druckbehälter. Vor Reparatur oder Demontage drucklos machen.“?',
        remoteLines: 'Sind Leitungen, die mit dem Druckbehälter verbunden sind, aber nicht in seiner unmittelbaren Nähe liegen, mit einem Gefahrenhinweis versehen?',
        noModifications: 'Ist der Druckbehälter frei von sichtbaren unzulässigen Veränderungen wie mechanischer Bearbeitung oder Schweißen?',
      },
      tests: {
        functions: 'Werden alle vorgesehenen Funktionen erfüllt?',
        safetyDevices: 'Funktionieren alle Sicherheitseinrichtungen bestimmungsgemäß?',
        emergencyStop: 'Wirkt der Not-Halt wie vorgesehen?',
        noNewHazards: 'Entstehen beim Betätigen des Not-Halts keine zusätzlichen Gefahren, auch bei verketteten Anlagen?',
        restart: 'Muss die Anlage nach dem Entriegeln des Not-Halts neu gestartet werden?',
        pressureTest: 'Verläuft eine Druckprüfung mit maximalem Betriebsdruck ohne Störungen wie Leckagen?',
        speedLimits: 'Werden die festgelegten Geschwindigkeits- und Drehzahlgrenzen von Zylindern und Motoren nicht überschritten?',
        noBending: 'Treten bei der Funktionsprüfung keine Biegungen oder Verwindungen von Kolbenstangen und Zylindern auf (nur Sichtkontrolle)?',
      },
      manual: {
        contents:
          'Enthält die Betriebsanleitung die bestimmungsgemäße Verwendung, die vernünftigerweise vorhersehbare Fehlanwendung, eine Beschreibung der pneumatischen Ausrüstung, die Betriebsdruckgrenzen, die Betriebstemperaturgrenzen, den Einsatztemperaturbereich und sonstige Umgebungseinflüsse, den Pneumatikschaltplan, die Pneumatikstückliste und, wo erforderlich, den Funktionsplan?',
        transport:
          'Sind Angaben zum sicheren Transport vorhanden: Erläuterungen zum Transport, Gewicht, Transportsicherung, Zeichnungen der Anschlagpunkte für Hebezeuge, Verschließen von Auslassöffnungen, Schutz von Außengewinden, besondere Vorkehrungen wie das Einfahren von Kolbenstangen und Sichern von Zylindern und Kennzeichnung der Leitungen und Verbindungen, die für den Transport getrennt werden müssen?',
        commissioning:
          'Sind Angaben zu Inbetriebnahme und Betrieb vorhanden: Platzbedarf einschließlich Sicherheitsabständen und Freiräumen für Wartungsarbeiten, zulässige Umgebungsbedingungen, Montageanweisungen, Befestigung für den sicheren Betrieb, Gefahrenhinweise und Anschlusskenndaten der Energieversorgung?',
        lubricants: 'Nennt die Betriebsanleitung eventuell erforderliche Schmiermittel der Druckluft?',
        safetyDataSheet:
          'Falls ein Schmiermittel erforderlich ist: Liegt dessen Sicherheitsdatenblatt vor und weist die Betriebsanleitung darauf hin, es zu beachten?',
        maintenance:
          'Sind Angaben zu Instandhaltung und Prüfung vorhanden: Anforderungen an das Personal, erforderliche persönliche Schutzausrüstung, Restdrücke bei abgeschalteter Anlage, Fehlererkennung und -beseitigung, Behälter- und Systementleerung, Wartungsintervalle, Sicherheitsmaßnahmen, Druckentlastung, Einstellvorgänge, Wiederinbetriebnahme (etwa Entlüften und Einstellen), Anbringen der Schutzeinrichtungen, Schlauchdaten wie Verwendungsdauer und regelmäßige Prüfungen, etwa von Druckbehältern, Schlauchleitungen, Zylindern und Wartungseinheiten?',
        emergencies:
          'Sind Angaben zum Verhalten bei Notfällen vorhanden: Betätigen des Not-Halts, Freifahren, Maßnahmen bei Energieausfall, Befreien von Personen, geeignete Feuerlöscheinrichtungen und Erste Hilfe?',
      },
    },
    hints: {
      circuit: {
        unexpectedStart:
          'Bei Systemen mit integriertem Druckerzeuger sind andere Maßnahmen möglich, etwa das Trennen der elektrischen Energieversorgung. Muss der Druck nach dem Trennen erhalten bleiben, etwa in einem Druckbehälter, sind ebenfalls andere Maßnahmen möglich.',
      },
      sizing: {
        componentRatings:
          'Das gilt unter anderem für Pneumatikmotoren, Zylinder, Ventile, Einrichtungen zur Aufbereitung der Druckluft, die Druckluft selbst, Rohre, Verbindungen und Kanäle sowie Druckbehälter.',
      },
      emergencyStop: {
        devices:
          'Schutzeinrichtungen wie Lichtgitter, Laserscanner oder Radarsensoren lösen einen Sicherheitshalt aus, keinen Not-Halt. Ein Not-Halt wird immer durch eine bewusste Handbetätigung ausgelöst (ISO 13850).',
      },
      servoValves: {
        controlHazard: 'Etwa durch sichere elektrische Trennung der Steuerenergie der Magnetspulen der Servo- oder Proportionalventile.',
        unintendedMotion: 'Die Maßnahmen können dieselben sein wie zum Beibehalten oder Wiederherstellen der Kontrolle.',
      },
    },
  },
  robotics: {
    parts: {
      controlPerformance: 'Sicherheitsbezogene Leistungsfähigkeit der Steuerung',
      design: 'Gestaltung und Einbau',
      motionLimits: 'Begrenzung der Roboterbewegung',
      layout: 'Anordnung',
      modes: 'Betriebsarten des Robotersystems',
      pendants: 'Handbediengeräte',
      maintenance: 'Instandhaltung und Reparatur',
      ims: 'Schnittstelle zum integrierten Fertigungssystem (IMS)',
      safeguarding: 'Technische Schutzmaßnahmen',
      collaborative: 'Kollaborierender Betrieb',
      commissioning: 'Inbetriebnahme',
    },
    sections: {
      performanceInfo: 'Angaben zur Leistungsfähigkeit',
      performanceLevel: 'Geforderte Leistung',
      riskBasedPerformance: 'Leistung aus der Risikobeurteilung',
      designConditions: 'Gestaltungsbedingungen',
      autoModeSelection: 'Wahl der Betriebsart Automatik',
      controls: 'Bedienelemente',
      power: 'Energieversorgung und Schaltschränke',
      bonding: 'Schutzpotentialausgleich',
      isolation: 'Trennung gefährdender Energie',
      storedEnergy: 'Freisetzen gespeicherter Energie',
      stopFunctions: 'Sicherheitshalt und Not-Halt',
      emergencyStop: 'Not-Halt-Einrichtungen',
      emergencyRecovery: 'Bewegen des Roboters im Notfall',
      warnings: 'Warnzeichen',
      lighting: 'Beleuchtung',
      applicationHazards: 'Gefährdungen durch die Anwendung',
      enablingDevices: 'Zusätzliche Zustimmeinrichtungen',
      spaces: 'Geschützter und eingeschränkter Raum',
      limitingDevices: 'Roboterbegrenzungseinrichtungen',
      dynamicLimiting: 'Dynamische Begrenzungseinrichtungen',
      perimeter: 'Äußere Schutzeinrichtungen',
      workingSpace: 'Freiräume und Zugang',
      materialHandling: 'Materialzu- und -abfuhr',
      processObservation: 'Prozessbeobachtung',
      multiRobot: 'Mehrfachroboterzellen',
      modeSelection: 'Wahl der Betriebsart',
      automaticMode: 'Betriebsart Automatik',
      automaticSelection: 'Auswahl der Betriebsart Automatik',
      automaticStart: 'Einleiten des Automatikbetriebs',
      startRestart: 'Start und Wiederanlauf',
      localControl: 'Lokale Steuerung bei manuellem Eingreifen',
      reducedSpeed: 'Manuell mit reduzierter Geschwindigkeit',
      highSpeed: 'Manuell mit hoher Geschwindigkeit',
      remoteControl: 'Fernsteuerung',
      pendantGeneral: 'Handbediengeräte allgemein',
      cableless: 'Kabellose oder absteckbare Handbediengeräte',
      multiRobotPendant: 'Handbediengeräte für mehrere Roboter',
      procedures: 'Inspektions- und Instandhaltungsverfahren',
      safeAccess: 'Sicherer Zugang für die Instandhaltung',
      guardDesign: 'Schutzeinrichtungen für die Instandhaltung',
      imsHazards: 'Gefährdungen durch andere Ausrüstung',
      imsEmergencyStop: 'Not-Halt im IMS',
      imsLocalControl: 'Lokale Steuerung im IMS',
      imsEnabling: 'Zustimmeinrichtungen im IMS',
      imsModes: 'Betriebsartenwahl im IMS',
      imsManual: 'Manuelles Eingreifen im IMS',
      safeguardsGeneral: 'Trennende und nichttrennende Schutzeinrichtungen',
      safeguardSelection: 'Auswahl der Schutzeinrichtungen',
      safeguardInstallation: 'Einbau der Schutzeinrichtungen',
      fixedMovableGuards: 'Feststehende und bewegliche trennende Schutzeinrichtungen',
      presenceStart: 'Anwesenheitserkennung gegen Start',
      presenceClearance: 'Anwesenheitserkennung für Freiräume',
      guards: 'Trennende Schutzeinrichtungen',
      guardDimensions: 'Abmessungen trennender Schutzeinrichtungen',
      interlockedGuards: 'Verriegelte bewegliche trennende Schutzeinrichtungen',
      guardLocking: 'Zuhaltung',
      entrapment: 'Schutz gegen Einschließen',
      sensitiveEquipment: 'Sensitive Schutzeinrichtungen',
      sensitiveStop: 'Sensitive Schutzeinrichtungen für den Sicherheitshalt',
      presenceSensing: 'Anwesenheitserkennung gegen Start',
      manualStations: 'Manuelle Be- und Entladestationen',
      movingStations: 'Bewegliche Stationen',
      sharedWorkspace: 'Gemeinsamer Arbeitsraum an Stationen',
      openings: 'Öffnungen für Material',
      adjacentCells: 'Angrenzende Zellen',
      endEffectors: 'Endeffektoren und Werkzeugwechselsysteme',
      muting: 'Muting',
      suspension: 'Außerkraftsetzen von Schutzeinrichtungen',
      collaborativeInfo: 'Angaben zum kollaborierenden Betrieb',
      collaborativeRisk: 'Risikobeurteilung und Schutzeinrichtungen',
      collaborativeWorkspace: 'Kollaborationsraum',
      collaborativeTransition: 'Wechsel zwischen autonomem und kollaborierendem Betrieb',
      collaborativeFeatures: 'Sicherheitsmerkmale',
      monitoredStop: 'Sicherheitsbewerteter überwachter Halt',
      handGuiding: 'Handführung',
      speedSeparation: 'Geschwindigkeits- und Abstandsüberwachung',
      powerForce: 'Leistungs- und Kraftbegrenzung',
      commissioningConcept: 'Inbetriebnahmekonzept',
      interimSafeguarding: 'Vorläufige Schutzeinrichtungen',
      startUp: 'Erstmaliges Ingangsetzen',
    },
    items: {
      performanceInfo: {
        stated:
          'Enthält die Benutzerinformation die Leistungsfähigkeit der sicherheitsbezogenen Steuerung sowie die Daten und Kriterien, nach denen sie festgelegt wurde?',
      },
      performanceLevel: {
        plCategory3: 'Erreicht die sicherheitsbezogene Steuerung PL d mit einer Struktur der Kategorie 3?',
        sil2: 'Wo stattdessen nach IEC 62061 bewertet wird: Erreicht sie SIL 2 mit einer Hardware-Fehlertoleranz von 1 und einem Proof-Test-Intervall von nicht unter 20 Jahren?',
      },
      riskBasedPerformance: {
        fromRiskAssessment: 'Werden die Ergebnisse der Risikobeurteilung zur Festlegung der geforderten Leistung verwendet?',
      },
      designConditions: {
        conditions: 'Ist das System auf Grundlage der vorgesehenen Einsatzbedingungen gestaltet und sind seine Bestandteile danach ausgewählt?',
      },
      autoModeSelection: {
        outside: 'Erfolgt die Wahl der Betriebsart Automatik von außerhalb des geschützten Bereichs?',
      },
      controls: {
        iec60204: 'Erfüllen die Bedienelemente IEC 60204-1?',
        noRemoteHazard:
          'Ist sichergestellt, dass das Robotersystem auf keine externen ferngesteuerten Befehle oder Zustände anspricht, die eine Gefährdungssituation verursachen können?',
      },
      power: {
        sources: 'Erfüllen alle Energiequellen die Anforderungen des Herstellers?',
        enclosureDoors:
          'Sind die Türen elektrischer Einbauräume so montiert, dass sie sich vollständig öffnen lassen und Fluchtwege stets erreichbar bleiben?',
      },
      bonding: {
        iec60204: 'Erfüllt der Schutzpotentialausgleich IEC 60204-1?',
      },
      isolation: {
        provided: 'Sind Einrichtungen zur Trennung gefährdender Energie vorgesehen?',
        marked: 'Sind diese Einrichtungen deutlich gekennzeichnet?',
      },
      storedEnergy: {
        provided: 'Sind Einrichtungen zum kontrollierten Freisetzen gespeicherter gefährdender Energie vorgesehen?',
        marked: 'Sind diese Einrichtungen deutlich gekennzeichnet?',
      },
      stopFunctions: {
        protectiveStop: 'Hat das Robotersystem eine Sicherheitshalt-Funktion?',
        emergencyStop: 'Hat das Robotersystem eine unabhängige Not-Halt-Funktion?',
        externalDevices: 'Lassen sich externe Schutzeinrichtungen an die Sicherheitshalt- und Not-Halt-Funktion anschließen?',
      },
      emergencyStop: {
        everyStation:
          'Hat jede Bedienstation, von der aus eine Roboterbewegung oder andere gefährdende Funktionen ausgelöst werden können, eine Not-Halt-Einrichtung?',
        stopsAll: 'Stoppt ihr Betätigen alle Roboterbewegungen und anderen gefährdenden Funktionen in der Zelle?',
        scope: 'Wirkt der Not-Halt auf das ganze System oder auf festgelegte Wirkungsbereiche der Steuerung für mehrere Funktionen?',
        sameScope: 'Haben alle Not-Halt-Einrichtungen in einem Arbeitsraum den gleichen Wirkungsbereich der Steuerung?',
        scopeInfo: 'Beschreibt die Benutzerinformation den Wirkungsbereich der Not-Halt-Einrichtungen?',
        requirements: 'Erfüllt die Not-Halt-Funktion die Not-Halt-Anforderungen von ISO 10218-2?',
        stopCategory: 'Entspricht die Not-Halt-Funktion der Stoppkategorie 0 oder 1?',
        performance:
          'Erreicht die Not-Halt-Funktion PL d mit einer Struktur der Kategorie 3, sofern die Risikobeurteilung keine anderen Leistungskriterien festlegt?',
        outputSignal:
          'Wo ein Not-Halt-Ausgangssignal vorgesehen ist: Bleibt es in Funktion, wenn die Energie vom Robotersystem weggenommen wird, oder wird andernfalls ein Not-Halt-Signal ausgegeben?',
      },
      emergencyRecovery: {
        procedure: 'Beschreibt die Benutzerinformation, wie der Roboter im Notfall bewegt werden kann, etwa um eine eingeklemmte Person zu befreien?',
        signs: 'Sind Schilder oder Kennzeichnungen für diese Vorgehensweise am Robotersystem angebracht oder Anleitungen dazu vorhanden?',
      },
      warnings: {
        obscured: 'Sind verdeckte Warnzeichen durch andere, gleich wirksame Warneinrichtungen ersetzt?',
      },
      lighting: {
        level: 'Wurde die für die Aufgaben benötigte Beleuchtungsstärke ermittelt und in der Benutzerinformation angegeben?',
        integral: 'Ist eine für die vorgesehenen Tätigkeiten geeignete eingebaute Beleuchtung vorhanden?',
      },
      applicationHazards: {
        considered: 'Berücksichtigt die Integration des Robotersystems die Gefährdungen durch die Anwendung?',
        interfaces:
          'Werden die Angaben des Herstellers zu den Schnittstellen zu anderen Maschinen, wie in der Benutzerinformation festgelegt, befolgt?',
      },
      enablingDevices: {
        iso10218: 'Erfüllen zusätzliche Zustimmeinrichtungen und deren Einbindung ISO 10218-1?',
        number: 'Sind ausreichend zusätzliche Zustimmeinrichtungen für die zu erwartende Zahl von Personen im geschützten Bereich vorgesehen?',
        sameFunction: 'Haben mehrere an eine Robotersteuerung angeschlossene Zustimmeinrichtungen die gleiche Funktionalität?',
        interlocked:
          'Sind Zustimmeinrichtungen für die Bereiche der Zelle verriegelt, in denen Personen Gefährdungen durch einen weiteren Roboter oder andere Einrichtungen ausgesetzt sind?',
        restart: 'Erfordern zusätzliche verriegelte Einrichtungen einen gesonderten Wiederanlauf?',
      },
      spaces: {
        safeguarded:
          'Ist der geschützte Bereich durch äußere Schutzeinrichtungen festgelegt, unter sorgfältiger Berücksichtigung des Orts, der Anordnung und der dortigen Gefährdungen?',
        restricted:
          'Ist der eingeschränkte Raum des Roboters durch Einrichtungen festgelegt, die die Bewegung von Roboter, Endeffektor, Vorrichtung und Werkstück begrenzen?',
        inside: 'Liegt der eingeschränkte Raum innerhalb des geschützten Bereichs?',
        distance:
          'Sind die äußeren Schutzeinrichtungen nicht näher an der Gefährdung angeordnet als der eingeschränkte Raum, außer sie sind als Begrenzungseinrichtung nach ISO 10218-2 gestaltet?',
      },
      limitingDevices: {
        mechanical: 'Erfüllen mechanische Roboterbegrenzungseinrichtungen ISO 10218-1?',
        nonMechanical: 'Erfüllen nicht-mechanische Roboterbegrenzungseinrichtungen ISO 10218-1?',
        controlSystem:
          'Erfüllen die Steuerungen nicht-mechanischer Begrenzungseinrichtungen ISO 10218-1, sofern eine Risikobeurteilung keine andere Leistung festlegt?',
        stoppingDistance: 'Ist der Anhalteweg an der Begrenzungseinrichtung in jeder Berechnung des eingeschränkten Raums berücksichtigt?',
        adjusted: 'Sind die Begrenzungseinrichtungen ordnungsgemäß eingestellt und gesichert?',
        actualLoad:
          'Wo nicht-mechanische Begrenzungseinrichtungen verwendet werden, einschließlich sicherheitsbewerteter Software-Achs- und Raumbegrenzung: Ist der eingeschränkte Raum mit dem Roboter unter tatsächlicher Last festgelegt?',
        speed:
          'Beruht der eingeschränkte Raum auf der maximalen Robotergeschwindigkeit oder, wo die Geschwindigkeit durch ein Überwachungssystem nach den Leistungsanforderungen von ISO 10218-2 begrenzt ist, auf der begrenzten Geschwindigkeit?',
        information: 'Enthält die Benutzerinformation die programmierten sicherheitsbewerteten und räumlichen Begrenzungen?',
        guardStrength:
          'Wo die äußere trennende Schutzeinrichtung als Begrenzungseinrichtung gestaltet ist: Werden die Ergebnisse der Risikobeurteilung zur Festlegung der Anforderungen an Gestaltung, Festigkeit und Verformung herangezogen?',
      },
      dynamicLimiting: {
        stopsRobot: 'Können dynamische mechanische Begrenzungseinrichtungen den Roboter unter Nennlast und Nenngeschwindigkeit anhalten?',
        performance: 'Erfüllen die sicherheitsbezogenen Teile der dynamischen Begrenzung die Leistungsanforderungen von ISO 10218-2?',
      },
      perimeter: {
        implemented: 'Sind die äußeren Schutzeinrichtungen nach den Anforderungen von ISO 10218-2 an Schutzeinrichtungen ausgeführt?',
        selection:
          'Berücksichtigt die Auswahl der Schutzeinrichtungen die zu erwartende Betriebsbeanspruchung, den Einfluss des verarbeiteten Materials und andere relevante äußere Einflüsse?',
        reachOver: 'Erfüllen die Sicherheitsabstände gegen Über- oder Durchgreifen ISO 13857?',
        interlockedDistance: 'Erfüllen die Mindestabstände verriegelter trennender Schutzeinrichtungen ISO 13855?',
        crushing: 'Erfüllen die Mindestabstände zur Vermeidung von Quetschgefahren ISO 13854?',
      },
      workingSpace: {
        clearance: 'Wird in Arbeitsbereichen, in denen manuell mit hoher Geschwindigkeit gearbeitet wird, ein Freiraum von mindestens 500 mm eingehalten?',
        tasksOutside: 'Ermöglicht die Anordnung, wo durchführbar, die Erledigung von Aufgaben von außerhalb des geschützten Bereichs?',
        safeAccess: 'Ist ein sicherer und geeigneter Zugang zu Arbeitspositionen innerhalb des geschützten Bereichs vorhanden?',
        accessFree: 'Sind Zugänge und Zugangsmittel frei von Gefährdungen?',
        permanentAccess: 'Ist für häufig ausgeführte Tätigkeiten eine dauerhafte Zugangseinrichtung vorgesehen?',
        electricalAccess: 'Wo elektrische Ausrüstung oberhalb der normalen Reichweite angeordnet ist: Ist eine Zugangseinrichtung vorgesehen?',
        accessHeight: 'Ist ein Zugang zu Einrichtungen vorgesehen, die zwischen 400 mm und 2000 mm über der Zugangsebene liegen?',
        platforms: 'Sind Arbeitsbühnen, Laufstege, Treppen, Treppenleitern und ortsfeste Leitern nach ISO 14122 ausgewählt und gestaltet?',
        adjacentCells: 'Sind technische Schutzmaßnahmen zwischen angrenzenden Zellen vorhanden?',
        materialFlow: 'Sind technische Schutzmaßnahmen für angrenzende Zellen während des Materialflusses vorgesehen?',
      },
      materialHandling: {
        detection:
          'Werden Personen erkannt, die den Gefährdungsbereich betreten, in dem Material über den geschützten Bereich zu- oder abgeführt wird?',
        measures: 'Verhindern Schutzmaßnahmen den Kontakt mit den Gefährdungen oder bringen sie die Gefährdungen in einen sicheren Zustand?',
      },
      processObservation: {
        modes:
          'Für die Prozessbeobachtung innerhalb des geschützten Bereichs: Sind die manuellen Betriebsarten (reduzierte oder hohe Geschwindigkeit) oder eine eigene Steuerungsbetriebsart für die Prozessbeobachtung vorgesehen?',
      },
      multiRobot: {
        notSelected: 'Verbleiben Robotersysteme in einer Mehrfachroboterzelle, die nicht für den Betrieb angewählt sind, in einem sicheren Zustand?',
        othersSafe: 'Verursachen andere, nicht manuell betriebene Roboter in der Zelle keine Gefährdung?',
      },
      modeSelection: {
        unauthorised: 'Ist eine unbefugte oder unbeabsichtigte Wahl der Betriebsart verhindert?',
        selectOnly: 'Wählen die Wahleinrichtungen nur die Betriebsart und setzen den Betrieb nicht in Gang?',
        separateStart: 'Ist zum Ingangsetzen des Roboterbetriebs eine gesonderte Betätigung erforderlich?',
        indication: 'Wird die gewählte Betriebsart eindeutig angezeigt?',
        changeSafe: 'Verursacht der Wechsel der Betriebsart keine Gefährdung?',
      },
      automaticMode: {
        entryStops: 'Löst in der Betriebsart Automatik das Betreten des geschützten Bereichs einen Sicherheitshalt aus?',
      },
      automaticSelection: {
        noOverride: 'Überlagert die Auswahl der Betriebsart Automatik keinen bestehenden Sicherheitshalt oder Not-Halt?',
        outside: 'Erfolgt die Auswahl der Betriebsart Automatik von außerhalb des geschützten Bereichs?',
        leavingStops: 'Löst das Umschalten aus der Betriebsart Automatik einen Halt aus?',
      },
      automaticStart: {
        outside: 'Wird der Automatikbetrieb von außerhalb des geschützten Bereichs eingeleitet?',
        safeguardsActive: 'Lässt sich der Automatikbetrieb nur einleiten, wenn alle Schutzeinrichtungen aktiv sind?',
      },
      startRestart: {
        simple: 'Sind Start und Wiederanlauf einfache Bedienvorgänge?',
        measuresActive: 'Sind die Schutzmaßnahmen vor Start und Wiederanlauf in Funktion?',
        performance: 'Erfüllen die sicherheitsbezogenen Steuerungsfunktionen für Start und Wiederanlauf die Leistungsanforderungen von ISO 10218-2?',
        manualReset: 'Sind manuell betätigte Verriegelungen (Rückstellung) für Start und Wiederanlauf vorgesehen?',
        personsProtected: 'Sind Personen im geschützten Bereich vor Start und Wiederanlauf geschützt?',
        notFromInside: 'Ist ausgeschlossen, dass die Bedienelemente für Start und Wiederanlauf von innerhalb des geschützten Bereichs betätigt werden?',
        nobodyInside:
          'Sind funktionale Sicherheits- und Schutzmaßnahmen vorgesehen, die sicherstellen, dass sich vor Start oder Wiederanlauf niemand im geschützten Bereich aufhält?',
        emergencyStopInside: 'Sind innerhalb des geschützten Bereichs zugängliche Not-Halt-Einrichtungen vorgesehen?',
        warning: 'Wird, wo erforderlich, vor dem Start ein Anwesenheitssignal oder ein akustisches und optisches Warnsignal gegeben?',
      },
      localControl: {
        local: 'Ist der Roboter beim manuellen Eingreifen in lokaler Steuerung in einer manuellen Betriebsart?',
        observation: 'Ermöglicht die Position der Steuereinrichtung die Beobachtung des Arbeitsbereichs?',
        stopNextToStart: 'Ist neben jeder Steuereinrichtung zum Starten eine Steuereinrichtung zum Stillsetzen angeordnet?',
        otherSources: 'Ist das Steuern von anderen Stellen aus verhindert, solange die lokale Steuerung aktiv ist?',
      },
      reducedSpeed: {
        tcpOffset: 'Ist der Werkzeugarbeitspunkt (TCP) mit der Offset-Funktion eingestellt?',
        maxSpeed: 'Beträgt die maximale Geschwindigkeit des TCP nicht mehr als 250 mm/s?',
        slower: 'Wurde festgelegt, ob eine geringere Geschwindigkeit erforderlich ist?',
        enabling: 'Ist für Bewegungen eine funktionstüchtige Zustimmeinrichtung erforderlich?',
      },
      highSpeed: {
        requirements: 'Sind die Anforderungen von ISO 10218-1 an den Betrieb mit hoher Geschwindigkeit und an das Handbediengerät erfüllt?',
        enablingTest: 'Enthält die Benutzerinformation eine Funktionsprüfung der Zustimmeinrichtung?',
      },
      remoteControl: {
        manualOnly: 'Ist Fernsteuerung nur in einer manuellen Betriebsart möglich?',
        oneStation: 'Ist bei Fernsteuerung immer nur eine Bedienstation gleichzeitig aktiv?',
        noOverride: 'Überlagert die Fernsteuerung weder die lokale Auswahl noch verursacht sie gefährdende Zustände?',
        activateLocally: 'Lässt sich die Fernsteuerung nur von der lokalen Steuerung aus aktivieren?',
        limitParameters: 'Sind ferngesteuerte Änderungen der Parameter der sicherheitsbewerteten Software-Achs- und Raumbegrenzung eingeschränkt?',
        indication: 'Wird eine aktive Fernsteuerung angezeigt?',
        notHighSpeed: 'Ist Fernsteuerung in der Betriebsart „Manuell mit hoher Geschwindigkeit“ verhindert?',
        information: 'Enthält die Benutzerinformation die Anforderungen an ferngesteuertes manuelles Eingreifen?',
      },
      pendantGeneral: {
        iso10218: 'Erfüllen Handbediengeräte, die im geschützten Bereich verwendet werden, ISO 10218-1?',
        emergencyStop: 'Erfüllt die Not-Halt-Funktion am Handbediengerät die Not-Halt-Anforderungen von ISO 10218-2?',
        cable: 'Haben kabelgebundene Handbediengeräte eine ausreichende Kabellänge und Haltbarkeit?',
        storage: 'Ist eine Ablage für das Handbediengerät vorgesehen, die Schäden verhindert?',
      },
      cableless: {
        iso10218: 'Erfüllen kabellose oder absteckbare Handbediengeräte die Anforderungen von ISO 10218-1?',
        devices: 'Erfüllen ihre Not-Halt- und Zustimmeinrichtungen ISO 10218-1?',
        unintended: 'Ist ein unbeabsichtigtes Steuern vermieden?',
        oneSystem: 'Ist ein kabelloses Handbediengerät nie gleichzeitig mit mehr als einem Robotersystem verbunden?',
        signalLoss: 'Führt ein Signalverlust zu einem Halt und erfordert der Wiederanlauf eine bewusste Handlung?',
        storage:
          'Sind Trennung und Ablage des Handbediengeräts so gelöst, dass aktive und inaktive Not-Halt-Einrichtungen nicht verwechselt werden können?',
        exclusive: 'Ist die ausschließliche Bedienung von einer Bedienstation sichergestellt?',
      },
      multiRobotPendant: {
        indication: 'Zeigen Handbediengeräte für mehrere Roboter an, welche Roboter gesteuert werden?',
        sameMode: 'Befinden sich alle ausgewählten Roboter in der gleichen Betriebsart?',
        unselectedSafe: 'Stellen nicht ausgewählte Roboter keine Gefährdung dar?',
        handGuided: 'Erfüllen handgeführte Steuerungselemente ISO 10218-1?',
      },
      procedures: {
        provided:
          'Sind Inspektions- und Instandhaltungsverfahren vorgesehen, die die Empfehlungen des Herstellers berücksichtigen und einen dauerhaft sicheren Betrieb ermöglichen?',
        functionTests: 'Fordert die Benutzerinformation regelmäßige Funktionsprüfungen der sicherheitsbezogenen Ausrüstung?',
      },
      safeAccess: {
        access: 'Ist das System für einen sicheren Zugang zur Instandhaltung gestaltet?',
        energyMeans: 'Hat das System Einrichtungen zur Beherrschung gefährdender Energie, mit Angaben zu deren Anwendung in der Benutzerinformation?',
        alternative: 'Hat das System geeignete alternative Schutzeinrichtungen für Aufgaben, die ohne Energietrennung durchgeführt werden?',
      },
      guardDesign: {
        size: 'Sind trennende Schutzeinrichtungen, die Zugang gewähren, groß genug für einen leichten Zugang?',
        fixedTool:
          'Lassen sich feststehende trennende Schutzeinrichtungen für gelegentliche Instandhaltungs- und Wartungsaufgaben nur mit Werkzeug entfernen?',
        frequentAccess:
          'Sind Stellen, die häufigen Zugang erfordern, durch nichttrennende Schutzeinrichtungen oder, vorzugsweise, durch bewegliche trennende Schutzeinrichtungen geschützt?',
        noStartOnClose: 'Löst eine bewegliche trennende Schutzeinrichtung beim Erreichen der Schutzstellung keinen Startbefehl aus?',
        remainInside:
          'Wo eine Person bei geschlossener beweglicher trennender Schutzeinrichtung im geschützten Bereich verbleiben kann: Sind zusätzliche Schutzmaßnahmen vorgesehen?',
        presenceType2:
          'Erfüllt eine Einrichtung zur Anwesenheitserkennung, die mit einer Wiederanlaufsperre verwendet wird, mindestens die Anforderungen an Typ 2 nach IEC 61496-1?',
      },
      imsHazards: {
        considered: 'Berücksichtigen Risikobeurteilung und Integration Gefährdungen durch andere Ausrüstung im geschützten Bereich?',
      },
      imsEmergencyStop: {
        allParts: 'Hat das IMS eine Not-Halt-Funktion, die auf alle betreffenden Teile der Anlage wirkt?',
        requirements: 'Erfüllen die Not-Halt-Einrichtungen die Not-Halt-Anforderungen von ISO 10218-2?',
        scopeInfo: 'Beschreibt die Benutzerinformation den Wirkungsbereich jeder Not-Halt-Einrichtung?',
      },
      imsLocalControl: {
        indicated: 'Wird die Auswahl der lokalen Steuerung der Steuerung des IMS angezeigt?',
        notOverridden: 'Ist ausgeschlossen, dass das IMS die lokale Steuerung überlagert?',
        stopsActive: 'Bleiben Not-Halt und Sicherheitshalt während der lokalen Steuerung funktionstüchtig?',
        nearby: 'Befinden sich die Einrichtungen zur Aktivierung der lokalen Steuerung in unmittelbarer Nähe der gesteuerten Elemente?',
        deactivation: 'Löst das Deaktivieren der lokalen Steuerung keine Gefährdungssituation innerhalb des geschützten Bereichs aus?',
        confirmation:
          'Falls die lokale Steuerung innerhalb des geschützten Bereichs deaktiviert werden kann: Ist eine gesonderte Bestätigung von außerhalb der Zelle erforderlich?',
      },
      imsEnabling: {
        requirements: 'Erfüllen zusätzliche Zustimmeinrichtungen im IMS die Anforderungen an zusätzliche Zustimmeinrichtungen?',
        interlocked: 'Ist die Zustimmeinrichtung durchgängig mit den Bereichen des IMS verriegelt?',
      },
      imsModes: {
        iso10218: 'Entspricht die Betriebsartenwahl ISO 10218-1?',
      },
      imsManual: {
        design: 'Ist das IMS für sichere manuelle Eingriffe gestaltet, einschließlich einer Einteilung in Zonen, wo erforderlich?',
        iso11161: 'Entspricht die Integration des Robotersystems in das IMS ISO 11161?',
      },
      safeguardsGeneral: {
        iso12100: 'Erfüllen trennende und nichttrennende Schutzeinrichtungen die Anforderungen von ISO 12100?',
      },
      safeguardSelection: {
        allHazards: 'Berücksichtigt die Auswahl der äußeren Schutzeinrichtungen alle Gefährdungen und Aufgaben?',
      },
      safeguardInstallation: {
        fixed: 'Sind die Schutzeinrichtungen fest eingebaut und ordnungsgemäß platziert?',
      },
      fixedMovableGuards: {
        iso14120: 'Erfüllen feststehende und bewegliche trennende Schutzeinrichtungen ISO 14120?',
        distance: 'Ist der Mindestabstand der trennenden Schutzeinrichtungen zur Gefährdung nach ISO 13857 festgelegt?',
        accessDistance: 'Wo der Zugang durch trennende Schutzeinrichtungen verhindert wird: Wird ISO 13857 zur Festlegung des Mindestabstands angewendet?',
      },
      presenceStart: {
        requirements:
          'Erfüllen Schutzeinrichtungen mit Anwesenheitserkennung, die Start oder Wiederanlauf verhindern, die Anforderungen von ISO 10218-2 an die Anwesenheitserkennung?',
      },
      presenceClearance: {
        requirements:
          'Erfüllen Schutzeinrichtungen mit Anwesenheitserkennung, die einen Freiraum sicherstellen, die Anforderungen von ISO 10218-2 an die Anwesenheitserkennung?',
      },
      guards: {
        standards: 'Erfüllen alle trennenden Schutzeinrichtungen die zutreffenden Anforderungen von ISO 12100 und ISO 14120?',
        interlocking: 'Erfüllen die Verriegelungseinrichtungen der trennenden Schutzeinrichtungen die zutreffenden Anforderungen?',
        fixedTools: 'Lassen sich feststehende trennende Schutzeinrichtungen nur mit Werkzeug demontieren?',
        fixings:
          'Bleiben, wo erforderlich, die Befestigungsmittel beim Abnehmen der trennenden Schutzeinrichtungen an diesen oder an der Maschine?',
        notCloser:
          'Sind die äußeren Schutzeinrichtungen nicht näher an der Gefährdung installiert als der eingeschränkte Raum, abgesehen von den Ausnahmen in ISO 10218-2?',
      },
      guardDimensions: {
        gaps: 'Verhindern der Abstand zwischen Unterkante der trennenden Schutzeinrichtung und Boden sowie andere Öffnungen, dass eine Person über, unter, um oder durch die Schutzeinrichtung hindurch die Gefährdung erreicht?',
        height: 'Ist die trennende Schutzeinrichtung mindestens 1400 mm hoch?',
      },
      interlockedGuards: {
        interlocking: 'Erfüllen die Verriegelungseinrichtungen beweglicher trennender Schutzeinrichtungen die zutreffenden Anforderungen?',
        closedProtects: 'Verhindern bewegliche trennende Schutzeinrichtungen in geschlossener Stellung, dass Bedienpersonen in Gefährdungsbereiche gelangen?',
        opening: 'Öffnen bewegliche trennende Schutzeinrichtungen seitlich oder von der Gefährdung weg und nicht in den geschützten Bereich hinein?',
        safeState: 'Bringt die Verriegelung alle Gefährdungen in einen sicheren Zustand, bevor eine Bedienperson sie erreichen kann?',
        positioned: 'Sind bewegliche trennende Schutzeinrichtungen ordnungsgemäß positioniert?',
        controlGuard:
          'Erfüllen bewegliche trennende Schutzeinrichtungen, die beim Schließen einen Start auslösen (steuernde trennende Schutzeinrichtungen), ISO 14120?',
        performance: 'Erreicht die Verriegelungsfunktion der beweglichen trennenden Schutzeinrichtungen mindestens die Leistungsanforderungen von ISO 10218-2?',
        resetControls: 'Erfüllen die Stellteile zur Rückstellung beweglicher trennender Schutzeinrichtungen die Anforderungen an Start und Wiederanlauf?',
      },
      guardLocking: {
        provided: 'Ist, wo erforderlich, zusätzlich zur Verriegelung eine Zuhaltung vorgesehen?',
        requirements: 'Erfüllt die Zuhaltung die Anforderungen von ISO 10218-2 an Zuhaltungen?',
        processParameters:
          'Erfüllen Prozessparameter, die als Bedingung für Zuhalten und Entsperren dienen, die gleichen funktionalen Sicherheitsanforderungen wie die Verriegelungsfunktion?',
      },
      entrapment: {
        prevented: 'Hat der geschützte Bereich eine Einrichtung, die verhindert, dass eine Person darin eingeschlossen wird?',
      },
      sensitiveEquipment: {
        requirements: 'Erfüllen berührungslos wirkende und druckempfindliche Schutzeinrichtungen die zutreffenden Anforderungen?',
      },
      sensitiveStop: {
        positioned: 'Sind sensitive Schutzeinrichtungen, die einen Sicherheitshalt auslösen, ordnungsgemäß positioniert?',
        fixed: 'Sind sie fest eingebaut und so platziert, dass Bedienpersonen den Detektionsbereich nicht umgehen können?',
        triggers: 'Wird ein Sicherheitshalt ausgelöst, wenn die sensitive Schutzeinrichtung während einer gefährdenden Maschinenfunktion anspricht?',
        noMotion:
          'Verursachen die abgesicherten gefährdenden Maschinenfunktionen nach dem Ansprechen keine gefährdende Bewegung oder Situation, bis die sensitive Schutzeinrichtung zurückgestellt ist?',
        resetNoStart: 'Löst das Rückstellen der sensitiven Schutzeinrichtung allein keine gefährdenden Maschinenfunktionen aus?',
        distanceFormula:
          'Ist der Mindestabstand der sensitiven Schutzeinrichtungen mit der Formel für den Sicherheitsabstand für alle Annäherungsrichtungen berechnet, unter Ansatz der maximalen Reichweite der beweglichen Teile in der jeweiligen Richtung?',
        partlyInside:
          'Falls eine Bedienperson teilweise im geschützten Bereich verbleiben kann: Sind zusätzliche Maßnahmen getroffen, um Gefährdungssituationen zu vermeiden?',
        resetVisibility:
          'Falls eine Person im Bereich vom Stellteil für die Rückstellung aus nicht erkannt werden könnte: Sind ergänzende Maßnahmen getroffen, die das Rückstellen der Wiederanlaufsperre verhindern?',
        deliberateReset: 'Erfordert das Rückstellen der Wiederanlaufsperre eine bewusste Handlung einer Person?',
      },
      presenceSensing: {
        combined: 'Werden Einrichtungen zur Anwesenheitserkennung, die einen Start verhindern, zusammen mit anderen Schutzmaßnahmen verwendet?',
        wholeZone: 'Sind sie so angeordnet und konfiguriert, dass eine Person oder Teile einer Person im gesamten Detektionsbereich erkannt werden?',
        noBypass: 'Sind, wo erforderlich, ergänzende Maßnahmen getroffen, damit der Detektionsbereich nicht umgangen werden kann?',
      },
      manualStations: {
        noFurtherHazards:
          'Sind Maßnahmen vorgesehen, damit Bedienpersonen durch den Betrieb manueller Stationen der Materialhandhabung keinen weiteren Gefährdungen ausgesetzt sind?',
        applicationHazards: 'Sind Maßnahmen getroffen, damit die Bedienperson keinen anwendungsbedingten Gefährdungen ausgesetzt ist?',
      },
      movingStations: {
        motionHazards: 'Sind Maßnahmen getroffen, um die Bedienperson vor Gefährdungen durch Bewegungen der manuellen Stationen zu schützen?',
        gap: 'Beträgt der Zwischenraum zwischen einer beweglichen Station und festen Elementen nicht mehr als 120 mm?',
      },
      sharedWorkspace: {
        coverage:
          'Wo eine Anwesenheitserkennung die Bedienperson im gemeinsamen Arbeitsraum erkennt: Deckt der Detektionsbereich den gesamten gemeinsamen Arbeitsraum ab?',
        unintendedReset:
          'Wo in einem gemeinsamen Arbeitsraum eine Wiederanlaufsperre vorgesehen ist: Sind Maßnahmen gegen ein unbeabsichtigtes Rückstellen vorgesehen?',
        visibleReset:
          'Wo in einem gemeinsamen Arbeitsraum manuell zurückgestellt wird: Ist der gesamte Arbeitsraum von der Rückstellung aus einsehbar oder sind andere Maßnahmen getroffen?',
      },
      openings: {
        dimensions: 'Haben die Öffnungen für die Materialzu- und -abfuhr die erforderlichen Mindestabmessungen?',
        crushing: 'Sind Quetsch- und Schergefahren zwischen dem Material und den Seiten der Öffnungen verhindert?',
        access: 'Ist der Zugang zur Gefährdung durch die Öffnungen verhindert oder wird er erkannt?',
        muting:
          'Lassen berührungslos wirkende Schutzeinrichtungen das Material durch eine Mutingfunktion oder einen Wechsel des Schutzfelds, etwa Blanking, passieren?',
        mutingStandard: 'Erfüllt die Mutingfunktion ISO 13849-1?',
        mutingLevel:
          'Erreichen Muting und Wechsel des Schutzfelds, etwa Blanking, mindestens das funktionale Sicherheitsniveau, das die Risikobeurteilung für die berührungslos wirkende Schutzeinrichtung festlegt?',
      },
      adjacentCells: {
        measures:
          'Sind Maßnahmen vorgesehen, die den Zugang von Bedienpersonen zu Gefährdungen in angrenzenden Zellen verhindern oder diese Gefährdungen zum Stillstand bringen?',
        height: 'Sind feststehende trennende Schutzeinrichtungen, die den Zugang zu Gefährdungen in angrenzenden Zellen verhindern, mindestens 1400 mm hoch?',
        otherMeasures: 'Sind andere Maßnahmen als feststehende trennende Schutzeinrichtungen auf Grundlage der nach ISO 10218-2 geforderten Risikobeurteilung ausgewählt?',
        suspended:
          'Erfüllen Maßnahmen, die für Produktionsabläufe unterdrückt werden, das in der Risikobeurteilung festgelegte funktionale Sicherheitsniveau?',
      },
      endEffectors: {
        energyLoss:
          'Sind Endeffektoren und Werkzeugwechselsysteme so gestaltet und gebaut, dass Verlust oder Wiederkehr der Energieversorgung zu keiner Gefährdung führt?',
        misuse: 'Ist das Werkzeugwechselsystem so gestaltet, dass eine Fehlanwendung zu keiner Gefährdungssituation führt?',
        position: 'Ist der Werkzeugwechsel nur in der Werkzeugwechselposition möglich?',
        loads: 'Hält das Werkzeugwechselsystem den zu erwartenden statischen und dynamischen Belastungen stand?',
      },
      muting: {
        limited: 'Ist das Muting auf unbedingt notwendige Prozesse beschränkt?',
        noUndetected: 'Ist ausgeschlossen, dass eine Person nach Ende des Mutings unerkannt im Gefährdungsbereich bleibt?',
        automatic: 'Wird das Muting automatisch eingeleitet und beendet, sofern die Mutingbedingungen ordnungsgemäß sind?',
        equivalentLevel: 'Erreicht die Mutingfunktion eine gleichwertige Sicherheitsleistung wie die Funktion, die dem Muting unterzogen wird?',
        noDegradation: 'Wirkt sich das Leistungsniveau der Mutingfunktion nicht nachteilig auf das Leistungsniveau der Schutzfunktion aus?',
        failure: 'Ist nach einem Ausfall der Mutingfunktion ein weiteres Muting verhindert, bis der Ausfall behoben ist?',
        information: 'Beschreibt die Benutzerinformation die Mutingeinrichtungen, deren Ort, die erfassten Bereiche und ihre Funktion?',
      },
      suspension: {
        dedicatedMode: 'Haben Aufgaben, die ein Außerkraftsetzen von Schutzeinrichtungen erfordern, eine eigene Betriebsart?',
        lockableSelection: 'Wird diese Betriebsart mit sicherbaren Mitteln gewählt, etwa einem abschließbaren Wahlschalter?',
        automaticRequirements:
          'Wo Schutzeinrichtungen automatisch außer Kraft gesetzt werden: Sind die Anforderungen von ISO 10218-2 an das automatische Außerkraftsetzen erfüllt?',
        othersStopped:
          'Wo Schutzeinrichtungen automatisch außer Kraft gesetzt werden: Befinden sich die für die Aufgabe nicht benötigten Einrichtungen in einem Sicherheitshalt oder unter direkter Steuerung durch die Bedienperson?',
        criticalSituations:
          'Beschreibt die Benutzerinformation die kritischen Situationen, in denen Schutzeinrichtungen manuell außer Kraft gesetzt werden müssen?',
      },
      collaborativeInfo: {
        safeguardsModes:
          'Beschreibt die Benutzerinformation die für den kollaborierenden Betrieb erforderlichen Schutzeinrichtungen und die Betriebsartenwahl?',
      },
      collaborativeRisk: {
        riskAssessment: 'Hat der Integrator eine Risikobeurteilung durchgeführt, die den gesamten Kollaborationsraum berücksichtigt?',
        robots: 'Erfüllen die Roboter im Kollaborationsraum ISO 10218-1?',
        presenceDevices: 'Erfüllen Schutzeinrichtungen zur Anwesenheitserkennung die Leistungsanforderungen von ISO 10218-2?',
        additionalDevices: 'Erfüllen zusätzliche Schutzeinrichtungen im Kollaborationsraum die Leistungsanforderungen von ISO 10218-2?',
        progression:
          'Sind technische Schutzmaßnahmen so gestaltet und eingebaut, dass sie ein weiteres Vordringen einer Person in die Zelle über den Kollaborationsraum hinaus verhindern oder erkennen?',
        stopBeyond: 'Stoppt der Roboter und enden die Gefährdungen, wenn jemand den geschützten Bereich über den Kollaborationsraum hinaus betritt?',
        nonCollaborativeAccess:
          'Verhindern oder erkennen die äußeren Schutzeinrichtungen den Zugang zu dem Teil des geschützten Bereichs, der nicht für den kollaborierenden Betrieb vorgesehen ist?',
        otherMachines:
          'Erfüllen andere angeschlossene Maschinen mit Sicherheitsfunktionen im Kollaborationsraum die Leistungsanforderungen von ISO 10218-2, sofern die Risikobeurteilung nichts anderes vorsieht?',
      },
      collaborativeWorkspace: {
        defined:
          'Ist der Kollaborationsraum, in dem Personen unmittelbar mit dem Roboter zusammenarbeiten, klar gekennzeichnet, etwa durch Bodenmarkierungen oder Schilder?',
        parameters: 'Erfüllen die Roboterparameter zusammen mit den Schutzeinrichtungen die Leistungsanforderungen von ISO 10218-2?',
        severalPersons:
          'Falls mehrere Personen am kollaborierenden Betrieb beteiligt sind: Ist jede Person durch Steuerungsfunktionen geschützt, die die Leistungsanforderungen von ISO 10218-2 erfüllen?',
        easyTasks: 'Ermöglicht der Kollaborationsraum eine leichte Ausführung der Tätigkeiten?',
        equipmentPosition: 'Bringt die Position der Ausrüstung keine zusätzlichen Gefährdungen mit sich?',
        clearance: 'Sind zusätzliche Schutzmaßnahmen gegen Fang- und Quetschgefahren in Bereichen mit weniger als 500 mm Freiraum vorhanden?',
      },
      collaborativeTransition: {
        safe: 'Gefährdet der Wechsel vom autonomen in den kollaborierenden Betrieb und zurück keine Personen?',
      },
      collaborativeFeatures: {
        selected: 'Sind geeignete Sicherheitsmerkmale für den kollaborierenden Roboterbetrieb ausgewählt?',
        failureStop: 'Führt ein erkannter Ausfall eines ausgewählten Sicherheitsmerkmals zu einem Sicherheitshalt?',
        restart:
          'Kann der autonome Betrieb nach einem erkannten Ausfall nur nach einer bewussten Handlung zum Neustart von außerhalb des Kollaborationsraums wieder aufgenommen werden?',
      },
      monitoredStop: {
        stops:
          'Beim sicherheitsbewerteten überwachten Halt: Stoppt der Roboter, sobald eine Person den Kollaborationsraum betritt, und hält er einen sicherheitsbewerteten überwachten Halt bei?',
      },
      handGuiding: {
        handoverStop: 'Wird bei Handführung ein sicherheitsbewerteter überwachter Halt ausgegeben, wenn der Roboter die Übergabeposition erreicht?',
        device: 'Erfüllt die Einrichtung zur Handführung ISO 10218-1?',
        releaseStop: 'Wird ein sicherheitsbewerteter überwachter Halt ausgelöst, wenn die Bedienperson die Einrichtung zur Handführung loslässt?',
      },
      speedSeparation: {
        robots: 'Bei Geschwindigkeits- und Abstandsüberwachung: Erfüllen die Roboter im Kollaborationsraum ISO 10218-1?',
        parameters: 'Sind die Parameter anhand der Risikobeurteilung festgelegt, mit Hinweisen aus ISO/TS 15066?',
      },
      powerForce: {
        robots: 'Bei Leistungs- und Kraftbegrenzung: Erfüllen die Roboter im Kollaborationsraum ISO 10218-1?',
        parameters: 'Sind die Parameter anhand der Risikobeurteilung festgelegt, mit Hinweisen aus ISO/TS 15066?',
      },
      commissioningConcept: {
        interimSafeguards:
          'Beschreibt das Inbetriebnahmekonzept die Schutzmaßnahmen (vorläufige Schutzeinrichtungen), die während der Inbetriebnahme benötigt werden?',
      },
      interimSafeguarding: {
        protects: 'Schützen die vorläufigen Schutzeinrichtungen gegen die in der Risikobeurteilung ermittelten Gefährdungen?',
        barriers: 'Sind mindestens Warnschranken eingebaut, die den eingeschränkten Raum kennzeichnen?',
        documented: 'Sind die vorläufigen Schutzeinrichtungen in der Benutzerinformation beschrieben?',
      },
      startUp: {
        plan: 'Enthält der Plan für das erstmalige Ingangsetzen mindestens die in ISO 10218-2 aufgelisteten Punkte?',
      },
    },
    hints: {},
  },
}
