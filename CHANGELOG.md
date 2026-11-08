# Changelog

## Unreleased

- `diff` with no lockfile says how to create one instead of printing a raw file error.
- `lock` refuses two skills with the same name. The lockfile is keyed by name, so one
  would silently have hidden the other.
- `diff` lists skills that are in the lockfile but no longer found.

## 0.3.0

Tested on Anthropic's public skills and Snyk's ToxicSkills demos (results/real-skills.md).

- Python scripts are read with `ast`: imports and calls count, comments and docstrings don't.
  Other languages are matched after comments are stripped. Findings give file and line.
- New rules: invisible Unicode tag characters (error, with the hidden text decoded),
  bidirectional overrides, zero-width runs, `` !`cmd` `` load-time execution, uploads of
  command output (error), request-capture hosts (error), more paste hosts.
- `instr.pipe-to-shell` is now an error.
- Fixed false positives seen on real skills: placeholder links like `[Title](URL)` and links
  inside quotes or code blocks reported as missing files; "token-counting" read as reading
  a token; credential paths in comments and docstrings; `urllib2` missed.

## 0.2.0

- Symlinks are never followed; a link leaving the skill is an error, and retargeting one is a high-risk change in `diff`
- `--format json` and `--format sarif` (SARIF 2.1.0, for GitHub code scanning); `sarif` input on the Action

## 0.1.0

- `check`: spec conformance, context budget, capability manifest, instruction flags
- `lock` / `diff`: per-skill hashes, description, allowed-tools, capabilities and URLs,
  with ranked changes and a CI-friendly exit code
- Composite GitHub Action
- Example skills and a labelled description-edit set
