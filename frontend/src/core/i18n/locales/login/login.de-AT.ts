// Messages for login, merged into the de-AT locale.
export default {
  title: 'Login',
  username: 'Benutzername',
  password: 'Passwort',
  submit: 'Anmelden',
  errors: {
    invalidCredentials: 'Benutzername oder Passwort ist falsch.',
    sessionExpired: 'Deine Sitzung ist abgelaufen. Bitte melde dich erneut an.',
    inactive: 'Dieses Konto ist inaktiv.',
    localLoginDisabled:
      'Die Anmeldung mit Passwort ist derzeit deaktiviert. Bitte wende dich an einen Administrator.',
    lockedOut: 'Zu viele fehlgeschlagene Versuche. Dieses Konto ist vorübergehend gesperrt.',
    lockedOutFor:
      'Zu viele fehlgeschlagene Versuche. Versuche es in Kürze erneut. | Zu viele fehlgeschlagene Versuche. Versuche es in 1 Minute erneut. | Zu viele fehlgeschlagene Versuche. Versuche es in {count} Minuten erneut.',
    maintenance: 'Die Anmeldung ist während der Wartung nicht möglich.',
    maintenanceLockout:
      'Du wurdest abgemeldet, weil das System in den Wartungsmodus gewechselt ist.',
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
  maintenance: {
    title: 'Wartungsmodus',
    defaultMessage:
      'Das System befindet sich derzeit in Wartung. Bitte versuche es später erneut.',
  },
  chooser: {
    switchUser: 'Benutzer wechseln',
    forget: 'Vergessen',
    otherAccounts: 'Weitere Konten auf diesem Gerät',
    usePassword: 'Gib dein Passwort ein, um dich anzumelden.',
  },
  passkey: {
    signIn: 'Mit Passkey anmelden',
    deviceName: {
      windowsHello: 'Windows Hello',
      touchId: 'Touch ID',
      generic: 'Passkey',
    },
    offer: {
      description:
        'Melde dich auf diesem Gerät beim nächsten Mal ohne Passwort an: Du bestätigst einfach mit Gesicht, Fingerabdruck oder PIN.',
      accept: {
        windowsHello: 'Windows Hello einrichten',
        touchId: 'Touch ID einrichten',
        generic: 'Passkey einrichten',
      },
      notNow: 'Nicht jetzt',
      dismissed: 'Die Einrichtung wurde abgebrochen. Versuche es erneut oder mach ohne weiter.',
      failed:
        'Der Passkey konnte nicht eingerichtet werden. Du kannst es später unter Konto, Passkeys erneut versuchen.',
    },
    errors: {
      rejected: 'Dieser Passkey wurde nicht akzeptiert. Gib stattdessen dein Passwort ein.',
      passwordRequired:
        'Melde dich einmal mit deinem Passwort an, um dein Verzeichniskonto zu bestätigen. Danach funktioniert der Passkey wieder.',
      unknown: 'Die Anmeldung mit dem Passkey ist fehlgeschlagen. Gib stattdessen dein Passwort ein.',
    },
  },
  totpSetup: {
    description:
      'Zwei-Faktor-Authentifizierung ist erforderlich. Scanne diesen Code mit deiner Authenticator-App, um die Einrichtung für {name} abzuschließen.',
    qrAlt: 'QR-Code für die Zwei-Faktor-Authentifizierung',
    manualEntry: 'Code lässt sich nicht scannen? Gib diesen Schlüssel manuell ein',
    code: 'Gib den 6-stelligen Code zur Bestätigung ein',
  },
  totp: {
    description: 'Gib den 6-stelligen Code aus deiner Authenticator-App ein.',
    code: 'Authentifizierungscode',
    submit: 'Bestätigen',
    back: 'Zurück',
    trustDevice: 'Auf diesem Gerät {days} Tage nicht mehr fragen',
    errors: {
      invalidCode: 'Ungültiger Code. Bitte versuche es erneut.',
      expired: 'Sitzung abgelaufen. Bitte melde dich erneut an.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
}
