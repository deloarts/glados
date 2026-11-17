# testing

The rules for backend and frontend tests: fixtures, fakes, database and Redis setup, mocks, test data and selectors. The concept is in [CONTRIBUTING.md section 7](../CONTRIBUTING.md#7-testing); commands, profiles and the Redis database are in [development-testing.md](development-testing.md). The lifecycle drift check, property suite and transition table are in [lifecycle.md section 7](lifecycle.md#7-drift-and-tests).

- [1 backend](#1-backend)
- [2 frontend](#2-frontend)

## 1 backend

- Tests need no Redis server. The integration suite fakes the event bus and the other Redis-backed ports, and `REDIS__URL` points at db 15, never the dev app's db 0.
- The database is a throwaway SQLite file, so the suite never needs Postgres, apart from the opt-in race tests under `tests/pg/`, which run against an empty throwaway Postgres database.
- Unit tests (`tests/unit/`) use fakes, not mocks of real infrastructure.
- The shared fixtures `fake_uow` and `fake_event_bus` are defined in `tests/unit/conftest.py` and so are available to unit tests only. `glados_caplog` is defined in `tests/conftest.py` for the whole suite.
- Use `glados_caplog`, never plain `caplog`, because the app logger has `propagate=False` and `caplog` sees nothing.
- Integration tests (`tests/integration/`) call the API through the unauthenticated `client` fixture, or through an authenticated one from `auth_client(permissions=[...])` named after who it acts as (`writer`, `manager`), and use the `db` fixture to arrange or assert state.
- The integration schema comes from the models (`Base.metadata.create_all`), not from migrations, so anything a test relies on must be declared on the model.
- Partial unique indexes need both `postgresql_where` and `sqlite_where`, otherwise they constrain nothing in tests.
- Name tests `test_<feature>_<behavior>`.
- If an existing test looks wrong after your change, raise it in review instead of quietly adjusting it.
- Cover a new read path and a new write with the tests [persistence.md](persistence.md) asks for in sections 1.5 and 1.7.

## 2 frontend

- Tests are Vitest with jsdom, and specs live in `__tests__/*.spec.ts` next to the code.
- Mount with `mountWithApp()` (`src/test-utils/mountWithApp.ts`), which wires Pinia, OpenVue, i18n and the toast service.
- A tab that `asyncTab()` loads lazily is mocked with `vi.mock(path, () => asyncTabStub(name))` from `src/test-utils/asyncTabStub.ts`, which explains why the module needs the `__esModule` flag.
- Call `await flushPromises()` after actions that trigger async work.
- Before each test Vitest restores every `vi.spyOn` spy and clears the call history of every mock (`restoreMocks` and `clearMocks` in `vitest.config.ts`), but it keeps implementations.
- A return value or implementation one test sets on a shared mock lasts into the next, so set it in `beforeEach`.
- Module state outlives a test too. A mock that hands out a shared fixture object returns a copy (`structuredClone`) when a test may change it, and a singleton such as the router or a module-level variable is reset in `beforeEach`.
- A spec has to pass in any test order (`npx vitest run <spec> --sequence.shuffle.tests`).
- CI runs the suite with coverage (`npm run test:coverage`) and fails below the thresholds in `vitest.config.ts`. Raise them as coverage grows.
- Build test data with factory functions, and type every `vi.fn()`.
- Shared factories for the common responses (user, order, production order, lot, demand, made item) and a memory-history test router live in `src/test-utils/factories`. New specs use them and pass the fields a test depends on as overrides, so the spec still shows them.
- Do not select on `.p-*` or `.mdi-*` classes. Use roles, labels, text or `data-testid`.
- When OpenVue renders the element, set the testid through the component's `pt` pass-through options.
- ESLint enforces the selector rule in specs. A spec that asserts on such a class itself, such as which icon a button shows, disables the line with a reason.
- Run one spec with `npm run test:unit:run -- src/path/__tests__/Foo.spec.ts`.
- `npm run test:visual` in `frontend/` takes screenshots of the key screens (the login page, the app shell with a catalogue table in both themes, a form dialog and the account page) and compares them with the baselines in `frontend/e2e/visual/baselines/`.
- It runs Playwright inside the pinned `mcr.microsoft.com/playwright` image, so fonts and rendering match on every machine. It needs Docker and runs on demand, not in CI.
- The tests serve a production build and answer every API request from `frontend/e2e/visual/fixtures.ts`, which is typed against the generated web schema. A request without a fixture fails the test, so a new request shows up as a failure rather than as an error toast in the picture. The browser clock is fixed, so dates on screen do not change.
- After a deliberate visual change, review the diffs in `frontend/test-results/` and accept them with `npm run test:visual -- --update-snapshots`.
- `npm run readme:media` in `frontend/` rebuilds the README pictures in `docs/assets/`: the dashboard in both themes and the animated tour. It captures them in the same pinned Playwright image from the made-up shop in `frontend/e2e/readme/fixtures.ts`, then `frontend/e2e/readme/assemble.py` builds the files, which needs Python with Pillow. Rerun it after a visible change to one of the screens the tour shows, and keep every name in the fixtures generic.
