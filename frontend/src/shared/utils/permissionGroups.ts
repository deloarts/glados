import { Permission } from '@/core/auth/permissions'

/**
 * The permissions the account page explains, grouped by area. Every entry of
 * `Permission.ALL` belongs to one group (a spec keeps it that way); read
 * access that every user has is listed as always granted, so each group
 * shows what can be done without a permission too.
 */

export interface PermissionEntry {
  key: string
  descriptionKey: string
  alwaysGranted?: boolean
}

export interface PermissionGroup {
  titleKey: string
  icon: string
  permissions: PermissionEntry[]
}

function granted(key: string): PermissionEntry {
  return {
    key,
    descriptionKey: `accountMe.permissions.desc.${key.replace(':', '_')}`,
    alwaysGranted: true,
  }
}

function perm(key: string): PermissionEntry {
  return { key, descriptionKey: `accountMe.permissions.desc.${key.replace(':', '_')}` }
}

export const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    titleKey: 'accountMe.permissions.groups.boughtItems',
    icon: 'mdi-package-variant',
    permissions: [
      granted('read:bought_items'),
      perm(Permission.WRITE_BOUGHT_ITEMS),
      perm(Permission.DELETE_BOUGHT_ITEMS),
      perm(Permission.USE_DATA_PORTAL),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.madeItems',
    icon: 'mdi-factory',
    permissions: [
      granted('read:made_items'),
      perm(Permission.WRITE_MADE_ITEMS),
      perm(Permission.DELETE_MADE_ITEMS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.sourceItems',
    icon: 'mdi-cube-outline',
    permissions: [
      granted('read:source_items'),
      perm(Permission.WRITE_SOURCE_ITEMS),
      perm(Permission.DELETE_SOURCE_ITEMS),
      perm(Permission.WRITE_SOURCE_ITEM_TYPES),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.demandItems',
    icon: 'mdi-cart-arrow-down',
    permissions: [
      granted('read:demand_items'),
      perm(Permission.WRITE_DEMAND_ITEMS),
      perm(Permission.MANAGE_DEMAND_ITEMS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.orders',
    icon: 'mdi-clipboard-list',
    permissions: [
      granted('read:orders'),
      perm(Permission.WRITE_ORDERS),
      perm(Permission.MANAGE_ORDERS),
      perm(Permission.RECEIVE_DELIVERIES),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.allocations',
    icon: 'mdi-source-branch',
    permissions: [granted('read:allocations'), perm(Permission.WRITE_ALLOCATIONS)],
  },
  {
    titleKey: 'accountMe.permissions.groups.suppliers',
    icon: 'mdi-truck',
    permissions: [
      granted('read:suppliers'),
      perm(Permission.WRITE_SUPPLIERS),
      perm(Permission.DELETE_SUPPLIERS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.contacts',
    icon: 'mdi-card-account-mail-outline',
    permissions: [perm(Permission.READ_CONTACTS), perm(Permission.WRITE_CONTACTS)],
  },
  {
    titleKey: 'accountMe.permissions.groups.productionLots',
    icon: 'mdi-factory',
    permissions: [granted('read:lots'), perm(Permission.WRITE_LOTS), perm(Permission.MANAGE_LOTS)],
  },
  {
    titleKey: 'accountMe.permissions.groups.productionOrders',
    icon: 'mdi-factory',
    permissions: [
      granted('read:production_orders'),
      perm(Permission.WRITE_PRODUCTION_ORDERS),
      perm(Permission.MANAGE_PRODUCTION_ORDERS),
      perm(Permission.WRITE_INSPECTIONS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.machines',
    icon: 'mdi-cog-outline',
    permissions: [
      granted('read:machines'),
      perm(Permission.WRITE_MACHINES),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.articleGroups',
    icon: 'mdi-tag-multiple',
    permissions: [
      granted('read:article_groups'),
      perm(Permission.WRITE_ARTICLE_GROUPS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.fabricationMethods',
    icon: 'mdi-cog',
    permissions: [
      granted('read:fabrication_methods'),
      perm(Permission.WRITE_FABRICATION_METHODS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.inspectionMethods',
    icon: 'mdi-magnify-scan',
    permissions: [
      granted('read:inspection_methods'),
      perm(Permission.WRITE_INSPECTION_METHODS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.productDeviceResources',
    icon: 'mdi-engine-outline',
    permissions: [
      granted('read:product_device_resources'),
      perm(Permission.WRITE_PRODUCT_DEVICE_RESOURCES),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.projects',
    icon: 'mdi-folder',
    permissions: [
      granted('read:projects'),
      perm(Permission.WRITE_PROJECTS),
      perm(Permission.MANAGE_PROJECTS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.meetings',
    icon: 'mdi-account-group-outline',
    permissions: [
      granted('read:meetings'),
      perm(Permission.WRITE_MEETINGS),
      perm(Permission.MANAGE_MEETINGS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.calculations',
    icon: 'mdi-calculator-variant-outline',
    permissions: [
      granted('read:calculations'),
      perm(Permission.WRITE_CALCULATIONS),
      perm(Permission.RELEASE_CALCULATIONS),
      perm(Permission.MANAGE_CALCULATIONS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.checklists',
    icon: 'mdi-clipboard-check-outline',
    permissions: [
      granted('read:checklists'),
      perm(Permission.WRITE_CHECKLISTS),
      perm(Permission.RELEASE_CHECKLISTS),
      perm(Permission.MANAGE_CHECKLISTS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.sequences',
    icon: 'mdi-sitemap-outline',
    permissions: [
      granted('read:sequences'),
      perm(Permission.WRITE_SEQUENCES),
      perm(Permission.RELEASE_SEQUENCES),
      perm(Permission.MANAGE_SEQUENCES),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.printing',
    icon: 'mdi-printer-outline',
    permissions: [
      perm(Permission.PRINT_DOCUMENTS),
      perm(Permission.WRITE_PRINTERS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.mail',
    icon: 'mdi-email-outline',
    permissions: [perm(Permission.SEND_MAIL)],
  },
  {
    titleKey: 'accountMe.permissions.groups.accessTokens',
    icon: 'mdi-key',
    permissions: [granted('read:pat'), perm(Permission.WRITE_PAT)],
  },
  {
    titleKey: 'accountMe.permissions.groups.apiKeys',
    icon: 'mdi-key-outline',
    permissions: [perm(Permission.MANAGE_API_KEYS)],
  },
  {
    titleKey: 'accountMe.permissions.groups.aiAgents',
    icon: 'mdi-robot-outline',
    permissions: [perm(Permission.USE_MCP)],
  },
  {
    titleKey: 'accountMe.permissions.groups.pdm',
    icon: 'mdi-file-cad-box',
    permissions: [perm(Permission.USE_PDM_ADDIN)],
  },
  {
    titleKey: 'accountMe.permissions.groups.terminals',
    icon: 'mdi-monitor-dashboard',
    permissions: [
      granted('read:terminals'),
      perm(Permission.MANAGE_TERMINALS),
      perm(Permission.CONNECT_TERMINALS),
    ],
  },
  {
    titleKey: 'accountMe.permissions.groups.infoscreens',
    icon: 'mdi-television-guide',
    permissions: [granted('read:infoscreens'), perm(Permission.WRITE_INFOSCREENS)],
  },
  {
    titleKey: 'accountMe.permissions.groups.settings',
    icon: 'mdi-shield-account',
    permissions: [perm(Permission.READ_SETTINGS), perm(Permission.WRITE_SETTINGS)],
  },
]
