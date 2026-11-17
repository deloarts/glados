/**
 * The version of the checklist definitions a saved checklist was filled in
 * against. Answers are stored by item id, so adding, removing or reordering
 * items keeps them attached to the right item; raise the version when the
 * meaning of an existing item changes, so a checklist saved before can tell.
 */
export const CHECKLIST_DEFINITION_VERSION = 1
