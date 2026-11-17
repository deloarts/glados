# design look

The exact rules of the Glados look: the page skeleton, tabs, buttons, tables, cards, dialogs and forms, feedback, settings tabs, the visual language and the copy. The idea behind it is in [CONTRIBUTING.md section 4.1](../CONTRIBUTING.md#41-the-glados-look). New views follow these rules; a deviation needs a reason and, if it is the better way, a change here first.

- [1 page skeleton](#1-page-skeleton)
- [2 tabs](#2-tabs)
- [3 buttons](#3-buttons)
- [4 tables](#4-tables)
- [5 cards](#5-cards)
- [6 dialogs and forms](#6-dialogs-and-forms)
- [7 settings tabs](#7-settings-tabs)
- [8 feedback](#8-feedback)
- [9 visual language](#9-visual-language)
- [10 copy](#10-copy)
- [11 phone layout](#11-phone-layout)

## 1 page skeleton

A page is a `PageLayout` with up to three bars above its content, in this order.

- The `InfoBar` (slot `#info`) is the identity strip of the record: its number or title in large type, then tags for revision and status, then muted facts such as owner, creator and date, separated by thin vertical dividers. An icon in front of its text, in a field or a tag, keeps `--space-2` to the text, and a divider keeps `--space-3` to the fields on either side. The `InfoBar` sets both for every caller.
- The `ControlsBar` (slot `#controls`) holds every action of the page.
- A tab never brings a toolbar of its own. Its actions fill the page's controls bar, as the Devices and Sequences tabs of a product do.
- On a page with tabs the record's own actions, such as Back to Products and Edit Product, show on its Overview tab only, and a tab without actions shows no controls bar at all.
- The primary actions come first, and secondary ones such as History, Print and Compare follow after a divider.
- A round handbook button at the bar's normal button size (`<HelpButton rounded />`) closes the controls bar. On a record's page a round share button before it (`ShareButton`) copies the record's lasting `/resolve` link.
- A list without actions, such as the production exceptions, has no controls bar, and its handbook button closes the views bar instead.
- The `ViewsBar` (slot `#views`) holds how a list is looked at: Sync, Views, Group By, Sort By, Show Actions and Clear. Lists with filtering, grouping or sorting have one, such as the catalogue and the orders.
- A detail page with many actions sets `wrap-menu` on its `PageLayout`, so its buttons wrap onto a new line as a whole instead of breaking their labels.

## 2 tabs

- A page with sub-views, such as a product or a project, has tabs, and the tab is part of the URL (`/workspace/products/4/devices`).
- The tab strip comes first, at the very top and flush to the edges of the content area as on the catalogue and procurement pages.
- Below the strip the active tab is a page of its own, in this order: the info bar of the record, the controls bar, the tab's views bar if it has one, and the content card. The strip that picks the tab therefore sits above the bars it changes.
- How a tab is looked at, such as the Devices tab's modes and Show Archived, goes into its views bar as toggle buttons whose pressed state means on.
- A page opened from a tab, such as a sequence or a checklist of a product, shows no tab strip. It is a page of its own with a way back to the tab.
- Tabs that fill a page take the `fill-tabs` class, and their panels have no background of their own and a `--space-2` padding from the theme preset.

## 3 buttons

- Buttons in the bars are text buttons with `severity="contrast"`, an `mdi` icon and a short label.
- Every button label is in Title Case in English ("New Sequence", "Show Archived", "Add Step").
- A button whose action the user lacks the rights for stays visible and disabled, with the missing permission in its tooltip.
- A button is hidden only when the record's state rules the action out, such as Edit on a released revision.
- A destructive action asks first in a confirm dialog with a header, one sentence, Cancel as a secondary button and the action in its severity, danger for Delete.

## 4 tables

- A `DataTable` sits inside a card, the page's content card or a `flush` `SectionCard`, and never on the bare page.
- A `DataTable` is `size="small"` and scrolls inside the height left to it (`scrollable`, `scroll-height="flex"`).
- A table is paginated with `TABLE_ROWS_PER_PAGE_OPTIONS`, and its paginator shows even when every row fits on one page (`always-show-paginator`).
- Gridlines and stripes follow the user's layout settings (`useLayoutStore`).
- A table spans its container with a muted `#` row number first (`body-class="row-number"`, styled once in `main.scss`), counted across pages (`first + index + 1`).
- Columns are as wide as their content (`class="column-fit"`), and a trailing empty column takes the width left, so the table spans its card while its columns stay narrow and the free space sits on the right.
- Cells have `--space-3` of padding on either side, so columns that fit their content still read as separate columns.
- An item cell looks the same in every table: the part number, a bought item's order code or a raw material's dimension in bold as a link that opens the item, the article name or material small and muted below it, and the item's thumbnail in a column without a header before it when file storage is on.
- Links in a table, such as a part number, a project or a lot, are in the text colour and show the primary colour with an underline only on hover.
- Clicking a row opens the record, and such a table takes the `clickable-rows` class for the pointer over its rows.
- The context menu keeps one shape: Open and Open in New Tab, then editing and history, then the document steps, then Delete, with the steps a row cannot take shown disabled.
- An empty table or panel shows `EmptyState`, a list missing from a detail section shows a short `.empty-note`, and a missing value shows `getEmptyPlaceholder()` in muted text.
- Lists follow other users' changes live ([frontend-conventions.md section 8](frontend-conventions.md#8-state-and-live-updates)), quietly, without the loading bar.

## 5 cards

- A page whose data area is several cards (`PageLayout :card="false"`) builds each one with `SectionCard`.
- `SectionCard` carries its title inside the card, an optional icon before it and an optional hint below it, in the same style as the blocks of an Overview tab (`OverviewSection`).
- A title never sits above a card, and a card never styles its own title.
- A count, a tag or an info icon next to the title goes into the `#title-end` slot.
- A card that holds a table is `flush`.
- Cards that share the height of a page, such as the two tables of the sessions page, are `fill`, so they split it evenly and each table scrolls inside its own card.

## 6 dialogs and forms

- Dialogs are modal and take a `--dialog-width-*` token.
- The buttons sit in the dialog's `#footer` slot, outside the content that scrolls, so they stay visible however long the form is.
- The footer has Cancel as a secondary text button and the main action with its icon after it.
- The dialog stays open on an error, which shows as a `Message` in the footer left of the buttons, so it is visible however far the form is scrolled.
- A dialog that groups its fields does so in `fieldset.dialog-section` boxes with a legend each, every group in the same box, so one dialog never mixes styles.
- In a form the label sits above its field, and fields are `fluid`.
- A hint is small muted text below the field, and an error is small red text below that shows after the first submit.
- A computed result that matters, such as a device's name preview, sits in a visible box beside its inputs, not in a note.

## 7 settings tabs

How a settings tab is registered and when it leaves the shell is in [recipes.md section 5](recipes.md#5-add-an-admin-settings-tab).

- An admin settings tab renders in `AdminSettingsTabShell`: a `Toolbar` in `#controls` with Save as a text button in its `#start` slot, disabled without write permission, and a card below whose body scrolls on its own.
- A form tab lays its fields out in a `.settings-fields` column, with the global styles in `assets/styles/main.scss`.
- A `.section-label` (small, uppercase, muted) heads each group, and a `Divider` separates the groups.
- A `.hint` paragraph under a section label explains the group in one or two sentences.
- Each field is a `.field-row`: a 16rem label column and a value column, the input at most 24rem wide.
- A field hint sits in the label as `small.hint`, and a live example or result, such as a rendered number format, sits next to the input.
- A switch is a `.field-row--toggle` with the `ToggleSwitch` between label and hint.
- On narrow screens the label goes above its value.
- A warning about the values entered, such as two overlapping patterns, is a `Message` with `severity="warn"` under the field it concerns.
- A table tab passes `table` to the shell, and a tab that is a full resource view of its own leaves the shell.

## 8 feedback

- Success and error toasts carry the record's name as title and one sentence as message.
- A server error shows the server's text.
- Page notices, such as an edit lock or an invalid or older revision, are `Message` components above the content, with a link where one helps.

## 9 visual language

- Components are OpenVue, and colours are its CSS variables (`--p-text-muted-color`, `--p-content-border-color` and the like), so dark mode needs nothing extra.
- Spacing stays small and comes from the `--space-*` scale, for gaps as for padding and margins: `--space-1` to `--space-3` inside a block, `--space-4` and up between layout blocks, and grids only for real matrices such as a field row.
- Body text is Segoe UI, then Calibri, then Inter. The Windows fonts come first because ClearType hinting keeps them crisp at small sizes, where Inter looks soft on a 100% scaled screen; Inter is bundled with the app and covers machines without them. Headings use Play and the wordmark Audiowide.
- The shared classes have one look everywhere: `.field` is a form field with its label above the input, `.field-label` the small uppercase caption above a read-only value, `.hint` a small muted sentence that explains a field or a section, `.field-hint` the smaller note under one input, `.form-grid` two columns of fields, `.panel-title` a panel's heading, `.row-actions` the icon buttons at the end of a table row and `.empty-note` a short muted note in place of a list or a value that is not there yet.
- Status tags use `warn` for draft, `success` for released, `secondary` for superseded, `danger` for invalid and `info` for editing.
- Icons are Material Design Icons: `mdi-plus` adds, `mdi-pencil` edits, `mdi-delete-outline` deletes, `mdi-archive-outline` archives and `mdi-history` opens the history.

## 10 copy

- English labels and headers are Title Case, and messages and hints are sentences.
- German copy follows [frontend-conventions.md section 7](frontend-conventions.md#7-german-copy-and-language).

## 11 phone layout

A phone gets a reduced set of pages under the same URLs, not a squeezed desktop. A phone is a screen at or below `$bp-sm` (768px), which `usePhoneLayout()` (`core/composables/`) reads as `isPhone`.

- A route declares what a phone offers in `meta.phone`: `true` for the whole page, or `{ param, tabs }` for only the tabs that route param names. A route without it is built for the desktop.
- On a phone a desktop page renders `DesktopOnlyNotice` instead of the page, with a Show Anyway button. The page stays reachable through links, searches and scans, and Show Anyway shows it in full until the user leaves the route.
- A tabbed view filters its tab strip through `tabOffered(tab)`, which lists only the phone tabs while `phoneMode` is on. `phoneMode` is `isPhone` except on a page shown in full anyway.
- A tab route without its param counts as offered, so a view whose desktop default tab is not a phone tab opens on a phone tab when `phoneMode` is on, as the workspace opens on Projects.
- The bottom navigation (`AppBottomNav`) takes the footer's place, with Procurement, Production, Scan, Search and More. More opens the sidebar as an overlay, which always shows its labels, lists only the sections a phone offers and closes on navigation.
- The header hides its search field and scan button, since the search page brings its own field on a phone and the bottom navigation scans.
- Every dialog takes the full screen: the `--dialog-width-*` tokens are 100vw and `_openvue.scss` gives the dialogs the full height. A confirmation stays a card.
- The controls bar moves its `#start` and `#center` actions into one Actions menu that drops down below the bar, one action per row, and closes once an action runs. `#end` and `#handbook` keep their place. A page needs no phone code for this.
- The views bar keeps only Sync and Clear, as icon buttons, and the search box across the rest of the row while `phoneMode` is on. Views, grouping, sorting, Show Archived and the caller's extra buttons belong to the desktop table.
- A list a phone offers keeps its desktop table and marks it for the phone: the `DataTable` takes the class `phone-columns` and the two or three columns that identify a row take `phone-col` (a catalogue column sets `phone: true` in its column definition). Its row number column takes `phone-row-number` and its picture column `phone-thumbnail` (a catalogue column `phone: 'thumbnail'`), and both stay in front as narrow columns, since a picture is often the quickest way to recognise a part on the shop floor. In phone mode `_openvue.scss` hides every other column, the filter row and the selection column, shares the width between the phone columns and trims the paginator to its arrows and page numbers. The table keeps its own data loading, row click and grouping, so a page needs no phone code beyond the classes.
- A table whose cells are too rich to stand alone on a phone gets a phone list of its own instead: a `DataTable` with two or three columns, the row number and the item's picture in front, the record's number and name stacked beside them, a short paginator and no filters, selection or context menu. A tapped row opens the record's page rather than a dialog, so the back button returns to the list, and the page hides its controls and side panels when they only serve the desktop table. `LotsPhoneList` is the model.
- A board that is dragged on the desktop, such as the production queue, stacks its columns on a phone and does not drag there, since a drag fights the scrolling.
- A contact's e-mail address in a list is a `ContactLinks` cell: a mail link everywhere, and in phone mode the phone number below it as a call link. A tap on either link does not open the row.
- A record page drops a side panel that sits beside its main table, such as the order's note and files panel, in phone mode, so the table gets the width.
- Glados installs as an app from the browser. `index.html` links the web app manifest the backend builds at `/api/v1/public/branding/manifest.webmanifest` from the branding settings: the app name, and the branding favicon as the icon when it is an SVG or a square PNG of at least 192 pixels, otherwise the Glados icons in `public/icons/`. The app runs full screen with `viewport-fit=cover`, so the bottom navigation pads itself by `env(safe-area-inset-bottom)`. There is no service worker and nothing is cached offline, since a page must never show production data that is out of date.
- A tab strip on a record that does not fit a phone's width scrolls (`:scrollable="isPhone"`), as the lot record's does.
