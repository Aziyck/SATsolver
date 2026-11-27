# do-item evals

Six cases that check how `/do-item` picks and refuses work, offline. Each
case runs in an empty workspace that its `world.sh` fills with a small
fixture repository: a plan with `Issues: #20`, issues saved as the JSON
`gh` would print (`.gh/`, mapped in `.gh/README.md`), one file item pair
(F1 blocked by F2), and a one-line bug in `calc.py`.

| Case | Checks |
|---|---|
| `refuses-blocked-issue` | `#22` is blocked by the open `#23`: no file changes, the blocker is named |
| `stops-at-needs-decision` | `#30` has `needs-decision`: the owner is asked, with the recommendation |
| `hands-hard-issue-to-opus` | `#31` is hard: the reply names `/do-item-hard #31` |
| `picks-first-issue-that-can-start` | plan `widgets`: `#21` closed, `#22` blocked, so `#23` |
| `fixes-easy-issue-test-first` | `#40`: the test is written before `calc.py` is fixed; `Fixes #40` |
| `finds-file-item` | the file ID `F1` is still found in `findings.md` (until MIG-5) |

Run from the repository root:

```bash
claude plugin eval .claude/skills/do-item --scaffold --trust-plugin \
  --allow-tools Write Edit Bash --ablation none --no-publish [--runs 1] [--case <name>]
```

`--scaffold` runs each case's `world.sh` (it is ours). Only
`fixes-easy-issue-test-first` writes files; it needs the `--allow-tools`
grant. Bash runs only where `claude plugin eval` has an OS sandbox (Linux,
macOS, WSL2): on native Windows a Bash grant fails every case before it
starts, so grant `Write Edit` only there. Results go to `evals/results/`
(ignored by git).

`_fixture/world.sh` is the one source of the fixture. The runner takes a
scaffold only from inside its case folder, so each case holds a copy; after
editing the source, copy it into every case.
`tests/test_eval_fixtures.py` fails while a copy differs.
