// Messages for account, merged into the de-AT locale.
export default {
  sessions: {
    title: 'Aktive Sitzungen',
    description:
      'Überall, wo dein Konto derzeit angemeldet ist. Das Beenden einer Sitzung meldet das Gerät sofort ab.',
    current: 'Dieses Gerät',
    unknownDevice: 'Unbekanntes Gerät',
    empty: 'Keine aktiven Sitzungen.',
    columns: {
      actions: 'Aktionen',
      device: 'Gerät',
      ip: 'IP-Adresse',
      signedIn: 'Angemeldet am',
      lastSeen: 'Zuletzt aktiv',
    },
    revokeButton: 'Abmelden',
    revokeConfirm: 'Diese Sitzung abmelden? Das Gerät muss sich erneut anmelden.',
    revokeCurrentConfirm: 'Das ist deine aktuelle Sitzung, du wirst sofort abgemeldet.',
    revoked: 'Sitzung abgemeldet.',
    revokeOthersButton: 'Andere Sitzungen abmelden',
    revokeOthersConfirm:
      'Alle Sitzungen außer dieser abmelden? Alle anderen Geräte müssen sich erneut anmelden.',
    othersRevoked:
      'Keine anderen Sitzungen abgemeldet. | 1 andere Sitzung abgemeldet. | {count} andere Sitzungen abgemeldet.',
    devices: {
      title: 'Vertrauenswürdige Geräte',
      description:
        'Geräte, auf denen die Zwei-Faktor-Authentifizierung bei der Anmeldung übersprungen wird. Nach dem Entfernen wird wieder ein Code verlangt.',
      empty: 'Keine vertrauenswürdigen Geräte.',
      columns: {
        trustedSince: 'Vertraut seit',
        lastUsed: 'Zuletzt verwendet',
        expires: 'Läuft ab',
      },
      revokeButton: 'Entfernen',
      revokeConfirm:
        'Dieses Gerät entfernen? Bei der nächsten Anmeldung wird wieder ein 2FA-Code verlangt.',
      revoked: 'Vertrauenswürdiges Gerät entfernt.',
      revokeAllButton: 'Alle entfernen',
      revokeAllConfirm:
        'Alle vertrauenswürdigen Geräte entfernen? Bei der nächsten Anmeldung wird überall wieder ein 2FA-Code verlangt.',
      allRevoked: 'Alle vertrauenswürdigen Geräte entfernt.',
    },
    errors: {
      loadFailed: 'Sitzungen konnten nicht geladen werden.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  passkeys: {
    title: 'Passkeys',
    description:
      'Melde dich ohne Passwort und Code an: Windows Hello, Touch ID oder ein Sicherheitsschlüssel bestätigt, dass du es bist. Jedes Gerät hat seinen eigenen Passkey.',
    empty: 'Noch keine Passkeys.',
    thisDevice: 'Dieses Gerät',
    synced: 'Synchronisiert',
    columns: {
      actions: 'Aktionen',
      name: 'Name',
      added: 'Hinzugefügt',
      lastUsed: 'Zuletzt verwendet',
    },
    addButton: 'Passkey hinzufügen',
    unsupported:
      'Dieser Browser kann hier keine Passkeys verwenden. Passkeys brauchen https oder localhost.',
    systemUser: 'Das Systemkonto meldet sich nur mit Passwort und Code an.',
    added: 'Passkey hinzugefügt.',
    renameButton: 'Umbenennen',
    renamed: 'Passkey umbenannt.',
    renameDialog: {
      title: 'Passkey umbenennen',
    },
    removeButton: 'Entfernen',
    removeConfirm:
      'Den Passkey „{name}“ entfernen? Dieses Gerät fragt dann wieder nach deinem Passwort.',
    removed: 'Passkey entfernt.',
    removeAllButton: 'Alle Passkeys entfernen',
    removeAllConfirm:
      'Alle Passkeys deines Kontos entfernen? Jedes Gerät fragt dann wieder nach deinem Passwort.',
    allRemoved: 'Keine Passkeys entfernt. | 1 Passkey entfernt. | {count} Passkeys entfernt.',
    addDialog: {
      title: 'Passkey hinzufügen',
      description:
        'Bestätige dein Passwort und folge dann der Abfrage deines Geräts, um den Passkey anzulegen.',
      name: 'Name',
      password: 'Aktuelles Passwort',
      submit: 'Passkey hinzufügen',
    },
    errors: {
      loadFailed: 'Passkeys konnten nicht geladen werden.',
      wrongPassword: 'Das Passwort ist nicht korrekt.',
      dismissed: 'Die Abfrage wurde abgebrochen. Versuche es erneut, sobald du bereit bist.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
  twoFactor: {
    title: 'Zwei-Faktor-Authentifizierung',
    status: {
      enabled: 'Aktiviert',
      disabled: 'Deaktiviert',
      enabledHint: 'Dein Konto ist mit der Zwei-Faktor-Authentifizierung geschützt.',
      disabledHint: 'Füge deinem Konto eine zusätzliche Sicherheitsebene hinzu.',
    },
    setup: {
      open: '2FA aktivieren',
      description:
        'Scanne den QR-Code mit deiner Authenticator-App (z.B. Google Authenticator, Authy) und gib den Code zur Bestätigung ein.',
      secret: 'Manueller Eingabeschlüssel',
      code: 'Bestätigungscode',
      confirm: 'Bestätigen & aktivieren',
      passwordDescription: 'Bestätige dein Passwort, um die Zwei-Faktor-Authentifizierung einzurichten.',
      password: 'Aktuelles Passwort',
      continue: 'Weiter',
    },
    disable: {
      open: '2FA deaktivieren',
      description:
        'Gib deinen aktuellen Authentifizierungscode ein, um die Zwei-Faktor-Authentifizierung zu deaktivieren.',
      code: 'Authentifizierungscode',
      submit: '2FA deaktivieren',
    },
    errors: {
      invalidCode: 'Ungültiger Code. Bitte versuche es erneut.',
      wrongPassword: 'Das Passwort ist nicht korrekt.',
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
    success: {
      enabled: 'Zwei-Faktor-Authentifizierung wurde aktiviert.',
    },
    systemUserMandatory:
      'Die Zwei-Faktor-Authentifizierung ist für das Systemkonto verpflichtend. Sie kann nur auf dem Server mit `admin reset-totp system` zurückgesetzt werden; bei der nächsten Anmeldung musst du dich erneut einrichten.',
  },
  pat: {
    title: 'Persönliche Zugriffstoken',
    description:
      'Selbstverwaltete Token, die sich als du authentifizieren, eingeschränkt auf die bei der Erstellung gewählten Berechtigungen.',
    systemUserNoCreate: 'Das Systemkonto kann keine persönlichen Zugriffstoken erstellen.',
    createButton: 'Token erstellen',
    createAddinButton: 'SolidWorks-Add-in-Token erstellen',
    createPdmAddinButton: 'PDM-Add-in-Token erstellen',
    createdTitle: 'Persönlicher Zugriffstoken erstellt',
    revokeAllButton: 'Alle widerrufen',
    revokeAllConfirm: 'Alle deine persönlichen Zugriffstoken widerrufen?',
    revokedAll: 'Keine Token widerrufen. | 1 Token widerrufen. | {count} Token widerrufen.',
    revokeButton: 'Widerrufen',
    revokeConfirm: 'Token "{name}" widerrufen? Dies kann nicht rückgängig gemacht werden.',
    revoked: 'Token widerrufen.',
    usageLogButton: 'Nutzungsprotokoll anzeigen',
    usageLogTitle: 'Nutzungsprotokoll, {name}',
    noUsage: 'Noch keine Nutzung erfasst.',
    usageColumns: {
      status: 'Status',
      method: 'Methode',
      path: 'Pfad',
      calledAt: 'Aufgerufen am',
    },
    columns: {
      actions: 'Aktionen',
      name: 'Name',
      prefix: 'Präfix',
      permissions: 'Berechtigungen',
      created: 'Erstellt',
      expires: 'Läuft ab',
    },
    fields: {
      name: 'Name',
      permissions: 'Berechtigungen',
      expiresInDays: 'Läuft ab in (Tage)',
      expiresInDaysHint: 'Maximal {days} Tage, festgelegt im Tab Sicherheit.',
      expiresInDaysNoCapHint: 'Der Tab Sicherheit legt kein Maximum fest.',
      neverExpires: 'Läuft nie ab',
      neverExpiresCapped:
        'Nicht verfügbar: Der Tab Sicherheit begrenzt Token auf {days} Tage, daher braucht jeder Token ein Ablaufdatum.',
      password: 'Aktuelles Passwort',
      passwordHint: 'Ein Token funktioniert auch nach dem Abmelden weiter, daher braucht er dein Passwort.',
    },
    addinMissingPermission:
      'Du kannst {permissions} noch nicht vergeben, daher wird der Add-in-Token ohne diese Berechtigung erstellt. Frag eine Administratorin oder einen Administrator um Zugriff.',
    neverExpiresWarning:
      'Dieser Token läuft nie ab, bis er manuell widerrufen wird. Erwäge ein Ablaufdatum festzulegen.',
    neverExpires: 'Läuft nie ab',
    expired: 'Abgelaufen',
    secretWarning: 'Kopiere diesen Token jetzt, er wird nicht erneut angezeigt.',
    copied: 'Token in die Zwischenablage kopiert.',
    saveFailed: 'Erstellen des Tokens fehlgeschlagen.',
    expiryRequired: 'Leg ein Ablaufdatum fest: Token dürfen höchstens {days} Tage gelten.',
    lifetimeExceeded: 'Das Ablaufdatum liegt zu weit in der Zukunft: Token dürfen höchstens {days} Tage gelten.',
    wrongPassword: 'Das Passwort ist nicht korrekt.',
    empty: 'Noch keine persönlichen Zugriffstoken vorhanden.',
    filters: {
      notExpired: 'Noch nicht abgelaufen',
      dateRange: 'Zeitraum',
    },
    errors: {
      unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
    },
  },
}
