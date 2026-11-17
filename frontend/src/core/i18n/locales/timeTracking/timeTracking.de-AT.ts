// Messages for timeTracking, merged into the de-AT locale.
export default {
  tab: 'Zeiterfassung',
  providerFallback: 'Zeiterfassung',
  reload: 'Neu laden',
  previousMonth: 'Vorheriger Monat',
  nextMonth: 'Nächster Monat',
  currentMonth: 'Aktueller Monat',
  empty: {
    missing: 'Gib deine {provider}-Zugangsdaten unter Mein Konto ein, um deine Zeitdaten hier zu sehen.',
    undecryptable:
      'Deine gespeicherten {provider}-Zugangsdaten können nicht mehr gelesen werden. Gib sie unter Mein Konto erneut ein.',
    binding_changed:
      'Der Zeiterfassungsserver oder -schlüssel hat sich geändert. Gib dein Passwort unter Mein Konto erneut ein.',
    auth_failed:
      '{provider} hat deine gespeicherten Zugangsdaten abgelehnt. Gib sie unter Mein Konto erneut ein.',
    consent_outdated:
      'Der Einwilligungstext hat sich geändert. Bestätige ihn, um deine Zeitdaten zu sehen, oder öffne Mein Konto.',
    openAccount: 'Mein Konto öffnen',
    monthNotAllowed: 'Dein Zeiterfassungskonto darf das Monatsjournal nicht lesen.',
    yearNotAllowed: 'Dein Zeiterfassungskonto darf das Jahresjournal nicht lesen.',
  },
  totals: {
    title: 'Überblick',
    clockedIn: 'Eingestempelt',
    clockedOut: 'Ausgestempelt',
    firstIn: 'Erstes Kommen',
    workedToday: 'Heute bisher gearbeitet',
    targetToday: 'Sollzeit heute',
    dayBalance: 'Tagessaldo',
    runningBalance: 'Laufender Saldo',
    targetReachedAt: 'Sollzeit erreicht um',
    month: 'Monat',
    worked: 'Gearbeitet',
    target: 'Soll',
    monthBalance: 'Monatssaldo',
    dataAsOf: 'Datenstand {time}',
  },
  accounts: {
    title: 'Konten',
    empty: 'Keine Konten für diesen Monat.',
    account: 'Konto',
    opening: 'Anfang',
    change: 'Veränderung',
    closing: 'Ende',
  },
  table: {
    empty: 'Keine Tage in diesem Monat.',
    date: 'Datum',
    shift: 'Schicht',
    firstIn: 'Kommen',
    lastOut: 'Gehen',
    bookings: 'Buchungen',
    showBookings: 'Buchungen anzeigen',
    worked: 'Gearbeitet',
    target: 'Soll',
    dayBalance: 'Tagessaldo',
    runningBalance: 'Laufender Saldo',
    status: 'Status',
    in: 'Kommen',
    out: 'Gehen',
  },
  dayStatus: {
    normal: 'Normal',
    shift_free: 'Schichtfrei',
    holiday: 'Feiertag',
    absence: 'Abwesenheit',
    open: 'Offen',
  },
  stats: {
    dailyTitle: 'Gearbeitet und Soll pro Tag',
    balanceTitle: 'Laufender Saldo',
    weekdayTitle: 'Durchschnitt je Wochentag',
    yearTitle: 'Jahr {year}',
    yearHours: 'Gearbeitet und Soll pro Monat',
    yearBalance: 'Saldo am Monatsende',
    noData: 'Für diesen Zeitraum gibt es noch keine Daten.',
    series: {
      worked: 'Gearbeitet',
      over: 'Über Soll',
      short: 'Unter Soll',
      target: 'Soll',
    },
    weekday: 'Wochentag',
    averageWorked: 'Durchschnittlich gearbeitet',
    averageFirstIn: 'Durchschnittliches Kommen',
    averageLastOut: 'Durchschnittliches Gehen',
    averageBounds: 'Im Durchschnitt bist du um {firstIn} gekommen und um {lastOut} gegangen.',
    kpi: {
      daysWorked: 'Arbeitstage',
      averageDay: 'Durchschnittlicher Tag',
      longestDay: 'Längster Tag',
      overtimeDays: 'Tage über Soll',
    },
  },
  consent: {
    title: 'Einwilligung zum Zeiterfassungszugriff',
    intro:
      'Bevor Glados deine {provider}-Zugangsdaten verwendet, lies bitte Folgendes und bestätige es.',
    readOnRequest:
      'Glados liest deine Zeitdaten nur dann aus dem Zeiterfassungssystem, wenn du die Seite Zeiterfassung öffnest, und zeigt sie nur dir an.',
    nothingStored: 'Keine deiner Zeitdaten werden in Glados gespeichert.',
    encrypted: 'Deine Zugangsdaten werden verschlüsselt gespeichert.',
    sealed:
      'Dein Passwort wird für den Zeiterfassungsdienst versiegelt, sodass Glados selbst es nicht lesen kann.',
    adminsCannotSee: 'Administratoren können weder dein Passwort noch deine Zeitdaten sehen.',
    withdraw:
      'Du kannst deine Einwilligung jederzeit widerrufen, indem du deine Zugangsdaten unter Mein Konto entfernst.',
    privacyPolicyHint: 'Weitere Informationen:',
    privacyPolicy: 'Datenschutzerklärung',
    agree: 'Ich habe das gelesen und bin einverstanden.',
    confirm: 'Bestätigen',
    saveFailed: 'Einwilligung nicht gespeichert',
  },
  errors: {
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    loadFailed: 'Zeitdaten konnten nicht geladen werden',
    notEnabled: 'Die Zeiterfassung ist nicht aktiviert.',
    credentialsMissing:
      'Es sind keine verwendbaren Zeiterfassungs-Zugangsdaten gespeichert. Gib deine Zugangsdaten unter Mein Konto ein.',
    authenticationFailed:
      'Das Zeiterfassungssystem hat die Zugangsdaten abgelehnt. Prüfe deinen Benutzernamen und dein Passwort.',
    permissionDenied: 'Dein Zeiterfassungskonto darf diese Daten nicht lesen.',
    credentialsNotAllowed:
      'Gemeinsame Konten und Systemkonten können keine Zeiterfassungs-Zugangsdaten haben.',
    provider:
      'Das Zeiterfassungssystem hat mit einem Fehler geantwortet. Bitte versuche es später erneut.',
    unavailable:
      'Das Zeiterfassungssystem ist gerade nicht erreichbar. Bitte versuche es später erneut.',
    rateLimited: 'Zu viele Versuche in kurzer Zeit. Bitte warte kurz und versuche es erneut.',
    userAlreadyLinked:
      'Dieser Zeiterfassungsbenutzer ist bereits mit einem anderen Glados-Konto verknüpft.',
    consentRequired: 'Bitte bestätige zuerst den aktuellen Einwilligungstext.',
    periodInvalid: 'Zukünftige Monate und Jahre können nicht angezeigt werden.',
    notConfigured: 'Gib zuerst die Dienst-URL und den API-Schlüssel ein.',
    bindingChanged:
      'Der Zeiterfassungsserver oder -schlüssel hat sich geändert. Gib dein Passwort unter Mein Konto erneut ein.',
    keyChanged:
      'Der Dienst verwendet jetzt einen anderen Zugangsdaten-Schlüssel. Teste die Verbindung erneut.',
  },
}
