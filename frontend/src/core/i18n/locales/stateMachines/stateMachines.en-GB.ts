// Messages for stateMachines, merged into the en-GB locale.
export default {
  liveHint: "This page is read live from the system's own rules, so it always shows what the system currently enforces.",
  asOf: 'As of {time}, fetched live from the backend',
  refresh: 'Refresh',
  missing: "This lifecycle isn't in the backend's introspection response.",
  legend: {
    initial: 'Initial state',
    terminal: 'Terminal state',
    backEdge: 'Back edge',
  },
  errors: {
    loadFailed: 'Failed to load the state machines.',
  },
  kind: {
    derived: 'Worked out from what happened',
    intent: 'Set by actions',
  },
  rules: {
    title: 'How the status is worked out',
    intro: 'The rows are checked from the top. The first row that applies decides the status.',
    columns: {
      number: '#',
      condition: 'When',
      result: 'Status',
    },
  },
  intents: {
    title: 'What you can do',
    anyStatus: 'Any status',
    setStatus: 'Set to {status}',
    columns: {
      action: 'Action',
      allowedFrom: 'Allowed in',
      condition: 'Also needs',
      permission: 'Permission',
      effect: 'What happens',
    },
  },
  transitions: {
    title: 'Status changes',
    intro: 'Every status change the system makes on this lifecycle, found by running its real actions against each other. A row that names another record was changed by an action on that record.',
    computedHint: 'This table is worked out from the system itself: a test fails whenever the system makes a change the table does not list, or the table lists one the system cannot make.',
    created: 'New',
    via: 'Action on: {machine}',
    change: '{machine}: {from} → {to}',
    columns: {
      from: 'From',
      to: 'To',
      trigger: 'Trigger',
      condition: 'Condition',
      permission: 'Permission',
      implications: 'Also changes',
    },
  },
  cascades: {
    title: 'What an action changes elsewhere',
    intro: 'For every action, the status changes it can make on other records. One action changes only those that apply to the records it touches.',
    columns: {
      record: 'Action on',
      trigger: 'Action',
      changes: 'Status changes',
    },
  },
  machines: {
    lot_status: 'Lot',
    lot_position_status: 'Lot Position',
    lot_position_kind: 'Lot Position Kind',
    production_order_status: 'Production Order',
    order_status: 'Order',
    order_item_status: 'Order Line',
    bought_item_demand_status: 'Bought Item Demand',
    made_item_demand_status: 'Made Item Demand',
    source_item_demand_status: 'Source Item Demand',
    quote_request_status: 'Quote Request',
  },
  triggers: {
    allocate: 'Allocate an order line',
    allocate_source: 'Allocate a source order line',
    assign_external: 'Order externally',
    assign_internal: 'Plan internally',
    award: 'Award the request',
    cancel_bought_demand_request: 'Cancel the demand',
    cancel_line: 'Cancel the line',
    cancel_lot_request: 'Cancel the lot',
    cancel_made_demand_request: 'Cancel the demand',
    cancel_order: 'Cancel the order',
    cancel_production_order: 'Cancel the production order',
    cancel_source_demand_request: 'Cancel the demand',
    close_short: 'Close short',
    complete: 'Record a completion',
    correct: 'Correct a delivery',
    create_lot_for_demand: 'Create a lot for the demand',
    deliver: 'Book a receipt',
    deliver_all: 'Deliver every line',
    force_complete: 'Complete the lot early',
    fulfil_bought_demand: 'Mark the demand fulfilled',
    fulfil_made_demand: 'Mark the demand fulfilled',
    fulfil_source_demand: 'Mark the demand fulfilled',
    hold: 'Put the lot on hold',
    mark_ordered: 'Mark the line ordered',
    mark_requested: 'Mark the line requested',
    merge: 'Merge production orders',
    move: 'Move to another order',
    pause: 'Pause',
    release: 'Release an allocation',
    reopen: 'Reopen the line',
    request_order: 'Mark the order requested',
    resume_lot: 'Resume the lot',
    reverse_completion: 'Reverse a completion',
    scrap: 'Scrap pieces',
    source_from_stock: 'Take from stock',
    split: 'Split the production order',
    start: 'Start or resume',
    submit_order: 'Mark the order ordered',
    take_from_stock: 'Take from stock',
    unassign_external: 'Remove the supplier line',
    update_allocation: 'Change an allocation',
  },
  actions: {
    deliver: 'Deliver',
    correct_delivery: 'Correct Delivery',
    close_short: 'Close Short',
    reopen: 'Reopen',
    mark_ready_for_pickup: 'Mark Ready for Pickup',
    cancel: 'Cancel',
    hold: 'Put on Hold',
    resume: 'Resume',
    force_complete: 'Force Complete',
    start: 'Start',
    pause: 'Pause',
    record_completion: 'Record Completion',
    reverse_completion: 'Reverse Completion',
    mark_requested: 'Mark Requested',
    mark_ordered: 'Mark Ordered',
    fulfil: 'Mark Fulfilled',
    allocate: 'Allocate',
    edit_quantity: 'Change Quantity',
    edit_structure: 'Change Steps',
    reorder_positions: 'Reorder Positions',
    move: 'Move to Another Order',
    remove: 'Delete',
    scrap: 'Scrap Pieces',
    split: 'Split',
    merge: 'Merge',
    assign_external: 'Order Externally',
    assign_internal: 'Plan Internally',
    unassign_external: 'Remove Supplier Line',
    record_provision: 'Record Provision',
    set_status: 'Set Status',
    send: 'Mark Sent',
    award: 'Award',
    close: 'Close',
    approve_source: 'Approve Source',
    reject_source: 'Reject Source',
    switch_source: 'Change Material Source',
    complete: 'Complete',
    archive: 'Archive',
    edit: 'Edit',
    add_item: 'Add Line',
  },
  rows: {
    order_status: {
      r1: 'Someone canceled the order.',
      r2: 'The order has no lines.',
      r2Result: 'Ordered once submitted, requested once requested, otherwise draft',
      r3: 'Every line is canceled.',
      r4: 'Every line that is not canceled is delivered.',
      r5: 'A line that is not canceled is fully or partly delivered.',
      r6: 'The order was submitted, or every line that is not canceled is ordered.',
      r7: 'A line that is not canceled is ordered.',
      r8: 'The order was requested, or every line that is not canceled is requested.',
      r9: 'In every other case.',
    },
    order_item_status: {
      r1: 'Someone canceled the line.',
      r2: 'Delivered and lost pieces reach the line quantity.',
      r3: 'Some pieces were delivered or lost.',
      r4: 'The line was marked ordered.',
      r5: 'The line was marked requested.',
      r6: 'In every other case.',
    },
    production_order_status: {
      r1: 'Someone canceled the order.',
      r2: 'Processed pieces reach the order quantity.',
      r3: 'The order was never started.',
      r4: 'The order has an open interruption.',
      r5: 'In every other case.',
    },
    lot_position_kind: {
      r1: 'It has a supplier line and also production orders or own progress.',
      r2: 'It has a supplier line.',
      r3: 'It has a production order that is not canceled, or own progress.',
      r4: 'In every other case.',
    },
    lot_position_status: {
      r1: 'The lot was canceled.',
      r2: 'Completed pieces reach the position quantity.',
      r3: 'Some pieces are completed.',
      r4: 'A production order is running or paused.',
      r5: 'The supplier line is ordered or partly delivered, or a production order is queued.',
      r6: 'In every other case.',
    },
    lot_status: {
      r1: 'Someone canceled the lot.',
      r2: 'Nothing is left to produce.',
      r3: 'Someone force-completed the lot, or every position is completed.',
      r4: 'Someone put the lot on hold.',
      r5: 'A position has started or has finished pieces.',
      r6: 'Every position is planned.',
      r7: 'Some positions are planned.',
      r8: 'In every other case.',
    },
    demand_status: {
      r1: 'Someone canceled the demand.',
      r2: 'Someone marked it fulfilled by hand.',
      r3: 'Delivered pieces and stock cover the quantity.',
      r4: 'Allocations and stock cover the quantity, and every order or lot behind them is placed.',
      r5: 'Something is allocated or taken from stock.',
      r6: 'In every other case.',
    },
    quote_request_status: {
      r1: 'Someone canceled the request.',
      r2: 'Someone closed the request.',
      r3: 'Every line is awarded or dropped, and at least one is awarded.',
      r4: 'Every line was dropped.',
      r5: 'The request went out to at least one supplier.',
      r6: 'In every other case.',
    },
  },
  intentRows: {
    order: {
      mark_requested: {
        effect: 'Requests the order and its pending lines.',
      },
      mark_ordered: {
        effect: 'Submits the order and marks its pending and requested lines ordered.',
      },
      cancel: {
        effect: 'Delivered lines stay, partly delivered lines are closed short, the rest are canceled and their demands released.',
        permission: 'Managing orders, once the order is submitted',
      },
      deliver: {
        effect: 'Books every deliverable line in one step.',
      },
      edit: {
        condition: 'Nobody canceled the order.',
        effect: 'Changes the supplier, the dates, the notes and the other header fields.',
        permission: 'Managing orders, once the order is submitted',
      },
      add_item: {
        condition: 'Nobody canceled the order.',
        effect: 'Adds a new pending line.',
        permission: 'Managing orders, once the order is past requested',
      },
    },
    order_item: {
      mark_requested: {
        effect: 'Records the request.',
        permission: 'Managing orders, once the line or its order is past requested',
      },
      mark_ordered: {
        effect: 'Records the order date.',
        permission: 'Managing orders, once the line or its order is past requested',
      },
      deliver: {
        condition: "The order is not canceled, and for a lot's line the lot is not canceled.",
        effect: 'Books the received pieces.',
      },
      mark_ready_for_pickup: {
        condition: 'The order is not canceled.',
        effect: 'Records when the goods are ready for pickup, never a time still to come.',
        permission: 'Managing orders, once the line or its order is past requested',
      },
      edit: {
        effect: 'Changes the note, the dates, the price and the storage place; the unit, the item and the project only until goods arrived.',
        permission: 'Managing orders, once the line or its order is past requested',
      },
      correct_delivery: {
        condition: 'Not a line for a lot, not closed short, and the order is not canceled.',
        effect: 'Takes pieces back from a delivery as miscounted or as rejected after receipt, never below what demands already used.',
      },
      close_short: {
        condition: 'Something was delivered or lost.',
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Lowers the quantity to what was delivered or lost; the supplier sends nothing more.',
      },
      reopen: {
        condition: 'Closed short, not a line for a lot, and the order is not canceled.',
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Brings back the quantity from before the close; the line waits for the rest again.',
      },
      cancel: {
        condition: 'Nothing was delivered or lost.',
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Cancels the line and releases its demands.',
      },
      edit_quantity: {
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Never below what was delivered or lost, or below what demands have allocated.',
      },
      move: {
        condition: 'Nothing was delivered or rejected, and nobody canceled the target order.',
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Moves the line to the other order.',
      },
      remove: {
        permission: 'Managing orders, once the line or its order is past requested',
        effect: 'Deletes the line and releases its demands.',
      },
    },
    production_order: {
      start: {
        condition: 'The lot is not on hold or finished, a machine can be found, and the previous step has pieces ready.',
        effect: 'Records the start and the operator.',
      },
      resume: {
        condition: 'Someone paused it by hand, the lot is not on hold, and the previous step has pieces ready.',
        effect: 'Ends the pause.',
      },
      pause: {
        effect: 'Starts a pause.',
      },
      cancel: {
        effect: 'Cancels the order and ends any pause.',
      },
      record_completion: {
        condition: 'The lot is not on hold.',
        effect: 'Books finished pieces, at most the order quantity; rejects only on an inspection step.',
      },
      reverse_completion: {
        condition:
          'The lot is not on hold, the completion rejected nothing and is not reversed yet, its lot is not finished, and the next position has not used its pieces.',
        permission: 'Reverse completions',
        effect:
          'Books the pieces of the completion back with a reason; both stay on record and the completed count drops.',
      },
      scrap: {
        condition: 'The lot is not on hold.',
        effect: 'Books scrapped pieces and shrinks the lot.',
      },
      split: {
        effect: 'Splits the order on the same machine and pool.',
      },
      merge: {
        effect: 'Joins queued orders of the same machine and pool.',
      },
    },
    lot_position: {
      assign_external: {
        condition:
          'The lot is not finished, there is no supplier line yet or only lines closed short, and some quantity is left.',
        effect:
          'Creates a supplier line for at most the free quantity; a line closed short stays beside the new one.',
      },
      unassign_external: {
        condition: 'The position is bought in and its supplier line is pending or requested.',
        effect: 'Deletes the supplier line.',
      },
      assign_internal: {
        condition: 'The lot is not finished and some quantity is left.',
        effect: 'Creates production orders for at most the free quantity.',
      },
      record_provision: {
        condition: 'The lot is not finished and the position is bought in.',
        effect: 'Books provided material, at most what the previous step made available.',
      },
    },
    lot: {
      hold: {
        effect: 'Pauses the running production orders.',
      },
      resume: {
        effect: 'Continues the orders the hold paused.',
      },
      cancel: {
        condition: 'No position finished a good piece yet; otherwise force-complete the lot.',
        permission: 'Managing lots',
        effect:
          'Cancels the open work of the lot, keeps ordered supplier lines open, releases its demands and settles its raw material.',
      },
      force_complete: {
        condition: 'A position finished a good piece.',
        permission: 'Managing lots',
        effect: 'Closes the lot at what it produced, ends its open work and settles its raw material.',
      },
      scrap: {
        effect:
          'Shrinks the position and the work after it. Pieces booked as lost at goods receipt are a recorded fact, not a scrap, and stay allowed on a held lot.',
      },
      edit_structure: {
        effect: 'Changes steps of positions that are not assigned and have no progress.',
      },
      reorder_positions: {
        effect: 'Moves only positions that are not assigned and have nothing completed.',
      },
      edit_quantity: {
        effect:
          'The positions and an open raw material demand follow; never below what demands have allocated.',
      },
      approve_source: {
        condition:
          'The material source waits for approval or was rejected, the project is active and the source item can still be used.',
        effect: 'Approves the material source and creates its raw material demand.',
      },
      reject_source: {
        condition: 'The material source waits for approval.',
        effect: 'Rejects the material source with a reason; no demand is created.',
      },
      switch_source: {
        condition: 'The raw material demand, if there is one, is not fulfilled.',
        effect:
          'Replaces the raw material demand and keeps what already arrived; the new source waits for approval or gets a demand for what is missing.',
      },
    },
    demand: {
      cancel: {
        condition: 'For a raw material demand, its lot has not started production.',
        effect:
          'Cancels the demand and releases its allocations. For a raw material demand you choose what happens to its lot: it is canceled too, or it stays unlinked and waits on raw material.',
      },
      fulfil: {
        effect:
          'Marks the demand fulfilled by hand. A bought or raw material demand keeps on its order lines only the pieces that arrived for it; the rest of those allocations is released.',
      },
      allocate: {
        effect: 'Allocates from orders, lots or stock, never more than the demand needs.',
      },
      edit_quantity: {
        effect: 'Never below what is allocated.',
      },
      remove: {
        condition: 'Nothing is allocated.',
        effect: 'Deletes the demand.',
      },
    },
    catalogue_item: {
      to_active: {
        effect: 'Names no successor; a stored one is dropped.',
      },
      to_inactive: {
        effect: 'Names no successor; a stored one is dropped.',
      },
      to_replaced: {
        effect: 'Needs a successor that exists, is not archived and does not lead back.',
      },
    },
    project: {
      hold: {
        effect: 'Puts the project on hold. It takes no new work; its open work goes on.',
      },
      resume: {
        effect: 'Makes the project active again, so it takes new work.',
      },
      complete: {
        condition: 'No open lots, production orders, order lines, demands or quote requests.',
        effect: 'Completes the project.',
      },
      archive: {
        condition: 'No open lots, production orders, order lines, demands or quote requests.',
        effect: 'Archives the project.',
      },
      reopen: {
        effect: 'Makes the project active again, so it takes new work.',
      },
      remove: {
        condition: 'No open lots, production orders, order lines, demands or quote requests.',
        effect: 'Deletes the project.',
      },
    },
    quote_request: {
      send: {
        condition: 'At least one line and one supplier.',
        effect: 'Records that the request went out to the supplier, who is then asked for every line.',
      },
      award: {
        condition: 'At least one open line.',
        effect: 'Puts each chosen line on a draft order of the supplier that won it.',
      },
      close: {
        condition: 'At least one awarded line.',
        effect: 'Drops the lines still open and closes the request.',
      },
      cancel: {
        condition: 'No awarded line.',
        effect: 'Cancels the request. Its demands stay open.',
      },
      reopen: {
        condition: 'Someone closed the request, and since then an award on it was voided.',
        effect: 'Clears the close, so the request is sent or draft again and the voided line can be awarded anew. The offers stay, and the lines the close dropped stay dropped until you take them back.',
      },
    },
  },
}
