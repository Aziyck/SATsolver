import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library unmounts after each test by itself only when vitest globals
// are on; this project imports describe/it explicitly, so do it here.
afterEach(cleanup);

// There is no server in tests. A component that fetches got data the test did
// not seed (renderWithApp's queryData); React Query would swallow the failed
// fetch and the test could pass on an empty screen, so fail it by name.
let unexpectedFetches: string[] = [];
globalThis.fetch = (input: RequestInfo | URL) => {
  const url = input instanceof Request ? input.url : String(input);
  unexpectedFetches.push(url);
  return Promise.reject(new Error(`no server in tests: ${url}`));
};
afterEach(() => {
  const urls = unexpectedFetches;
  unexpectedFetches = [];
  if (urls.length) throw new Error(`A test fetched ${urls.join(", ")}; seed that data with renderWithApp's queryData.`);
});

// jsdom has no matchMedia or ResizeObserver; Mantine uses both (color scheme,
// responsive props, floating elements). Inert stand-ins are enough to render.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
