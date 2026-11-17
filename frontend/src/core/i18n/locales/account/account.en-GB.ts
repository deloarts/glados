// Messages for account, merged into the en-GB locale.
export default {
  sessions: {
    title: 'Active Sessions',
    description:
      'Everywhere your account is currently signed in. Ending a session signs that device out immediately.',
    current: 'This device',
    unknownDevice: 'Unknown device',
    empty: 'No active sessions.',
    columns: {
      actions: 'Actions',
      device: 'Device',
      ip: 'IP Address',
      signedIn: 'Signed In',
      lastSeen: 'Last Active',
    },
    revokeButton: 'Sign Out',
    revokeConfirm: 'Sign this session out? The device will need to log in again.',
    revokeCurrentConfirm: 'This is your current session, you will be signed out immediately.',
    revoked: 'Session signed out.',
    revokeOthersButton: 'Sign Out Other Sessions',
    revokeOthersConfirm:
      'Sign out every session except this one? All other devices will need to log in again.',
    othersRevoked:
      'No other sessions signed out. | 1 other session signed out. | {count} other sessions signed out.',
    devices: {
      title: 'Trusted Devices',
      description:
        'Devices where two-factor authentication is skipped at sign-in. Removing a device makes it ask for a code again.',
      empty: 'No trusted devices.',
      columns: {
        trustedSince: 'Trusted Since',
        lastUsed: 'Last Used',
        expires: 'Expires',
      },
      revokeButton: 'Remove',
      revokeConfirm:
        'Remove this trusted device? It will ask for a 2FA code at the next sign-in.',
      revoked: 'Trusted device removed.',
      revokeAllButton: 'Remove All',
      revokeAllConfirm:
        'Remove every trusted device? All devices will ask for a 2FA code at the next sign-in.',
      allRevoked: 'All trusted devices removed.',
    },
    errors: {
      loadFailed: 'Could not load sessions.',
      unknown: 'Something went wrong. Please try again.',
    },
  },
  passkeys: {
    title: 'Passkeys',
    description:
      'Sign in without password and code: Windows Hello, Touch ID or a security key confirms it is you. Each device has its own passkey.',
    empty: 'No passkeys yet.',
    thisDevice: 'This device',
    synced: 'Synced',
    columns: {
      actions: 'Actions',
      name: 'Name',
      added: 'Added',
      lastUsed: 'Last Used',
    },
    addButton: 'Add Passkey',
    unsupported: 'This browser cannot use passkeys here. Passkeys need https or localhost.',
    systemUser: 'The system account signs in with its password and code only.',
    added: 'Passkey added.',
    renameButton: 'Rename',
    renamed: 'Passkey renamed.',
    renameDialog: {
      title: 'Rename Passkey',
    },
    removeButton: 'Remove',
    removeConfirm: 'Remove the passkey "{name}"? That device will ask for your password again.',
    removed: 'Passkey removed.',
    removeAllButton: 'Remove All Passkeys',
    removeAllConfirm:
      'Remove every passkey of your account? Every device will ask for your password again.',
    allRemoved: 'No passkeys removed. | 1 passkey removed. | {count} passkeys removed.',
    addDialog: {
      title: 'Add Passkey',
      description:
        'Confirm your password, then follow the prompt of your device to create the passkey.',
      name: 'Name',
      password: 'Current Password',
      submit: 'Add Passkey',
    },
    errors: {
      loadFailed: 'Could not load passkeys.',
      wrongPassword: 'The password is not correct.',
      dismissed: 'The prompt was cancelled. Try again when you are ready.',
      unknown: 'Something went wrong. Please try again.',
    },
  },
  twoFactor: {
    title: 'Two-Factor Authentication',
    status: {
      enabled: 'Enabled',
      disabled: 'Disabled',
      enabledHint: 'Your account is protected with two-factor authentication.',
      disabledHint: 'Add an extra layer of security to your account.',
    },
    setup: {
      open: 'Enable 2FA',
      description:
        'Scan the QR code with your authenticator app (e.g. Google Authenticator, Authy), then enter the code below to confirm.',
      secret: 'Manual entry key',
      code: 'Verification Code',
      confirm: 'Confirm & Enable',
      passwordDescription: 'Confirm your password to set up two-factor authentication.',
      password: 'Current Password',
      continue: 'Continue',
    },
    disable: {
      open: 'Disable 2FA',
      description: 'Enter your current authentication code to disable two-factor authentication.',
      code: 'Authentication Code',
      submit: 'Disable 2FA',
    },
    errors: {
      invalidCode: 'Invalid code. Please try again.',
      wrongPassword: 'The password is not correct.',
      unknown: 'Something went wrong. Please try again.',
    },
    success: {
      enabled: 'Two-factor authentication has been enabled.',
    },
    systemUserMandatory:
      'Two-factor authentication is mandatory for the system account. It can only be reset from the server with `admin reset-totp system`; you will be asked to enrol again at the next sign-in.',
  },
  pat: {
    title: 'Personal Access Tokens',
    description:
      'Self-service tokens that authenticate as you, scoped to a permission subset you choose at creation.',
    systemUserNoCreate: 'The system account cannot create personal access tokens.',
    createButton: 'Create Token',
    createAddinButton: 'Create SolidWorks Add-in Token',
    createPdmAddinButton: 'Create PDM Add-in Token',
    createdTitle: 'Personal Access Token Created',
    revokeAllButton: 'Revoke All',
    revokeAllConfirm: 'Revoke all of your personal access tokens?',
    revokedAll: 'No tokens revoked. | Revoked 1 token. | Revoked {count} tokens.',
    revokeButton: 'Revoke',
    revokeConfirm: 'Revoke token "{name}"? This cannot be undone.',
    revoked: 'Token revoked.',
    usageLogButton: 'View Usage Log',
    usageLogTitle: 'Usage Log, {name}',
    noUsage: 'No usage recorded yet.',
    usageColumns: {
      status: 'Status',
      method: 'Method',
      path: 'Path',
      calledAt: 'Called At',
    },
    columns: {
      actions: 'Actions',
      name: 'Name',
      prefix: 'Prefix',
      permissions: 'Permissions',
      created: 'Created',
      expires: 'Expires',
    },
    fields: {
      name: 'Name',
      permissions: 'Permissions',
      expiresInDays: 'Expires In (days)',
      expiresInDaysHint: 'Maximum {days} days, set on the Security tab.',
      expiresInDaysNoCapHint: 'The Security tab sets no maximum.',
      neverExpires: 'Never expires',
      neverExpiresCapped:
        'Not available: the Security tab limits tokens to {days} days, so every token needs an expiry.',
      password: 'Current Password',
      passwordHint: 'A token keeps working after you sign out, so it needs your password.',
    },
    addinMissingPermission:
      'Your account cannot grant {permissions} yet, so the add-in token is created without it. Ask an administrator for access.',
    neverExpiresWarning:
      'This token will never expire until manually revoked. Consider setting an expiry.',
    neverExpires: 'Never expires',
    expired: 'Expired',
    secretWarning: 'Copy this token now, it will not be shown again.',
    copied: 'Token copied to clipboard.',
    saveFailed: 'Creating the token failed.',
    expiryRequired: 'Set an expiry: tokens may live at most {days} days.',
    lifetimeExceeded: 'The expiry is too far away: tokens may live at most {days} days.',
    wrongPassword: 'The password is not correct.',
    empty: 'No personal access tokens yet.',
    filters: {
      notExpired: 'Not yet expired',
      dateRange: 'Date range',
    },
    errors: {
      unknown: 'Something went wrong. Please try again.',
    },
  },
}
