// Messages for login, merged into the en-GB locale.
export default {
  title: 'Login',
  username: 'Username',
  password: 'Password',
  submit: 'Sign in',
  errors: {
    invalidCredentials: 'Incorrect username or password.',
    sessionExpired: 'Your session has expired. Please sign in again.',
    inactive: 'This account is inactive.',
    localLoginDisabled: 'Password sign-in is currently disabled. Contact an administrator.',
    lockedOut: 'Too many failed attempts. This account is temporarily locked.',
    lockedOutFor:
      'Too many failed attempts. Try again shortly. | Too many failed attempts. Try again in 1 minute. | Too many failed attempts. Try again in {count} minutes.',
    maintenance: 'Sign-in is unavailable during maintenance.',
    maintenanceLockout: 'You were signed out because the system entered maintenance mode.',
    unknown: 'Something went wrong. Please try again.',
  },
  maintenance: {
    title: 'Maintenance mode',
    defaultMessage: 'The system is currently under maintenance. Please try again later.',
  },
  chooser: {
    switchUser: 'Switch User',
    forget: 'Forget',
    otherAccounts: 'Other accounts on this device',
    usePassword: 'Enter your password to sign in.',
  },
  passkey: {
    signIn: 'Sign In With Passkey',
    // Default names of a passkey set up from the login page.
    deviceName: {
      windowsHello: 'Windows Hello',
      touchId: 'Touch ID',
      generic: 'Passkey',
    },
    offer: {
      description:
        'Next time, sign in on this device without your password: confirm with your face, fingerprint or PIN.',
      accept: {
        windowsHello: 'Set Up Windows Hello',
        touchId: 'Set Up Touch ID',
        generic: 'Set Up Passkey',
      },
      notNow: 'Not Now',
      dismissed: 'The setup was cancelled. Try again, or continue without it.',
      failed: 'The passkey could not be set up. You can try again later under Account, Passkeys.',
    },
    errors: {
      rejected: 'This passkey was not accepted. Enter your password instead.',
      passwordRequired:
        'Sign in with your password once to confirm your directory account, then the passkey works again.',
      unknown: 'Signing in with the passkey failed. Enter your password instead.',
    },
  },
  totpSetup: {
    description:
      'Two-factor authentication is required. Scan this code with your authenticator app to finish setting up {name}.',
    qrAlt: 'Two-factor authentication QR code',
    manualEntry: "Can't scan the code? Enter this key manually",
    code: 'Enter the 6-digit code to confirm',
  },
  totp: {
    description: 'Enter the 6-digit code from your authenticator app.',
    code: 'Authentication Code',
    submit: 'Verify',
    back: 'Back',
    trustDevice: "Don't ask again on this device for {days} days",
    errors: {
      invalidCode: 'Invalid code. Please try again.',
      expired: 'Session expired. Please log in again.',
      unknown: 'Something went wrong. Please try again.',
    },
  },
}
