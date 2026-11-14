import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider, type QueryKey } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { theme } from "../theme";

export interface AppRenderOptions extends Omit<RenderOptions, "wrapper"> {
  /** Server data the component reads through React Query, e.g. [["job", 7], job]. */
  queryData?: Array<[QueryKey, unknown]>;
}

/**
 * Render a component inside the providers the app gives it (Mantine theme,
 * React Query, a router). Each call gets a fresh query client without
 * retries, so one test's cache or a failing stub never leaks into another.
 * Seeded queryData never goes stale: tests have no server to refetch from.
 */
export function renderWithApp(ui: ReactElement, { queryData = [], ...options }: AppRenderOptions = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const [key, data] of queryData) queryClient.setQueryData(key, data);
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MantineProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>{children}</MemoryRouter>
        </QueryClientProvider>
      </MantineProvider>
    );
  }
  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
