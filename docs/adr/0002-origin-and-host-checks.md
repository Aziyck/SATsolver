# 0002. The server accepts only local Host and Origin values, and needs no token

- **Status:** Accepted (2026-11-13)
- **Decided by:** the repository owner, on the recommendation of audit item A1
  (`docs/reviews/2026-10-16-audit.md`)

## Context

The server listens on 127.0.0.1 and has no login, on the assumption that only
the user can reach it. A browser breaks that assumption: any page the user
visits can send requests to 127.0.0.1. A POST without a body needs no
permission, so a foreign page could cancel, rerun and delete jobs; the
WebSocket answered any page with every job and result; and because any `Host`
header was accepted, a hostile domain that resolves to 127.0.0.1 (DNS
rebinding) became same-origin with the app and got full access.

## Decision

Every request, static files and the WebSocket handshake included, passes two
checks in one middleware (`LocalOnlyGuard` in `sat_web/api.py`):

- **Host:** the `Host` header must be `localhost`, `127.0.0.1` or `[::1]`, on
  any port, or a name in `WIZSAT_ALLOWED_HOSTS` (the launcher adds its
  `--host` value there). Anything else gets 400. Names are compared exactly:
  no wildcards.
- **Origin:** a request that carries an `Origin` header must name one of the
  same hosts, with `http` or `https`, on any port. Anything else, `null`
  included, gets 403. A request without `Origin` is accepted.

There is no token and no login.

## Alternatives considered

- **A random token per server start, required on every request.** Safer: it
  also stops other programs and other users on the same machine. Set aside
  because it breaks plain `curl` and script use of the API, which the guides
  rely on, and the threat here is the browser, which the two header checks
  cover.
- **Checking the port as well** (only the server's own port and 5173). Set
  aside: the server may move to the next free port, the Vite port is
  configurable, and another local port is another program on the user's own
  machine, which can reach the API without a browser anyway.
- **CORS headers only.** They decide who may read a response, not whether the
  request runs: a cross-site POST without a body would still cancel jobs.
- **Starlette's `TrustedHostMiddleware` for the Host check** (the fix A1
  named). Set aside after review: it compares case-sensitively, older
  versions that `requirements.txt` still allows cut `[::1]:8000` at the
  first colon, it treats `*` entries as patterns while the Origin check
  compares exactly, and its 400 cannot name the setting to change.

## Consequences

- A page on another site can no longer send the app commands or read its
  answers, also through DNS rebinding.
- A plain GET without `Origin` still passes, so another site can show the
  app in a frame or load a GET route as an image. It cannot read the answer;
  audit item A13 covers the framing.
- Requests without `Origin` are trusted, so local programs and other local
  users can still use the API. That is accepted for a single-user tool.
- With `--host 0.0.0.0` the server cannot know the names other machines use
  for it; they must be listed in `WIZSAT_ALLOWED_HOSTS`, or those machines
  get 400.
- Tests and tools must address the server by an allowed name (`TestClient`
  defaults to `testserver`; `tests/test_api.py` uses `localhost:8000`).
- A new route or mount is covered automatically because the checks are
  middleware. Adding permissive CORS headers would undo part of this.
