/** The views of a sequence page, part of its address. */
export const SEQUENCE_VIEWS = ['editor', 'initial', 'diagram', 'grafcet'] as const
export type SequenceView = (typeof SEQUENCE_VIEWS)[number]

export function isSequenceView(value: unknown): value is SequenceView {
  return typeof value === 'string' && (SEQUENCE_VIEWS as readonly string[]).includes(value)
}
