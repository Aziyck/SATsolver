// Links inside the algorithm notes (docs/algorithms/*.md) are written for
// GitHub, relative to docs/algorithms/. In the app they become:
// - another note            -> /learn/<name>      (in-app route)
// - docs/visualisations/... -> /visualisations/... (served by the Python server)
// - any other repository doc -> its page on GitHub
// - absolute URLs and anchors stay as they are.

export const REPOSITORY_URL = "https://github.com/Aziyck/SATsolver/blob/main";

export interface LearnLink {
  href: string;
  internal: boolean;
}

export function learnLink(href: string, topics: string[]): LearnLink {
  if (/^[a-z]+:/i.test(href) || href.startsWith("#")) return { href, internal: false };
  const resolved = new URL(href, "https://repo/docs/algorithms/");
  const path = resolved.pathname;
  const note = path.match(/^\/docs\/algorithms\/([^/]+)\.md$/);
  if (note && topics.includes(note[1])) return { href: `/learn/${note[1]}${resolved.hash}`, internal: true };
  if (path.startsWith("/docs/visualisations/")) return { href: path.replace(/^\/docs/, "").replace(/index\.html$/, ""), internal: false };
  return { href: `${REPOSITORY_URL}${path}${resolved.hash}`, internal: false };
}
