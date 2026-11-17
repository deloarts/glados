// Messages for todo, merged into the en-GB locale.
export default {
  title: 'Todo',
  viewAll: 'View all',
  openCount: '{count} open',
  andMore: '+{count} more',
  showAll: 'Showing all',
  showAllHidden: 'Show all (+{count})',
  empty: 'Nothing to do right now.',
  emptyImportant: 'Nothing urgent right now.',
  emptyFiltered: 'No categories selected.',
  resetFilters: 'Show all categories',
  bucketEmpty: 'Nothing here.',
  allCategories: 'All Categories',
  categories: {
    procurement: 'Procurement',
    shop_floor: 'Shop Floor',
    planning: 'Planning',
    meetings: 'Meetings',
  },
  loadError: 'Failed to load tasks.',
  buckets: {
    overdue: 'Overdue',
    today: 'Today',
    week: 'This Week',
    blockers: 'Blockers',
  },
  tasks: {
    meetingTodo: {
      title: '{title}',
      subtitle: '{meetingNumber} {meetingName} · {scope}',
      subtitleNoScope: '{meetingNumber} {meetingName}',
    },
    collectPickup: {
      title: 'Collect {item}',
      subtitle: 'Ready at {supplier} · {orderNumber}',
    },
    confirmPickup: {
      title: 'Confirm pickup for {item}',
      subtitle: 'Awaiting confirmation from {supplier} · {orderNumber}',
    },
    chaseDelivery: {
      title: 'Chase delivery of {item}',
      subtitle: 'Overdue from {supplier} · {orderNumber}',
    },
    chasePartialDelivery: {
      title: 'Chase remainder of {item}',
      subtitle: '{delivered} of {quantity} delivered · {supplier} · {orderNumber}',
    },
    submitOrder: {
      title: 'Submit order {orderNumber}',
      subtitle: 'Still a draft · {supplier}',
    },
    orderDemand: {
      title: 'Order {item}',
      subtitle: 'Project {project} · qty {quantity}',
    },
    startProductionOrder: {
      title: 'Start {lotNumber} · {partNumber}',
      subtitle: '{machine} · position {position}/{count}',
    },
    productionConflict: {
      subtitle: '{lotNumber} · {orderNumber}',
    },
    planLot: {
      title: 'Plan lot {lotNumber}',
      subtitle: '{partNumber} · qty {quantity}',
    },
    resumeLot: {
      title: 'Lot {lotNumber} is on hold',
      subtitle: '{partNumber} · qty {quantity}',
    },
    chaseRawMaterial: {
      title: '{lotNumber} is waiting on raw material',
      subtitle: '{partNumber} · {orderNumber}',
    },
    approveLotSource: {
      title: 'Approve source item for lot {lotNumber}',
      subtitle: '{partNumber} · qty {quantity}',
    },
  },
}
