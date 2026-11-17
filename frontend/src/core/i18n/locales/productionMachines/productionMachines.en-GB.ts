// Messages for productionMachines, merged into the en-GB locale.
export default {
  controls: {
    new: 'New Machine',
    search: 'Search machines…',
  },
  views: {
    sortByItems: {
      nameAsc: 'Name (A → Z)',
      nameDesc: 'Name (Z → A)',
      createdDesc: 'Created (newest first)',
      createdAsc: 'Created (oldest first)',
    },
    groupByItems: {
      capability: 'Capability',
    },
  },
  columns: {
    internalName: 'Internal Name',
    status: 'Status',
    vendor: 'Vendor',
    model: 'Model',
    capabilities: 'Capabilities',
    maxPartDimension: 'Max Part Dimension',
    note: 'Note',
    created: 'Created',
    actions: 'Actions',
  },
  table: {
    empty: 'No production machines yet.',
  },
  filters: {
    filterBy: 'Filter',
    any: 'Any',
  },
  viewMachine: 'View Machine',
  editMachine: 'Edit Machine',
  archiveBlocked:
    '{n} production order is still queued, in progress or paused on this machine. Move it or finish it first. | {n} production orders are still queued, in progress or paused on this machine. Move them or finish them first.',
  qaMachineTag: 'QA / Measuring',
  qaMachineTooltip:
    'Dedicated measuring machine, only selectable for QA inspection steps, never for fabrication work.',
  errors: {
    unknown: 'Something went wrong. Please try again.',
  },
  create: {
    createTitle: 'New Production Machine',
    editTitle: 'Edit Production Machine',
    fields: {
      internalName: 'Internal Name',
      vendor: 'Vendor',
      model: 'Model',
      capabilities: 'Capabilities',
      capabilitiesPlaceholder: 'Select capabilities…',
      capabilitiesHint:
        'The fabrication methods this machine can do. Only steps with one of these methods can run on it.',
      capabilitiesQaDisabledHint:
        'QA/measuring machines take no fabrication work; capabilities do not apply.',
      maxPartDimension: 'Max Part Dimension',
      note: 'Note',
      isQaMachine: 'QA / measuring machine',
      isQaMachineHint:
        'Dedicated in-house measuring machine (e.g. a CMM). Only selectable for QA inspection steps and excluded from all fabrication work.',
    },
    errors: {
      required: 'Please fill in all required fields.',
      unknown: 'Something went wrong. Please try again.',
    },
  },
  calendar: {
    manage: 'Manage Calendar',
    title: 'Calendar, {name}',
    workingHours: {
      title: 'Working Hours',
      useDefault: 'Use Global Default',
      useCustom: 'Custom Override',
    },
    exceptions: {
      title: 'Calendar Exceptions',
      add: 'Add',
      empty: 'No calendar exceptions yet.',
      columns: {
        date: 'Date',
        availableMinutes: 'Available',
        note: 'Note',
      },
      edit: 'Edit',
      window: 'From {start} for {minutes} min',
      deleteConfirm: 'Delete the calendar exception for {date}?',
      errors: {
        dateRequired: 'Please select a date.',
      },
    },
    editDefault: 'Default Calendar',
    defaultTitle: 'Default Calendar',
    defaultHint: 'Weekly hours machines fall back to unless a machine has its own override.',
  },
  downtime: {
    button: 'Downtimes',
    addDowntime: 'Add Downtime',
    badge: 'Down since {time}',
    reasons: {
      breakdown: 'Breakdown',
      maintenance: 'Maintenance',
      tooling: 'Tooling Change',
      no_operator: 'No Operator',
      no_material: 'No Material',
      other: 'Other',
    },
    form: {
      addTitle: 'Add Downtime',
      explain: 'Explain downtimes',
      fields: {
        machine: 'Machine',
        startedAt: 'Started At',
        endedAt: 'Ended At',
        endedAtHint: 'Leave empty for an ongoing downtime.',
        reason: 'Reason',
        reasonPlaceholder: 'Select a reason…',
        note: 'Note',
      },
      errors: {
        required: 'Please fill in all required fields.',
        unknown: 'Something went wrong. Please try again.',
      },
    },
    list: {
      title: 'Machine Downtimes',
      explain: 'Explain downtimes',
      machineFilter: 'Machine',
      machineFilterPlaceholder: 'All machines',
      periodFrom: 'From',
      periodTo: 'To',
      empty: 'No downtimes in this period.',
      loadError: 'Could not load downtimes.',
      endError: 'Could not end the downtime.',
      deleteError: 'Could not delete the downtime.',
      deleteConfirm: 'Delete this downtime record for {machine}?',
      open: 'Open',
      end: 'End',
      columns: {
        machine: 'Machine',
        startedAt: 'Started',
        endedAt: 'Ended',
        reason: 'Reason',
      },
    },
  },
  status: {
    down: 'Down',
    running: 'Running',
    paused: 'Paused',
    idle: 'Idle',
    downTooltip: 'Down since {time}: {reason}',
    noOrderTooltip: 'No order running',
  },
}
