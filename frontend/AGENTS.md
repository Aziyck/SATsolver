# Rules for `frontend/`

- Server data goes through React Query (`api/queries.ts`); live updates patch
  the cache in `api/live.ts`. Per-browser preferences go through
  `lib/storage.ts` (localStorage, wrapped in try/catch).
- Keep `api/types.ts` in sync with the JSON the API returns.
  `tests/test_wire_samples.py` records real payloads in
  `api/wireSamples.ts`, where `npm run typecheck` checks each against its
  type, missing and unknown fields alike (except inside values typed `any` or
  `Record<string, unknown>`). After a deliberate payload change,
  run that test with `WIZSAT_RECORD_GOLDEN=1`, then fix `types.ts`.
- Charts follow the dataviz rules already in `lib/palette.ts` and
  `components/charts/`: fixed categorical order, one y-axis (use facets
  instead of a second axis), a table view next to every chart, status colors
  only for statuses, text never in series colors.
- Pure logic lives in `lib/` with vitest tests; components stay thin.
  Component tests render through `renderWithApp()` (`src/test/render.tsx`)
  and use Testing Library queries.
- Parameter fields and statistic keys come from `GET /api/catalog`; never
  declare one here (root `AGENTS.md`, "Rules that hold everywhere").
