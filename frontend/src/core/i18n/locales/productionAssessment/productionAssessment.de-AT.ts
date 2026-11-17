// Messages for productionAssessment, merged into the de-AT locale.
export default {
  title: 'Fertigungsbewertung',
  description:
    'Hilf, zukünftige Zeitschätzungen zu verbessern, indem du festhältst, wie dieser Auftrag tatsächlich verlaufen ist.',
  fields: {
    actualMinutesPerPiece: 'Tatsächliche Minuten pro Stück',
    actualSetupMinutes: 'Tatsächliche Rüstminuten',
    complexity: 'Komplexität',
    note: 'Notiz',
  },
  complexity: {
    low: 'Niedrig',
    normal: 'Normal',
    very: 'Sehr komplex',
  },
  rubric: {
    low: 'Unkompliziert, keine Überraschungen.',
    normal: 'Typische Komplexität für diese Art von Teil.',
    very: 'Erforderte Nacharbeit, spezielle Vorrichtungen oder erhebliche Fehlersuche.',
  },
  skip: 'Überspringen',
  submit: 'Bewertung speichern',
  errors: {
    invalid: 'Bitte gib die tatsächlichen Minuten pro Stück ein.',
    unknown: 'Etwas ist schiefgelaufen. Bitte versuche es erneut.',
  },
}
