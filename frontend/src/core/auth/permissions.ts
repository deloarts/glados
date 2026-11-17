export const Permission = {
  WRITE_BOUGHT_ITEMS: 'write:bought_items',
  DELETE_BOUGHT_ITEMS: 'delete:bought_items',

  WRITE_MADE_ITEMS: 'write:made_items',
  DELETE_MADE_ITEMS: 'delete:made_items',

  WRITE_SOURCE_ITEMS: 'write:source_items',
  DELETE_SOURCE_ITEMS: 'delete:source_items',

  WRITE_SOURCE_ITEM_TYPES: 'write:source_item_types',

  WRITE_DEMAND_ITEMS: 'write:demand_items',
  MANAGE_DEMAND_ITEMS: 'manage:demand_items',

  WRITE_ORDERS: 'write:orders',
  MANAGE_ORDERS: 'manage:orders',

  // Recording a delivery against an order line. Deliberately separate from
  // WRITE_ORDERS/MANAGE_ORDERS, receiving goods is a warehouse action, so a
  // receiving clerk must not need (or gain) the ability to edit, submit or
  // cancel orders. See OrderRules.assert_can_receive_delivery.
  RECEIVE_DELIVERIES: 'receive:deliveries',

  WRITE_LOTS: 'write:lots',
  MANAGE_LOTS: 'manage:lots',

  // Gates recording completions on an inspection-role position and
  // managing its evidence files. An ordinary (non-inspection) order
  // completion needs only WRITE_PRODUCTION_ORDERS.
  WRITE_INSPECTIONS: 'write:inspections',

  WRITE_MACHINES: 'write:machines',

  WRITE_PRODUCTION_ORDERS: 'write:production_orders',
  // Manage also covers reversing a recorded completion, a correction kept
  // apart from recording one.
  MANAGE_PRODUCTION_ORDERS: 'manage:production_orders',

  WRITE_ALLOCATIONS: 'write:allocations',

  WRITE_SUPPLIERS: 'write:suppliers',
  DELETE_SUPPLIERS: 'delete:suppliers',

  // Contacts are personal data, so unlike most master data reading them
  // needs a permission. Write covers creating, editing and archiving them,
  // and anonymising them together with manage:meetings. Linking them to a
  // product or project follows that record's own edit rights.
  READ_CONTACTS: 'read:contacts',
  WRITE_CONTACTS: 'write:contacts',

  WRITE_ARTICLE_GROUPS: 'write:article_groups',

  WRITE_FABRICATION_METHODS: 'write:fabrication_methods',

  WRITE_INSPECTION_METHODS: 'write:inspection_methods',

  // The lists product devices pick from (driving media, kinds, component
  // roles, energy behaviours). Devices themselves follow the product's rule.
  WRITE_PRODUCT_DEVICE_RESOURCES: 'write:product_device_resources',

  WRITE_PROJECTS: 'write:projects',
  MANAGE_PROJECTS: 'manage:projects',

  // Every signed-in user reads every meeting, so there is no read
  // permission. Write covers meetings, their cards, decisions, todos and
  // files; manage covers marking them invalid, restoring and deleting them
  // and anonymising attendees.
  WRITE_MEETINGS: 'write:meetings',
  MANAGE_MEETINGS: 'manage:meetings',

  // Saved calculations of the tools under /tools. Release is a sign-off the
  // author may give on their own work; manage covers other users'
  // calculations, withdrawing a release and deleting released ones.
  WRITE_CALCULATIONS: 'write:calculations',
  RELEASE_CALCULATIONS: 'release:calculations',
  MANAGE_CALCULATIONS: 'manage:calculations',

  // Inspection checklists. Release is a second person's sign-off and is
  // never given by the creator of a revision; manage covers other users'
  // checklists, withdrawing a release and deleting released ones.
  WRITE_CHECKLISTS: 'write:checklists',
  RELEASE_CHECKLISTS: 'release:checklists',
  MANAGE_CHECKLISTS: 'manage:checklists',

  // Flow sequences of products. Release is a sign-off the author may give
  // on their own work; manage covers other users' sequences, taking over
  // their editing and marking released revisions invalid.
  WRITE_SEQUENCES: 'write:sequences',
  RELEASE_SEQUENCES: 'release:sequences',
  MANAGE_SEQUENCES: 'manage:sequences',

  WRITE_PAT: 'write:pat',
  MANAGE_API_KEYS: 'manage:api_keys',

  // Connecting an AI agent through the MCP surface (/api/v1/mcp). A token
  // reaches it only while it carries this permission, so an admin decides
  // per user or group who may use an agent at all.
  USE_MCP: 'use:mcp',

  READ_SETTINGS: 'read:settings',
  WRITE_SETTINGS: 'write:settings',

  // User-composed mail sent through the instance's own SMTP account. The
  // system-generated welcome/notification/digest mails need no permission,
  // they are never user-authored. Rate-limited on top of this gate.
  SEND_MAIL: 'send:mail',

  // Write covers printers and their templates, archiving and restoring included.
  WRITE_PRINTERS: 'write:printers',
  PRINT_DOCUMENTS: 'print:documents',

  // The SolidWorks PDM add-in: sending change notifications and reading the
  // sync history of the files it names. It is the whole add-in token preset
  // each vault user signs in with, never write:settings or anything
  // item-shaped. See RequestPdmFileRefresh and ListPdmFileHistory.
  USE_PDM_ADDIN: 'use:pdm_addin',

  // The EPLAN Data Portal lookups: the search in the bought item create
  // dialog, the add-in's match on a number and a part's picture. Creating
  // the item still needs write:bought_items, and the lookup on an existing
  // item follows that item's own write permission.
  USE_DATA_PORTAL: 'use:data_portal',

  // Wall displays. Connecting is the device's own permission, held only by
  // the service account of a terminal key and never granted to a person, a
  // PAT or a normal API key. Managing covers approving, assigning, reloading,
  // identifying, revoking and deleting terminals; writing infoscreens covers
  // building and archiving the screens they show.
  CONNECT_TERMINALS: 'connect:terminals',
  MANAGE_TERMINALS: 'manage:terminals',
  WRITE_INFOSCREENS: 'write:infoscreens',

  ALL: [
    'write:bought_items',
    'delete:bought_items',
    'write:made_items',
    'delete:made_items',
    'write:source_items',
    'delete:source_items',
    'write:source_item_types',
    'write:demand_items',
    'manage:demand_items',
    'write:orders',
    'manage:orders',
    'receive:deliveries',
    'write:lots',
    'manage:lots',
    'write:inspections',
    'write:machines',
    'write:production_orders',
    'manage:production_orders',
    'write:allocations',
    'write:suppliers',
    'delete:suppliers',
    'read:contacts',
    'write:contacts',
    'write:article_groups',
    'write:fabrication_methods',
    'write:inspection_methods',
    'write:product_device_resources',
    'write:projects',
    'manage:projects',
    'write:meetings',
    'manage:meetings',
    'write:calculations',
    'release:calculations',
    'manage:calculations',
    'write:checklists',
    'release:checklists',
    'manage:checklists',
    'write:sequences',
    'release:sequences',
    'manage:sequences',
    'write:pat',
    'manage:api_keys',
    'use:mcp',
    'read:settings',
    'write:settings',
    'send:mail',
    'write:printers',
    'print:documents',
    'use:pdm_addin',
    'use:data_portal',
    'connect:terminals',
    'manage:terminals',
    'write:infoscreens',
  ] as const,

  /**
   * Permissions never grantable to an API key or PAT, settings access and
   * the ability to mint/revoke further keys are reserved for interactive
   * human sessions. Connecting terminals belongs to terminal keys alone,
   * which only the Create Terminal Key action mints. Mirrors
   * NEVER_GRANTABLE_TO_TOKENS on the backend.
   */
  NEVER_GRANTABLE_TO_TOKENS: [
    'read:settings',
    'write:settings',
    'manage:api_keys',
    'connect:terminals',
  ] as const,
} as const
