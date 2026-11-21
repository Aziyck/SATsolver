---
name: defense-questions
description: "Log a question about the project as a committee question in docs/report/defense-questions.md, or quiz the owner on the logged ones."
argument-hint: "[a question; empty to sweep this session; quiz]"
disable-model-invocation: true
---

Defense questions: $ARGUMENTS

A question the owner had to ask about the project is a **committee
question**: one the thesis committee may ask at the defense. This skill keeps
them in `docs/report/defense-questions.md` and quizzes the owner on them. You
write that file; a guide or algorithm doc changes only after the owner
approves the exact lines.

A committee question is about the design, an algorithm, an encoding, a
result or a limitation. Syntax and tool use stay in the session.

## The file

If it is missing, create it with the title `# Defense questions` and one line
saying what it is for, and add its row to the table in
`docs/report/README.md`.

One entry per committee question:

```markdown
## <the question, as a committee member would ask it>

- Asked: YYYY-MM-DD
- Answer: <2-4 sentences the owner can say aloud in 30 seconds, in the terms of GLOSSARY.md>
- Evidence: `path/to/file.py:Symbol`
- Doc gap: none | proposed: <doc> | fixed: <doc>, <section>
- Confidence: shaky | ok | solid
```

A new entry starts `shaky`. When an entry already asks the same thing,
update that entry.

## 1. Pick the branch

- **A question:** usually right after a `/btw` answer, which the session does
  not keep, so the owner passes the question and maybe the gist of the
  answer. Rephrase it as a committee question and go to step 2.
- **Empty:** sweep this session. List, numbered, each question the owner
  asked to understand the project (why it works, what it does, why this over
  that), rephrased as a committee question. Task instructions are not
  questions. The owner picks; run steps 2 and 3 for each pick.
- **`quiz`:** go to step 4.

**Done when** the owner has confirmed the questions to log, or you are in
the quiz.

## 2. Answer from the code

Find the answer in the code and docs (`docs/README.md` is the index). Check a
`/btw` gist against them: `/btw` reads no files, so where the code disagrees,
the code wins and you tell the owner. Theory the code cannot settle (an
encoding's correctness, a complexity bound) goes into the Answer as
`Open: <question for the thesis partner>`.

**Done when** every sentence of the Answer rests on an Evidence line you
opened in this session.

## 3. Write the entry and the doc gap

Write the entry. Then judge whether `docs/guide/` or `docs/algorithms/`
should already answer the question. If so, propose the exact sentences and
where they go, and set `Doc gap: proposed: <doc>`. On the owner's yes, add
them and set `fixed`.

**Done when** the entry is in the file with its Doc gap set.

## 4. Quiz

Pick 3 entries: `shaky` first, then `ok`, oldest `Asked` first. One at a
time:

1. Ask the heading as the committee would, with the entry's Answer hidden,
   and wait for the owner's answer.
2. Grade it against the entry and the code: what held, what was missing,
   and the one sentence to add next time. A vague answer is a miss.
3. Move Confidence one level up for a full answer, one down for a miss.
   When the owner's answer shows the entry is wrong or stale, fix the entry.

**Done when** 3 entries (or all, if fewer) are graded, their Confidence is
updated, and you have listed the grades.
