// Messages for productionAssessment, merged into the en-GB locale.
export default {
  title: 'Manufacturing Assessment',
  description: 'Help improve future time estimates by recording how this order actually went.',
  fields: {
    actualMinutesPerPiece: 'Actual Minutes per Piece',
    actualSetupMinutes: 'Actual Setup Minutes',
    complexity: 'Complexity',
    note: 'Note',
  },
  complexity: {
    low: 'Low',
    normal: 'Normal',
    very: 'Very Complex',
  },
  rubric: {
    low: 'Straightforward, no surprises.',
    normal: 'Typical complexity for this kind of part.',
    very: 'Required rework, special fixturing, or significant troubleshooting.',
  },
  skip: 'Skip',
  submit: 'Save Assessment',
  errors: {
    invalid: 'Please enter the actual minutes per piece.',
    unknown: 'Something went wrong. Please try again.',
  },
}
