import type { SequenceActionQualifier, SequenceConditionTerm, SequenceStep, SequenceAction } from '../types/sequence'
import { TARGET_END, TARGET_NEXT } from '../types/sequence'

/**
 * Lays out a sequence as a GRAFCET chart (IEC 60848): the steps top down in
 * their order, the first one the initial step with a double frame, each
 * step's actions as boxes to its right with their qualifier, a device
 * action with the device and its command in cells of their own, and below it
 * its transitions as bars with their conditions, one term per line below
 * each other, all of which must hold. The action boxes and the branches
 * grow with their texts, so no text is cut off. Several
 * transitions of a step are an alternative branch (a single line
 * divergence); the branches that go on to the next step meet again above
 * it. A transition to any other step or to the end ends in an arrow with
 * its destination, the way large charts reference steps, and the step it
 * leads to names where it is entered from.
 */

export type Point = [number, number]

export interface GrafcetStepBox {
  key: string
  number: number
  x: number
  y: number
  initial: boolean
  timeoutMs: number | null
  /** The steps that lead here by a jump, such as [3] for a loop from step 3. */
  enteredFrom: number[]
}

export interface GrafcetActionBox {
  x: number
  y: number
  height: number
  qualifier: 'S' | 'N' | 'P'
  /** The device a device action moves, in a cell of its own; null for a text action. */
  device: string | null
  /** The command of a device action, or the text of a text action across both cells. */
  text: string
  condition: string | null
}

export interface GrafcetTransitionBar {
  x: number
  y: number
  /** The whole condition on one line, or 1 for none. */
  label: string
  /** The terms of the condition, one per line, or [1] for none. */
  lines: string[]
}

export interface GrafcetJump {
  x: number
  y: number
  /** The destination step number, or null for the end of the sequence. */
  target: number | null
}

export interface GrafcetLayout {
  steps: GrafcetStepBox[]
  actions: GrafcetActionBox[]
  transitions: GrafcetTransitionBar[]
  links: Point[][]
  jumps: GrafcetJump[]
  /** The width of every action box, wide enough for the longest text. */
  actionWidth: number
  /** The width of the device cell of every device action, wide enough for the longest name. */
  deviceWidth: number
  width: number
  height: number
}

export interface GrafcetActionText {
  device: string | null
  text: string
}

export interface GrafcetText {
  action: (action: SequenceAction, stepKey: string) => GrafcetActionText
  condition: (terms: readonly SequenceConditionTerm[], stepKey: string) => string
}

export const GRAFCET = {
  step: 36,
  center: 120,
  actionGap: 28,
  actionWidth: 300,
  // The qualifier cell, and the room between a cell's line and its text.
  qualifierWidth: 22,
  cellPadding: 6,
  actionHeight: 26,
  actionConditionHeight: 14,
  transitionGap: 22,
  branchWidth: 260,
  jumpHeight: 26,
  conditionLineHeight: 14,
  // The estimated width of a character of the chart's text (12px) and of
  // its notes (10px), from which boxes and branches take their widths.
  charWidth: 6.6,
  noteCharWidth: 5.5,
  stepGap: 14,
  margin: 16,
} as const

const QUALIFIER: Record<SequenceActionQualifier, 'S' | 'N' | 'P'> = { stored: 'S', continuous: 'N', pulse: 'P' }

export function layoutGrafcet(steps: readonly SequenceStep[], text: GrafcetText): GrafcetLayout {
  const G = GRAFCET
  const numbers = new Map(steps.map((step, index) => [step.key, index + 1]))
  const enteredFrom = new Map<string, number[]>()
  steps.forEach((step, index) => {
    for (const transition of step.transitions ?? []) {
      const target = transition.target ?? TARGET_NEXT
      if (target === TARGET_NEXT || target === TARGET_END) continue
      if (numbers.get(target) === index + 2) continue
      enteredFrom.set(target, [...(enteredFrom.get(target) ?? []), index + 1])
    }
  })

  const layout: GrafcetLayout = {
    steps: [],
    actions: [],
    transitions: [],
    links: [],
    jumps: [],
    actionWidth: G.actionWidth,
    deviceWidth: 0,
    width: 0,
    height: 0,
  }
  let cursor = G.margin + 14
  let maxX = 0
  // Where the line into the next step starts, when the step before goes on to it.
  let incoming: Point | null = null
  // The longest texts of the action boxes in characters, from which their
  // cells take their widths once every step is laid out.
  let deviceChars = 0
  let commandChars = 0
  let textChars = 0
  let noteChars = 0

  function conditionLines(terms: readonly SequenceConditionTerm[], stepKey: string) {
    const label = text.condition(terms, stepKey) || '1'
    const lines = terms.length > 0 ? terms.map((term) => text.condition([term], stepKey)) : [label]
    // The lines start 20 to the right of the bar.
    const width = 20 + Math.max(...lines.map((line) => line.length)) * G.charWidth
    return { label, lines, width, extra: (lines.length - 1) * G.conditionLineHeight }
  }

  steps.forEach((step, index) => {
    const number = index + 1
    const isLast = index === steps.length - 1
    const top = cursor
    if (incoming) layout.links.push([incoming, [G.center, top]])
    layout.steps.push({
      key: step.key,
      number,
      x: G.center - G.step / 2,
      y: top,
      initial: index === 0,
      timeoutMs: step.timeout_ms ?? null,
      enteredFrom: enteredFrom.get(step.key) ?? [],
    })

    // Actions, attached to the right of the step, one below the other.
    let actionY = top + (G.step - G.actionHeight) / 2
    const actionX = G.center + G.step / 2 + G.actionGap
    const actions = step.actions ?? []
    if (actions.length > 0) layout.links.push([[G.center + G.step / 2, top + G.step / 2], [actionX, top + G.step / 2]])
    for (const action of actions) {
      const condition = (action.condition ?? []).length > 0 ? text.condition(action.condition ?? [], step.key) : null
      const height = G.actionHeight + (condition ? G.actionConditionHeight : 0)
      const { device, text: description } = text.action(action, step.key)
      if (device === null) {
        textChars = Math.max(textChars, description.length)
      } else {
        deviceChars = Math.max(deviceChars, device.length)
        commandChars = Math.max(commandChars, description.length)
      }
      // The condition note has a word such as "if" before it.
      if (condition) noteChars = Math.max(noteChars, condition.length + 6)
      layout.actions.push({
        x: actionX,
        y: actionY,
        height,
        qualifier: QUALIFIER[action.qualifier ?? 'stored'],
        device,
        text: description,
        condition,
      })
      actionY += height
    }
    let bottom = Math.max(top + G.step, actionY)
    const stepBottom: Point = [G.center, top + G.step]

    const transitions = step.transitions ?? []
    incoming = null
    if (transitions.length === 1) {
      const transition = transitions[0]!
      const barY = bottom + G.transitionGap
      const { label, lines, width, extra } = conditionLines(transition.condition ?? [], step.key)
      layout.transitions.push({ x: G.center, y: barY, label, lines })
      maxX = Math.max(maxX, G.center + width)
      const end: Point = [G.center, barY + G.transitionGap + extra]
      layout.links.push([stepBottom, end])
      const target = transition.target ?? TARGET_NEXT
      if (target === TARGET_NEXT && !isLast) {
        incoming = end
        bottom = end[1]
      } else {
        layout.jumps.push({ x: G.center, y: end[1], target: target === TARGET_END ? null : (numbers.get(target) ?? null) })
        bottom = end[1] + G.jumpHeight
      }
    } else if (transitions.length > 1) {
      const divergeY = bottom + 12
      const texts = transitions.map((transition) => conditionLines(transition.condition ?? [], step.key))
      // The branches stand far enough apart for the widest condition to fit beside its bar.
      const spacing = Math.max(G.branchWidth, ...texts.map((t) => t.width + 24))
      const lastX = G.center + (transitions.length - 1) * spacing
      maxX = Math.max(maxX, lastX + Math.max(G.branchWidth - 20, texts.at(-1)!.width))
      layout.links.push([stepBottom, [G.center, divergeY]])
      layout.links.push([[G.center, divergeY], [lastX, divergeY]])
      const extra = Math.max(...texts.map((t) => t.extra))
      const branchEnd = divergeY + 2 * G.transitionGap + extra
      const rejoin: number[] = []
      let jumped = false
      transitions.forEach((transition, j) => {
        const x = G.center + j * spacing
        const { label, lines } = texts[j]!
        layout.transitions.push({ x, y: divergeY + G.transitionGap, label, lines })
        layout.links.push([[x, divergeY], [x, branchEnd]])
        const target = transition.target ?? TARGET_NEXT
        if (target === TARGET_NEXT && !isLast) {
          rejoin.push(x)
        } else {
          layout.jumps.push({ x, y: branchEnd, target: target === TARGET_END ? null : (numbers.get(target) ?? null) })
          jumped = true
        }
      })
      bottom = branchEnd + (jumped ? G.jumpHeight : 0)
      if (rejoin.length > 0) {
        const joinY = bottom + 10
        for (const x of rejoin) layout.links.push([[x, branchEnd], [x, joinY]])
        if (rejoin.length > 1 || rejoin[0] !== G.center) {
          layout.links.push([[Math.min(G.center, ...rejoin), joinY], [Math.max(...rejoin), joinY]])
        }
        incoming = [G.center, joinY]
        bottom = joinY
      }
    }
    cursor = bottom + G.stepGap
  })

  const pad = G.cellPadding
  layout.deviceWidth = deviceChars > 0 ? 2 * pad + deviceChars * G.charWidth : 0
  layout.actionWidth = Math.max(
    G.actionWidth,
    deviceChars > 0 ? G.qualifierWidth + layout.deviceWidth + 2 * pad + commandChars * G.charWidth : 0,
    G.qualifierWidth + 2 * pad + textChars * G.charWidth,
    G.qualifierWidth + 2 * pad + noteChars * G.noteCharWidth,
  )
  maxX = Math.max(maxX, G.center + G.step / 2 + G.actionGap + layout.actionWidth)
  layout.width = maxX + G.margin
  layout.height = cursor + G.margin
  return layout
}
