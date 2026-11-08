# skill-preflight on real skills

Run on 8 November 2026 with skill-preflight 0.3.0, `python tools/real_skills.py <dir>`, on
a Linux container. Two public repositories:

- [anthropics/skills](https://github.com/anthropics/skills) at `2c5958e`: 19 skills
  published by Anthropic, assumed benign. Every security warning here is either a true
  observation or a false positive.
- [snyk-labs/toxicskills-goof](https://github.com/snyk-labs/toxicskills-goof) at
  `80ce2e0`: 8 demo skills from Snyk's ToxicSkills research. Six of them carry an attack:
  two fake Vercel skills post `uname -a` and `.env` to a paste site; a fake Snyk skill
  pipes downloads into `bash`; a ClawHub skill sends users to a paste site to "install";
  `testing-guidelines` hides instructions in invisible Unicode tag characters; and
  `skill-with-commands` uses `` !`cmd` `` load-time execution. `google` and
  `skill-defender` carry no attack (the second is a scanner full of example patterns).

## Anthropic's skills

One error, a true one: `claude-api`'s description is 1,068 characters, over the spec's
1,024. Thirteen warnings:

| Warning | Count | Verdict |
|---|---|---|
| body over 5,000 tokens / over 500 lines (`claude-api`, `skill-creator`) | 3 | true: the spec's guidance |
| a script reads an API key from the environment (`claude-api`) | 1 | true, and worth knowing before install |
| instructions that load docs from `raw.githubusercontent.com` (`mcp-builder`) | 6 | true by design: remote instructions can change after review |
| "read secrets" on lines that describe how the SDK reads `ANTHROPIC_API_KEY` (`claude-api`) | 3 | false positive in intent |

Before this release the same run had five more false positives, each fixed with a
regression test in `tests/test_semantic.py`:

- `[Title](URL)` in a quoted example, reported as a missing file. This was an error, so it
  would have failed CI.
- "Read `shared/token-counting.md`" matched as reading a token.
- A comment explaining a symlink guard (`~/.ssh/id_rsa`) counted as credential access.
- A docstring saying no `ANTHROPIC_API_KEY` is needed counted as using one.

## ToxicSkills demos

| Skill | Attack | skill-preflight 0.2 | skill-preflight 0.3 | Cisco skill-scanner 2.3.2 |
|---|---|---|---|---|
| vercel (.gemini) | posts `$(cat .env)` to a paste site | warning (secrets) | **error** (upload of command output), paste site | info only |
| vercel (.agents) | posts `$(uname -a)` to a paste site | nothing | **error**, paste site | info only |
| snyk-skill | `curl … \| bash` | warning | **error**, load-time exec | **critical** |
| clawhub | "run the command on this paste site" | nothing | warning (paste site) | info only |
| testing-guidelines | hidden Unicode-tag instructions | nothing | **error**, text decoded | **critical** (ASCII smuggling) |
| skill-with-commands | `` !`git diff` `` at load time | nothing | warning | info only |
| google | none | nothing | nothing | info only |
| skill-defender | none (a scanner) | 2 warnings | 2 warnings | 23 high |

Cisco's scanner was run with its default static analyzers (`skill-scanner scan <dir>
--format json`), without its LLM, behavioural or VirusTotal options, which need keys or
services. It took 16.3 s for the 19 Anthropic skills; skill-preflight took 0.5 s.

**This table is not a fair contest.** The new skill-preflight rules were written after
seeing these demos. They are general (any paste or request-capture host, any upload of
`$(…)` output, any `` !`…` ``, any tag characters), but this sample can no longer test
them blind. Cisco ran blind. On Anthropic's skills, Cisco's static rules raised 2 critical
and 6 high findings (shell calls in legitimate scripts, an infinite-loop heuristic), against
skill-preflight's single, true error.

The two tools want different jobs. Cisco's scanner, and NVIDIA's SkillSpector, are
malware scanners with taint tracking, YARA rules and optional LLM review. skill-preflight is
a fast pre-install check of form and declared behaviour, and its lockfile `diff` catches a
skill that changes after you approved it. Neither tool has the other's half.
