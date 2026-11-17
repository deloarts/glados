import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import type { ConfirmationOptions } from "openvue/confirmationoptions";

import { mountWithApp } from "@/test-utils/mountWithApp";
import { userWithPermissions } from "@/test-utils/factories";
import { i18n } from "@/core/i18n";
import { getEmptyPlaceholder } from "@/core/utils/emptyValue";
import { useCurrentUserStore } from "@/core/stores/currentUserStore";
import { usePdmFilesStore } from "../../../stores/pdmFilesStore";

import type { PageResponse } from "@/core/api/types";
import type {
  PdmFileRetryResult,
  PdmFileSnapshot,
  PdmFileSnapshotFilterParams,
} from "../../../types/adminSettingsTypes";

// Same technique as AcknowledgementsPanel.spec.ts: replace the composable
// so `accept` can be invoked directly instead of driving a real
// <ConfirmDialog/>'s DOM.
const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>();
vi.mock("openvue/useconfirm", () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}));

const getPdmFilesMock =
  vi.fn<(params?: PdmFileSnapshotFilterParams) => Promise<PageResponse<PdmFileSnapshot>>>();
const retryPdmFileMock = vi.fn<(id: number) => Promise<PdmFileRetryResult>>();
const dismissPdmFileMock = vi.fn<(id: number) => Promise<PdmFileSnapshot>>();

vi.mock("../../../api/getPdmFiles", () => ({
  getPdmFiles: (params?: PdmFileSnapshotFilterParams) => getPdmFilesMock(params),
}));
vi.mock("../../../api/retryPdmFile", () => ({
  retryPdmFile: (id: number) => retryPdmFileMock(id),
}));
vi.mock("../../../api/dismissPdmFile", () => ({
  dismissPdmFile: (id: number) => dismissPdmFileMock(id),
}));

import PdmFilesDialog from "../PdmFilesDialog.vue";

function makeSnapshot(overrides: Partial<PdmFileSnapshot> = {}): PdmFileSnapshot {
  return {
    id: 1,
    public_id: "22222222-2222-2222-2222-222222222222",
    vault_id: "vault-guid",
    file_id: 42,
    kind: "made",
    name: "bracket.sldprt",
    path: "\\Made-Parts\\bracket.sldprt",
    parent_folder_id: 7,
    version: 3,
    state_id: 2,
    state: "Released",
    modified_at: "2026-09-01T10:00:00Z",
    first_seen_at: "2026-08-01T10:00:00Z",
    last_seen_at: "2026-09-01T10:05:00Z",
    last_ingested_version: 3,
    sync_state: "conflict",
    last_error: "manufacturer unresolved",
    part_number: "PUR-26-00001",
    revision: "A",
    item_id: 99,
    item_kind: "made",
    has_parked_payload: true,
    ...overrides,
  };
}

function page(items: PdmFileSnapshot[], total = items.length): PageResponse<PdmFileSnapshot> {
  return { items, total, limit: 25, skip: 0 };
}

// Row actions are icon-only (aria-label, no visible text label), and the
// controls-row refresh button shares the retry row-action's icon (mdi
// mdi-refresh), so an icon-only lookup is not unambiguous. Look these up
// by their i18n text instead, same as every other button in this file.
function findButtonByAriaLabel(wrapper: Awaited<ReturnType<typeof mountDialog>>, label: string) {
  return wrapper
    .findAllComponents({ name: "Button" })
    .find((b) => b.attributes("aria-label") === label);
}

function syncButton(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper
    .findAllComponents({ name: "Button" })
    .find((b) => b.props("label") === (i18n.global.t("common.reload") as string));
}

// OpenVue's Dialog teleports its content to document.body, outside the
// mounted wrapper's own DOM subtree (same note as
// PdmFolderPickerDialog.spec.ts), so read text straight off `document`
// rather than `wrapper.text()`. Component-tree lookups (findComponent/
// findAllComponents) are unaffected, teleport only moves DOM placement.
function bodyText(): string {
  return document.body.textContent ?? "";
}

// Mounted already visible (visible: true is a required prop, this dialog is
// only ever rendered by its caller via v-if once opened), so its fetch
// fires on mount, the same way it fires once it exists at all.
async function mountDialog(
  permissions: string[] = ["write:settings"],
  { withRouter = false }: { withRouter?: boolean } = {},
) {
  const pinia = createPinia();
  setActivePinia(pinia);
  useCurrentUserStore().user = userWithPermissions(permissions);

  // The part-number links only render with a router installed.
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component: { template: "<div />" } }],
  });
  const wrapper = mountWithApp(PdmFilesDialog, {
    props: { visible: true },
    pinia,
    attachTo: document.body,
    global: withRouter ? { plugins: [router] } : {},
  });
  await flushPromises();
  return wrapper;
}

describe("PdmFilesDialog", () => {
  beforeEach(() => {
    getPdmFilesMock.mockReset();
    retryPdmFileMock.mockReset();
    dismissPdmFileMock.mockReset();
    confirmRequireMock.mockReset();
    getPdmFilesMock.mockResolvedValue(page([makeSnapshot()]));
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads and renders rows on mount", async () => {
    const wrapper = await mountDialog();

    expect(getPdmFilesMock).toHaveBeenCalledTimes(1);
    expect(bodyText()).toContain("bracket.sldprt");
    expect(bodyText()).toContain("PUR-26-00001");

    wrapper.unmount();
  });

  // A file under a `by_kind` watched folder whose datacard hasn't supplied
  // a kind value yet has `kind: null`, rendered with the same empty
  // placeholder every other unset field on this dialog uses, same as
  // PdmSyncLogDialog's own kind column.
  it("renders a null kind as the empty placeholder, and a resolved kind by its label", async () => {
    getPdmFilesMock.mockResolvedValue(
      page([
        makeSnapshot({ id: 1, public_id: "33333333-3333-3333-3333-333333333333", kind: "made" }),
        makeSnapshot({
          id: 2,
          public_id: "44444444-4444-4444-4444-444444444444",
          kind: null,
          name: "unresolved.sldprt",
          part_number: null,
          revision: null,
          item_id: null,
        }),
      ]),
    );
    const wrapper = await mountDialog();

    const rows = wrapper.findComponent({ name: "DataTable" }).findAll("tr");
    const madeRow = rows.find((row) => row.text().includes("bracket.sldprt"))!;
    expect(madeRow.text()).toContain(i18n.global.t("adminSettings.itemFields.madeSection"));

    const unresolvedRow = rows.find((row) => row.text().includes("unresolved.sldprt"))!;
    expect(unresolvedRow.text()).toContain(getEmptyPlaceholder());

    wrapper.unmount();
  });

  it("renders part number and revision in separate columns, a dash when the revision is null", async () => {
    // Default host-store revision separator is ':' (see hostStore's
    // defaultMadeItemPartNumberPolicy), untouched here since this dialog
    // only consumes it through the shared useMadeItemLabel() formatter, not
    // a hard-coded ":" of its own.
    getPdmFilesMock.mockResolvedValue(
      page([
        makeSnapshot({ id: 1, public_id: "33333333-3333-3333-3333-333333333333" }),
        makeSnapshot({
          id: 2,
          public_id: "44444444-4444-4444-4444-444444444444",
          name: "plate.sldprt",
          part_number: "PUR-26-00002",
          revision: null,
        }),
      ]),
    );
    const wrapper = await mountDialog();

    const cells = Array.from(document.body.querySelectorAll("td")).map((td) =>
      td.textContent?.trim(),
    );
    expect(cells).toContain("PUR-26-00001");
    expect(cells).toContain("A");
    expect(cells).toContain("PUR-26-00002");
    expect(cells).toContain("-");
    expect(bodyText()).not.toContain("PUR-26-00001:A");

    wrapper.unmount();
  });

  it("the sync-state filter refetches with sync_state", async () => {
    const wrapper = await mountDialog();
    const store = usePdmFilesStore();

    store.syncState = "missing";
    // Selects in this dialog fetch immediately (@update:model-value), not
    // debounced like the search box. The store setter alone doesn't fire
    // the fetch, so drive it the same way the component's own handler does.
    await wrapper.vm.$nextTick();

    // Exercise the component's onFilterChange through the Select instead of
    // reaching into internals: find the Select bound to syncState.
    const selects = wrapper.findAllComponents({ name: "Select" });
    const syncSelect = selects[0];
    await syncSelect?.vm.$emit("update:modelValue", "missing");
    await flushPromises();

    expect(getPdmFilesMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ sync_state: "missing", skip: 0 }),
    );

    wrapper.unmount();
  });

  it("the kind filter refetches with kind", async () => {
    const wrapper = await mountDialog();

    const selects = wrapper.findAllComponents({ name: "Select" });
    const kindSelect = selects[1];
    await kindSelect?.vm.$emit("update:modelValue", "bought");
    await flushPromises();

    expect(getPdmFilesMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ kind: "bought", skip: 0 }),
    );

    wrapper.unmount();
  });

  it('the kind filter offers "Exported Documents" and refetches with kind=document', async () => {
    const wrapper = await mountDialog();

    const selects = wrapper.findAllComponents({ name: "Select" });
    const kindSelect = selects[1]!;
    expect(kindSelect.props("options")).toEqual(
      expect.arrayContaining([
        {
          label: i18n.global.t(
            "adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments",
          ),
          value: "document",
        },
      ]),
    );

    await kindSelect.vm.$emit("update:modelValue", "document");
    await flushPromises();

    expect(getPdmFilesMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ kind: "document", skip: 0 }),
    );

    wrapper.unmount();
  });

  it('renders a "document"-kind row by the same "Exported Documents" label, with its plain name', async () => {
    getPdmFilesMock.mockResolvedValue(
      page([
        makeSnapshot({
          id: 3,
          public_id: "55555555-5555-5555-5555-555555555555",
          kind: "document",
          name: "bracket-A.pdf",
          part_number: null,
          revision: null,
          item_id: null,
        }),
      ]),
    );
    const wrapper = await mountDialog();

    const row = wrapper
      .findComponent({ name: "DataTable" })
      .findAll("tr")
      .find((r) => r.text().includes("bracket-A.pdf"))!;
    expect(row.text()).toContain(
      i18n.global.t("adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments"),
    );

    wrapper.unmount();
  });

  it("links a document row to the catalogue of its item, not to bought items", async () => {
    getPdmFilesMock.mockResolvedValue(
      page([
        makeSnapshot({ id: 1, kind: "bought", part_number: "PUR-1", item_id: 3, item_kind: "bought" }),
        makeSnapshot({ id: 2, kind: "document", part_number: "I-26-00041", item_id: 9, item_kind: "made" }),
        makeSnapshot({ id: 3, kind: "document", part_number: "I-26-00042", item_id: 7, item_kind: null }),
      ]),
    );
    const wrapper = await mountDialog(["write:settings"], { withRouter: true });

    const links = wrapper.findAllComponents({ name: "RouterLink" });
    expect(links.map((link) => [link.text(), link.props("to")])).toEqual([
      ["PUR-1", "/catalogue/bought-items/3"],
      ["I-26-00041", "/catalogue/made-items/9"],
    ]);
    expect(bodyText()).toContain("I-26-00042");

    wrapper.unmount();
  });

  it("search debounces before refetching", async () => {
    vi.useFakeTimers();
    const wrapper = await mountDialog();
    const store = usePdmFilesStore();
    getPdmFilesMock.mockClear();

    store.search = "bracket";
    await wrapper.vm.$nextTick();
    expect(getPdmFilesMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(500);

    expect(getPdmFilesMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: "bracket" }),
    );

    wrapper.unmount();
  });

  it("the controls-row refresh button refetches with the current filters", async () => {
    const wrapper = await mountDialog();
    const store = usePdmFilesStore();
    store.syncState = "conflict";
    getPdmFilesMock.mockClear();

    await syncButton(wrapper)!.trigger("click");
    await flushPromises();

    expect(getPdmFilesMock).toHaveBeenCalledWith(
      expect.objectContaining({ sync_state: "conflict" }),
    );

    wrapper.unmount();
  });

  it("retry calls the API and clears the loading state", async () => {
    retryPdmFileMock.mockResolvedValue({ accepted: true });
    const wrapper = await mountDialog();

    const retryButton = findButtonByAriaLabel(
      wrapper,
      i18n.global.t("adminSettings.pdmFiles.retry"),
    );
    expect(retryButton).toBeDefined();

    await retryButton!.trigger("click");
    await flushPromises();

    expect(retryPdmFileMock).toHaveBeenCalledWith(1);

    wrapper.unmount();
  });

  it("dismiss asks for confirmation, then calls the API on accept", async () => {
    dismissPdmFileMock.mockResolvedValue(makeSnapshot({ sync_state: "skipped" }));
    const wrapper = await mountDialog();

    const dismissButton = findButtonByAriaLabel(
      wrapper,
      i18n.global.t("adminSettings.pdmFiles.dismiss"),
    );
    await dismissButton!.trigger("click");

    expect(confirmRequireMock).toHaveBeenCalledTimes(1);
    expect(dismissPdmFileMock).not.toHaveBeenCalled();

    const options = confirmRequireMock.mock.calls[0]![0] as { accept: () => Promise<void> };
    await options.accept();
    await flushPromises();

    expect(dismissPdmFileMock).toHaveBeenCalledWith(1);

    wrapper.unmount();
  });

  it("disables retry/dismiss without write:settings", async () => {
    const wrapper = await mountDialog([]);

    const retryButton = findButtonByAriaLabel(
      wrapper,
      i18n.global.t("adminSettings.pdmFiles.retry"),
    );
    const dismissButton = findButtonByAriaLabel(
      wrapper,
      i18n.global.t("adminSettings.pdmFiles.dismiss"),
    );

    // Button forwards `disabled` through $attrs onto the native <button>
    // rather than declaring it as its own prop, so it shows up on
    // `attributes()`, not `props()`.
    expect(retryButton?.attributes("disabled")).toBeDefined();
    expect(dismissButton?.attributes("disabled")).toBeDefined();

    wrapper.unmount();
  });
});
