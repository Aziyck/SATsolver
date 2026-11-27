# `/write-plan review <PR#>`

Answer the owner's review comments on a design doc pull request: reply to
questions, edit the doc for changes, push, resolve the threads you handled.
The doc stays a draft; the merge is the owner's.

## 1. Find the threads

1. `gh pr view <PR#> --json state,headRefName,files`. The pull request is
   open and its branch starts with `plan/`; otherwise stop and say what it
   is.
2. A clean working tree, then note the current branch and
   `gh pr checkout <PR#>`. You return to the noted branch in section 4.
3. The threads still open:

   ```bash
   gh api graphql -F owner='{owner}' -F repo='{repo}' -F number=<PR#> -f query='
   query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){
   pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved isOutdated path line
   comments(last:50){nodes{author{login} body}}}}}}}'
   ```

   A thread is yours to handle when it is not resolved and its last comment
   does not start with `**Claude:** ` (an answered thread waits for the
   owner). A comment on an outdated line (`isOutdated`): find the passage by
   its words in the current doc.
4. The owner's other words: general comments on the pull request and the
   text of submitted reviews (`gh pr view <PR#> --json comments,reviews`).
   One is yours to handle when no later comment starts with `**Claude:** `.
   You answer it with `gh pr comment`, signed as in section 3, item 2; it
   has no thread to resolve.

**Done when** you have a list of the threads to handle, each with its file,
the passage it is about, and the owner's words.

## 2. Decide each thread

Read the passage and its section in the doc, and the code or doc it cites.
Then one of three:

- **Question:** answer it from the doc and the code, with the section or file
  that holds the answer. When the answer shows the doc is unclear or
  incomplete, it is also a change.
- **Change:** edit the doc so it says what the owner asked, in the form of
  [`DESIGN-DOC-FORMAT.md`](DESIGN-DOC-FORMAT.md): the failure path and the
  second solution stay, the header keeps `Issues: none yet` and has no
  `Status` field, and a decision that becomes hard to reverse gets its ADR
  in the same pull request. A change that follows from the comment on other
  lines of the doc is made there too.
- **Choice:** the comment asks for something that reverses a decision the
  owner made in the grilling, or that has two reasonable answers. Reply with
  the options, what each costs, and the recommended one; the thread stays
  open.

## 3. Push, reply, resolve

1. One commit for the edits, `Plan <name>: answer review comments`, and
   `git push`. No edits: no commit.
2. A reply per thread; every reply starts with `**Claude:** ` (`gh` is
   logged in as the owner, so the signature is how the owner tells your
   words from theirs). A change names what was edited and the commit's short
   hash.

   ```bash
   gh api graphql -F thread=<thread id> -f body='**Claude:** ...' -f query='
   mutation($thread:ID!,$body:String!){addPullRequestReviewThreadReply(input:{
   pullRequestReviewThreadId:$thread,body:$body}){comment{url}}}'
   ```

3. Resolve each thread you answered or changed (not a **Choice** thread):

   ```bash
   gh api graphql -F thread=<thread id> -f query='
   mutation($thread:ID!){resolveReviewThread(input:{threadId:$thread}){thread{isResolved}}}'
   ```

**Done when** every handled thread has a reply and is resolved, and the
edits are on the pull request branch.

## 4. Report

Run the query of section 1, item 3 again and check what it shows: the handled threads
are resolved, the **Choice** threads are open. Check out the branch you
noted. Report per thread: question, change or choice, and what you did;
then the threads still open, which are the owner's to settle. The next step
is the owner's: more comments and another `/write-plan review <PR#>`, or the
merge and then `/write-plan issues <name>`.
