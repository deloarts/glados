// Messages for importing and exporting template files in the settings editors, merged into the en-GB locale.
export default {
  importFile: 'Import from file',
  exportFile: 'Export to file',
  imported: 'Loaded {files}',
  importedReview: 'Check the values and save to keep them.',
  importedIgnored: 'Check the values and save to keep them. Not used: {keys}.',
  importFailed: 'Import failed',
  errors: {
    invalidJson: '{file} is not a valid JSON file.',
    notTemplate: '{file} is not a Glados template file.',
    wrongKind: '{file} holds a different kind of template ({detail}).',
    unsupportedVersion: '{file} uses format version {detail}, which this version of Glados cannot read.',
    invalidContent: '{file} has an invalid value at "{detail}".',
    wrongTarget: '{file} belongs to {detail}, not to this template.',
    readFailed: '{file} could not be read.',
  },
  mail: {
    importTemplates: 'Import templates',
    dialogTitle: 'Import mail templates',
    intro:
      'Pick one or more HTML files named after the template and the language, such as welcome.enGB.html. The title of each file becomes the subject.',
    columns: {
      file: 'File',
      template: 'Template',
      language: 'Language',
      status: 'Status',
    },
    status: {
      new: 'New',
      replaces: 'Replaces the current template',
      badName: 'Name not recognised',
      unknownKind: 'Unknown template',
      unknownLanguage: 'Language not enabled',
      duplicate: 'Picked twice, the last one counts',
    },
    importAction: 'Import one template | Import {count} templates',
    importedCount: 'One mail template imported. | {count} mail templates imported.',
    nothingToImport: 'None of the picked files can be imported.',
    saveFailed: 'The templates for {kind} could not be saved.',
  },
  pdm: {
    importVariableMaps: 'Import variable maps',
    exportVariableMaps: 'Export variable maps',
  },
}
