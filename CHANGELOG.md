# Changelog

## 0.2.0

- Symlinks are never followed; a link leaving the skill is an error, and retargeting one is a high-risk change in `diff`
- `--format json` and `--format sarif` (SARIF 2.1.0, for GitHub code scanning); `sarif` input on the Action

## 0.1.0

- `check`: spec conformance, context budget, capability manifest, instruction flags
- `lock` / `diff`: per-skill hashes, description, allowed-tools, capabilities and URLs,
  with ranked changes and a CI-friendly exit code
- Composite GitHub Action
- Example skills and a labelled description-edit set
