---
title: Machine Page
summary: What the page for one machine shows, which order its buttons act on and how operators run their shift from it.
sourceRefs:
  - frontend/src/features/production/machines/views/MachineDetailView.vue
  - frontend/src/features/production/machines/components/MachineDetailContent.vue
  - frontend/src/features/production/machines/components/MachineCurrentOrderCard.vue
  - backend/src/modules/fulfillment/domain/services/lifecycle/intents.py
lastVerified: 2026-11-10
---

The machine page shows one machine and its work, and it is meant to stay open on a screen at the machine for the whole shift. You open it by clicking a machine name on the [Queue Board](/handbook/production/queue) or a machine in the **Production Machines** list under Resources. It updates by itself whenever an order, a lot or the machine changes.

## The bar at the top {#info}

The top bar names the machine with its vendor and model, its fabrication methods and the pools it belongs to. A tag shows whether the machine is **Running**, **Paused** or **Idle**, and while a downtime is open, a red tag says since when the machine is down.

## The cards {#cards}

**Current Order** shows the order running or paused on the machine. It has the item's 3D model or picture, the part, the lot, the **Order Number**, the quantity, when it **Started** and who started it. Below that come the item's files and data and the source material, with its order and the state of its material demand. If more than one order runs on the machine, the others are listed under **Also running on this machine**.

**Queue** lists the orders queued on this machine for today or overdue, in queue order. For each pool the machine belongs to, a pool queue card lists the pool's orders that no machine has taken yet, also for today or overdue. The cards in both lists have the same buttons as on the Queue Board, without dragging.

## The buttons {#controls}

The buttons in the controls bar act on the current order, or on the first order of the queue when nothing runs. **Start** or **Resume**, **Pause**, **Complete**, **Scrap Pieces** and **Cancel** work as described on the [Queue Board](/handbook/production/queue), and **Complete** opens the dialog from [Recording Completions](/handbook/production/completions). **Print Docket** prints the order's docket, and its menu also offers **Print Label**. **Open Item**, **Open Source Material** and **Open Order** show the details in a dialog. **Downtimes** opens the machine's downtimes, as described under [Production Machines](/handbook/resources/machines).

The order buttons need **Write Production Orders**, and printing needs **Print Documents**. A button whose permission you lack shows disabled with a tooltip that names the permission.

To show a machine on a wall screen without any buttons, use the **Machine view** widget of an [infoscreen](/handbook/resources/infoscreens).

## Examples {#examples}

Nothing runs on the machine and the queue holds two orders. The operator presses **Start**, and the first order becomes the current order.

An order waits in the pool queue card of a machine. Pressing **Start** on its card asks which machine of the pool runs it, and once started it shows as the current order of that machine.

The operator finishes the last pieces and presses **Complete**. After recording them, the **Manufacturing Assessment** asks how the order went, and the next order of the queue becomes the target of the buttons.
