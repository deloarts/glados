// Messages for productionSchedule, merged into the en-GB locale.
export default {
  tabLabel: 'Capacity',
  dateRange: 'Date range',
  weekPrefix: 'W',
  empty: 'No machines to show for this range.',
  machinesSectionTitle: 'Machines',
  staleSince:
    'Changes since {time} are still being worked into the stored planned dates. This board is already up to date.',
  poolsSectionTitle: 'Machine Pools',
  poolsEmpty: 'No machine pools to show for this range.',
  machineOrdersEmpty: 'No orders in this range.',
  overbookedTooltip: '+{hours} overbooked',
  floatingTag: 'Unresolved',
  floatingTooltip:
    'This order is placed in the pool but not yet assigned to a specific machine; its dates are a forecast and may still shift.',
  floatingTooltipReserved: 'Reserved on {machine}.',
  columns: {
    machine: 'Machine',
    orders: 'Orders',
    order: 'Order',
    lot: 'Lot',
    project: 'Project',
    item: 'Item',
    step: 'Step',
    window: 'Window',
    conflicts: 'Conflicts',
  },
  autoPlan: {
    trigger: 'Auto-Plan',
    title: 'Auto-Plan Schedule',
    description:
      'Proposes and applies a priority/due-date-driven re-sequencing for every eligible queued order. In-progress orders are never touched; pinned orders are left alone unless you allow overwriting them below.',
    algorithm: 'Planning algorithm',
    algorithms: {
      urgentFirst: {
        label: 'Urgent First',
        description:
          'Places urgent orders first, then whichever is due soonest; each order goes to whichever machine finishes it fastest. The default behavior.',
        ordering:
          'Urgency class first (most urgent first), then the earliest position due date, then creation order.',
        selection: 'Earliest finish, whichever eligible machine completes the order soonest.',
        bestFor:
          'Everyday planning, where an explicitly marked urgent order really should jump the queue.',
        watchOut:
          'A steady stream of urgent orders keeps pushing everything else further back, however close its own deadline is.',
      },
      strictDeadline: {
        label: 'Strict Deadline',
        description:
          'Ignores urgency tags entirely and always places orders strictly in due-date order, which minimizes the worst-case lateness.',
        ordering:
          'Earliest position due date only; urgency markings are ignored completely. Creation order breaks ties.',
        selection: 'Earliest finish, whichever eligible machine completes the order soonest.',
        bestFor:
          'Delivery-date discipline, this ordering provably minimizes how late the single worst order ends up.',
        watchOut:
          'An order flagged urgent no longer jumps ahead of one that is simply due earlier.',
      },
      fairQueue: {
        label: 'Fair Queue',
        description:
          'No reprioritization at all: orders are placed in the order they were created, which keeps the plan fully predictable.',
        ordering: 'Creation order, and nothing else.',
        selection: 'Earliest finish, whichever eligible machine completes the order soonest.',
        bestFor:
          'A neutral, fully predictable baseline, also useful for seeing what the other algorithms actually change.',
        watchOut:
          'Ignores both urgency and due dates, so a late-created but urgent order gets no preference at all.',
      },
      balancedLoad: {
        label: 'Balanced Load',
        description:
          'Same urgency/due-date ordering as Urgent First, but spreads work evenly across machines instead of always picking whichever finishes fastest.',
        ordering: 'Identical to Urgent First, urgency, then due date, then creation order.',
        selection:
          'Least loaded, whichever eligible machine has the fewest booked minutes so far, ties broken by machine id.',
        bestFor:
          'Keeping every machine busy and stopping one machine from absorbing the whole backlog.',
        watchOut:
          'An individual order can finish later than it would otherwise, since the least-loaded machine is not necessarily the fastest one available.',
      },
      criticalRatio: {
        label: 'Critical Ratio',
        description:
          '(days until due) / (days of work remaining), lower = more urgent. Adapts automatically as time passes, but can behave oddly once a due date is already in the past.',
        ordering:
          '(days until due) divided by (days of work remaining), lowest first, recomputed against today on every run.',
        selection: 'Earliest finish, whichever eligible machine completes the order soonest.',
        bestFor:
          'Weighing urgency against job length by itself, the ratio shrinks on its own the longer an order waits.',
        watchOut:
          'Once a due date is already in the past the ratio turns negative and the ranking gets counter-intuitive. Orders with no due date never become critical and sort last.',
      },
      shortestProcessingTime: {
        label: 'Shortest Processing Time',
        description:
          'Shortest jobs first, regardless of urgency or due date. Maximizes throughput, but can delay a long job indefinitely.',
        ordering:
          'Shortest estimated duration first, regardless of urgency or due date. Creation order breaks ties.',
        selection: 'Earliest finish, whichever eligible machine completes the order soonest.',
        bestFor:
          'Clearing a backlog of small jobs quickly, it finishes the largest number of orders soonest.',
        watchOut:
          'A long job can be starved indefinitely as shorter ones keep arriving in front of it.',
      },
    },
    explain: {
      trigger: 'Explain',
      tooltip: 'Show how the planning algorithm works',
      // The prose lives in the handbook page
      // features/handbook/content/*/production/auto-plan.md. Only these
      // stay: the picker above reads the same per-algorithm labels, so
      // duplicating them into markdown would let the two drift.
      selected: 'Selected',
      facts: {
        ordering: 'Ordering',
        selection: 'Machine choice',
        bestFor: 'Best for',
        watchOut: 'Watch out',
      },
    },
    machines: 'Machines to include',
    assignMachines: 'Allow assigning machines',
    assignMachinesHint:
      'Off by default: only reorders orders within the machine they already have. When enabled, it may also assign a machine to an unassigned order, or move an order to a different one, whichever finishes it soonest among capable machines.',
    planningLevel: 'Planning level',
    planningLevelOptions: {
      machines: 'Machines',
      pools: 'Pools',
    },
    overwritePinned: 'Allow overwriting user-planned dates',
    overwritePinnedHint:
      'Off by default: a manually pinned order is left untouched, acting as a fixed anchor. When enabled, it becomes a candidate too, and any pinned order actually moved is unpinned, which turns it back into a normal auto-managed order.',
    excludeTodaysPlanned: "Exclude today's planned items",
    excludeTodaysPlannedHint:
      "On by default: an order already planned to run today is left untouched, even if it hasn't started yet, so the shop floor's queue for today doesn't get reshuffled. Turn off to let Auto-Plan reconsider today's queue too.",
    responseTimeDays: 'Response time for planned start (days)',
    responseTimeDaysHint:
      "Buffer added to an external step's arrival and a raw material's arrival before either can gate the next step's earliest start. Pre-filled from the admin setting; changing it here applies to this run only.",
    run: 'Run Auto-Plan',
    before: 'Before',
    after: 'After',
    noProposals: 'No orders needed re-planning.',
    skipped:
      'No pinned or in-progress orders skipped. | Skipped 1 pinned or in-progress order. | Skipped {count} pinned or in-progress orders.',
    skippedTodaysPlanned:
      'No orders already planned for today left untouched. | Left 1 order already planned for today untouched. | Left {count} orders already planned for today untouched.',
    redated: {
      title: 'Re-dated by the Schedule Walk',
      hint: "Orders this run didn't place, but whose day the walk after it changed.",
      kept: 'Every other open order kept its day. | 1 other open order kept its day. | {count} other open orders kept their day.',
      none: 'The walk moved no other order to another day.',
      walkFailed: "The schedule couldn't be refreshed after this run. The dates update with the next walk.",
      filter: {
        all: 'All',
        earlier: 'Earlier',
        later: 'Later',
      },
      columns: {
        column: 'Column',
        before: 'Before',
        after: 'After',
        shift: 'Shift',
        reason: 'Reason',
      },
      shift: {
        earlier: '1 day earlier | {count} days earlier',
        later: '1 day later | {count} days later',
        dated: 'Now dated',
        undated: 'No date',
      },
      reason: {
        readyNow: 'Ready now',
        readyNowDetail: 'Nothing holds it back.',
        queue: 'After {order}',
        queueRunning: 'Behind running {order}',
        queueDetail: 'Which ends {moment}.',
        queueOverrunDetail: 'Overrunning: {processed} of {quantity} reported, {left} left, ends about {moment}.',
        predecessor: 'After position {sequence}',
        predecessorDetail: '{order} ends {moment}.',
        predecessorReadyDetail: 'Position {sequence} is ready {moment}.',
        waitAfter: 'Wait after the step, {duration}',
        waitAfterDetail: 'Position {sequence} is ready {moment}.',
        orderLine: 'Waits for order line #{line}',
        orderLineDetail: 'Expected {date}, plus {days} response day. | Expected {date}, plus {days} response days.',
        orderLineArrivedDetail: 'Arrived {date}, plus {days} response day. | Arrived {date}, plus {days} response days.',
        orderLineForecast: 'Waits for the step at a supplier',
        orderLineForecastDetail:
          'No supplier date yet: forecast back {date}, plus {days} response day. | No supplier date yet: forecast back {date}, plus {days} response days.',
        orderLineLate: 'Order line #{line} is late',
        orderLineLateDetail:
          'Expected {date}, not delivered: counts as today, plus {days} response day. | Expected {date}, not delivered: counts as today, plus {days} response days.',
        rawMaterial: 'Waits for raw material',
        rawMaterialDetail: 'Ready {date}, response time included.',
        notBefore: 'Not before {date}',
        running: 'Running',
        runningDetail: '{processed} of {quantity} reported.',
        runningOverrunDetail: 'Overrunning: {processed} of {quantity} reported, {left} left.',
        pinned: 'Pinned',
        frozen: 'Inside the frozen window',
        undated: 'No date yet',
        undatedDetail: "An earlier step or the raw material has no date yet.",
        walkedMeanwhile: 'Dated by a walk that ran meanwhile',
      },
    },
    skippedOrders: {
      title: '1 order could not be placed: | {count} orders could not be placed:',
      reasons: {
        waiting_on_material: 'Waiting on material',
        waiting_on_materialTooltip:
          "This order's raw material has neither arrived nor been ordered with a delivery date, so it's left unplanned until the demand is allocated or ordered.",
        no_eligible_machine: 'No eligible machine',
        no_eligible_machineTooltip:
          'No machine within the selected scope is capable of this order.',
        no_eligible_pool: 'No eligible pool',
        no_eligible_poolTooltip:
          'No machine pool is capable of this order at the Pools planning level.',
        no_eligible_pool_member: 'No pool member in scope',
        no_eligible_pool_memberTooltip:
          'A capable pool exists, but none of its member machines is within the selected scope of this run.',
        machine_down: 'Machine down',
        machine_downTooltip:
          'An eligible machine (or pool member) exists, but it currently has an open downtime, so it was excluded from this run.',
        changed_while_planning: 'Changed while planning',
        changed_while_planningTooltip:
          'An order in the queue this order came from or would go to changed while the run was planning, so the queue was left as it is. Run Auto-Plan again to place it.',
        unknown: 'Not placed',
        unknownTooltip: 'The planner could not place this order.',
      },
    },
    progress: {
      preparing: 'Preparing…',
      loading_orders: 'Loading production orders…',
      scoring: 'Prioritising orders…',
      placing: 'Placing orders…',
      recomputing: 'Recalculating machine schedules…',
      finalizing: 'Preparing results…',
      counter: '{current} / {total}',
      skippedTag: 'skipped',
      backgroundHint: 'The run continues in the background if you close this dialog.',
    },
    errors: {
      unknown: 'Something went wrong. Please try again.',
      connectionLost:
        'Connection lost, the run continues on the server. Check the schedule board in a moment.',
    },
    observer: {
      title: 'Auto-plan is running',
      startedBy: 'Started by {user}',
      startedAt: 'at {time}',
      blocked: 'A new run can only be started once this one has finished.',
      finished: 'The run started by {user} has finished.',
    },
  },
}
