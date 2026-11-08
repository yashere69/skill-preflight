# Reporting a security problem

Please use GitHub's private vulnerability reporting (the **Security** tab → "Report a
vulnerability") rather than a public issue, and attach the smallest skill folder that shows
it.

What counts here, because the tool itself would be the hole:

- skill-preflight reading, following or hashing anything outside the skill directory
  (symlinks, `..` paths, absolute paths in references)
- anything that makes it execute, import or evaluate content from a skill
- a crafted skill that crashes `lock` or `diff`, or makes `diff` report "no change" when a
  file's contents changed

What doesn't: a malicious instruction or script that `check` doesn't flag. skill-preflight
is not a malware scanner and says so on every run. A missed pattern is an ordinary issue,
and a test case for it is welcome.

There is no bounty. I'll reply within a week.
