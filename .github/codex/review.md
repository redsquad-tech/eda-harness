Review only the changes introduced by this pull request. Compare the commits in
`$PR_BASE_SHA...$PR_HEAD_SHA`.

Focus on concrete defects: correctness bugs, regressions, security issues, data
loss risks, broken skill instructions, unsafe archive paths, packaging drift,
dependency drift, and missing tests for changed behavior. Check that both the
MCPB and Codex plugin contain every canonical skill. The MCPB must exclude Codex
metadata; the skills-only Codex plugin must exclude the MCP server, Node runtime,
tests, analytics, CI files, raw logs, caches, and PDK data.

Do not install dependencies or execute repository-controlled code. You may use
read-only inspection commands and safe Git commands such as `git diff`, `git log`,
`git show`, and `git grep`.

For each finding, provide:

- severity (`P0` critical through `P3` minor),
- file path and line number,
- a concise explanation of the failure mode,
- a specific suggested fix.

Do not report style preferences or speculative concerns. If there are no
actionable findings, say so explicitly. Keep the review concise.
