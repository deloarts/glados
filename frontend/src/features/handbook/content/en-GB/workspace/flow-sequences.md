---
title: Flow Sequences
summary: How a flow sequence of a machine is built from steps, actions and transitions, and read as diagrams with an estimated cycle time.
sourceRefs:
  - backend/src/modules/quality/domain/services/sequence_rules.py
  - backend/src/modules/quality/domain/value_objects/sequence_content.py
  - backend/src/modules/quality/application/use_cases/sequence/save_sequence.py
  - frontend/src/features/sequences/utils/validation.ts
  - frontend/src/features/sequences/utils/suggestions.ts
lastVerified: 2026-11-10
---

The **Sequences** tab of a product holds its flow sequences, such as the automatic cycle and homing. A sequence says what each device does in which step, always under the devices' current names, and Glados draws a **Displacement-Step Diagram** and a **GRAFCET** from it. Creating, releasing and revising a sequence is on [Releasing Flow Sequences](/handbook/workspace/flow-sequence-release).

## Steps and actions

A sequence is a list of numbered steps. **Add Step** adds one at the end, and **Insert Step** between two steps puts one there. The actions of a step start together when the step becomes active. A **Device Action** moves a device to a position of its kind, with a value where the position takes one. An action names the PLC command, such as Extend, and a condition the position, such as Extended. A device that moves with another one is greyed out, so move its driver instead. A **Text Action** describes in words what happens outside the devices, such as the robot picking a part. Each action is stored (S), continuous (N) or pulse (P), and may wait for a condition before it starts. The optional **Timeout** is the time after which the PLC reports a fault.

## Leaving a step

A step leaves through its transitions. **Go to** names the next step, any other step or the **End of sequence**. **Alternative Branch** adds a second way out, such as part OK and part not OK, and then every branch needs a condition. A condition is one or more terms that must all hold: a device **In position**, a device **Value** compared with a threshold, another step **Step complete**, the **Time in step**, and a **Text** for anything outside the devices, such as robot ready.

Under each transition, **Suggested:** offers the positions the step moves its devices to, and **Add All** takes them all, the usual way to wait until a move has finished. A suggestion with a warning sign is a position no sensor confirms, so the PLC cannot check it.

While you edit, a step shows in red what saving would refuse, such as a missing value. It also warns when two branches have the same condition, or when a transition waits for a device in another position than the step moves it to.

## Start state and variants

**Initial** shows the **Start State**, the initial position of every device, which a released revision keeps from its release. The product's **Variants**, such as Clamp 60 and Clamp 80, can each get their own value under **Values per variant**; a variant left empty uses the common one.

## Estimated cycle time

Every step shows its estimated duration from the travel times of the devices, the times of its actions, the time conditions it waits for and its **Expected** duration. A step that waits for a **Text** condition needs an expected duration, or the total reads "at least". The info strip shows the cycle along the first branch of each step, or the branch you pick with the timer button, and the worst case. **Time Axis** sizes the diagram's columns by duration.

## Examples

**A plain cycle.** Step 1 waits for B00 Start Button in position Pressed, steps 2 to 4 move the axis and the cylinders, and the last step goes to step 1.

**Waiting for a move.** Step 2 extends B01 Lift Cylinder P1. **Suggested:** offers the cylinder in Extended, and one click makes the step wait until its sensor reports it out.

**A stroke per variant.** B02 Linear Axis E1 moves to Position with 120 mm for Clamp 60 and 160 mm for Clamp 80.
