/**
 * Mirrors `LiveResource` on the backend (src/modules/platform/ports/outbound/live_signal.py).
 * Each value is the API path segment of the list endpoint that serves the
 * resource's rows. A table subscribes with its own value and refetches
 * changed rows through that same endpoint, so the wire shape always
 * matches what the table already renders.
 */
export const LiveResource = {
  ORDERS: 'orders',
  BOUGHT_ITEM_DEMANDS: 'bought-items-demands',
  // Signalled when an item's files or pictures change; the item id names
  // the item.
  BOUGHT_ITEMS: 'bought-items',
  MADE_ITEMS: 'made-items',
  SOURCE_ITEMS: 'source-items',
  MADE_ITEM_DEMANDS: 'made-items-demands',
  SOURCE_ITEM_DEMANDS: 'source-item-demands',
  PRODUCTION_LOTS: 'production-lots',
  PRODUCTION_ORDERS: 'production-orders',
  PRODUCTION_MACHINES: 'production-machines',
  MACHINE_POOLS: 'production-machine-pools',
  ANNOUNCEMENTS: 'announcements',
  CALCULATIONS: 'calculations',
  CHECKLISTS: 'checklists',
  SEQUENCES: 'sequences',
  // Signalled with the product id when a device of that product changes.
  PRODUCT_DEVICES: 'product-devices',
  // A quote request page, its list and the "in quotation" markers.
  QUOTE_REQUESTS: 'quote-requests',
  // Contacts, and the contact links signalled with the product or project
  // id. Only readers of contacts receive them.
  CONTACTS: 'contacts',
  PRODUCT_CONTACTS: 'product-contacts',
  PROJECT_CONTACTS: 'project-contacts',
  // A meeting and everything on its page, signalled with the meeting id,
  // for the meeting page and the meeting lists.
  MEETINGS: 'meetings',
  // Someone edits a meeting card: the id is the card's and the actor the
  // editor, "updated" while they type and "deleted" when they stop.
  MEETING_CARD_PRESENCE: 'meeting-card-presence',
  // Wall display devices and the screens they show.
  TERMINALS: 'terminals',
  INFOSCREENS: 'infoscreens',
  // The default display schedule the screens in the default mode follow.
  INFOSCREEN_DEFAULTS: 'infoscreen-defaults',
  // Messages shown on many terminals at once, signalled on send and on end.
  TERMINAL_BROADCASTS: 'terminal-broadcasts',
} as const

export type LiveResourceValue = (typeof LiveResource)[keyof typeof LiveResource]
