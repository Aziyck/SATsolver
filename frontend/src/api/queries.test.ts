import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";
import { applyEvents } from "./live";
import { rowsOptions } from "./queries";
import type { BenchmarkRow } from "./types";

type RowsReply = Awaited<ReturnType<typeof api.rows>>;

const row = (index: number) => ({ index }) as BenchmarkRow;

describe("rowsOptions", () => {
  afterEach(() => vi.restoreAllMocks());

  // A run compared on the results page is fetched through rowsOptions (finding A22).
  it("keeps a row streamed while the row list is being fetched", async () => {
    let reply!: (value: RowsReply) => void;
    vi.spyOn(api, "rows").mockReturnValue(new Promise<RowsReply>((done) => (reply = done)));
    const client = new QueryClient();

    const fetched = client.fetchQuery(rowsOptions(7));
    // The server took its snapshot before row 2 finished; the row event overtakes the reply.
    applyEvents([{ type: "row", job_id: 7, row: row(2) }], client);
    reply({ job_id: 7, label: "J7", rows: [row(0), row(1)] });
    await fetched;

    expect(client.getQueryData<RowsReply>(["rows", 7])?.rows.map((item) => item.index)).toEqual([0, 1, 2]);
  });
});
