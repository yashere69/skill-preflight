# skill-preflight

Pre-install checks for [Agent Skills](https://agentskills.io/specification): spec
conformance, how much context the skill costs, what its scripts can touch, and a lockfile
that shows exactly what changed when the skill updates.

![skill-preflight checking a skill with a pipe-to-shell instruction, then flagging a one-sentence description change after an update](docs/demo.png)

```bash
pip install git+https://github.com/yashere69/skill-preflight
skill-preflight check path/to/skills
skill-preflight lock path/to/skills && skill-preflight diff path/to/skills
```

## What this is, and what it isn't

Skills are folders of instructions and scripts that an agent loads and follows. Installing
one is closer to adding a dependency than to reading a document. Snyk's ToxicSkills study
(February 2026) scanned 3,984 public skills and found critical issues in 13.4% of them,
with 76 confirmed malicious payloads. The same team later showed that several "skill
scanners" built on keyword lists miss obvious exfiltration, and that one of them was itself
malware.

So this tool does **not** try to decide whether a skill is malicious. Pattern matching
can't do that. `c${u}rl` gets past every regex here (there's a test documenting exactly
that). If you need that verdict, look at tools that combine rules with model-based review:
Snyk's agent-scan, Cisco's [skill-scanner](https://github.com/cisco-ai-defense/skill-scanner)
or NVIDIA's SkillSpector. Then still read the code.

What it does do is the boring, reliable part that a reviewer needs before reading:

| Check | Why |
|---|---|
| **Spec conformance**: name format and directory match, description 1–1024 chars, compatibility ≤500, metadata string→string, allowed-tools as a string, no unknown fields | A non-conformant skill may load differently, or not at all, across agents |
| **Context budget**: tokens of name+description (loaded every session), body vs the spec's ~5,000 guidance, SKILL.md lines vs 500, missing or deeply nested references | Every installed skill taxes every conversation |
| **Capability manifest**: network, shell, env, credential paths and home-directory writes in the skill's scripts, with file and line, compared with `allowed-tools`. Python is read with `ast`, so imports and calls count but comments and docstrings don't. Other languages are matched after their comments are stripped | Tells you where to look first |
| **Instruction flags**: pipe-to-shell, uploading a command's output (`curl --data "$(cat .env)"`), request-capture and paste hosts, `` !`cmd` `` that runs when the skill loads, "ignore previous instructions", hide-from-user, send-to-URL, read-secrets, long base64 | The risky line in a skill is often plain English |
| **Hidden text**: invisible Unicode tag characters (an error, decoded so you can read them), bidirectional overrides, runs of zero-width characters. ZWJ and ZWNJ are allowed, because Devanagari and emoji need them | What a reviewer can't see, the model still reads |
| **Symlinks**: any link leaving the skill directory is an error, and links are never followed | A `references/notes.md` that points at `~/.ssh/id_rsa` gets read by whatever loads the skill |
| **Lock and diff**: hashes, description, allowed-tools, capabilities, URLs and link targets per skill | A trusted skill can change on update |

Every run ends with "No findings does not mean safe."

## The lockfile

`skill-preflight lock` writes `skills.lock` with, per skill: the description, allowed-tools,
a SHA-256 of every file, the capability set, and every URL in SKILL.md. Commit it next to
your skills. `skill-preflight diff` then ranks what changed:

- **high**: description gains a URL or an alert word ("every task", "silently", "install",
  ".env", ...), allowed-tools changes, a new capability, a new URL, a new script
- **medium**: description largely rewritten, a script modified, a non-script file added
- **low**: small description edit, docs changed, file removed

`diff` exits 1 on any high change, so it works as a CI gate on a skills repo.

## In CI

`--format json` is for scripts. `--format sarif` writes SARIF 2.1.0 (it validates against
the OASIS schema), so findings show up as annotations on the pull request and in the
repository's Security tab:

```yaml
- uses: yashere69/skill-preflight@v0.3.0
  with:
    path: skills
    sarif: skill-preflight.sarif
- uses: github/codeql-action/upload-sarif@v3
  if: always()
  with:
    sarif_file: skill-preflight.sarif
```

The description gets special treatment because it's loaded for every session and decides
when the skill runs. Rewriting "Use when the user shares a CSV" as "Use for every task,
before anything else" changes no code and doesn't touch a script, yet it makes the skill run
first on everything. Recent research describes this class of semantic supply-chain attack;
the example in the screenshot above is the simplest version.

[results/description-edits.md](results/description-edits.md) scores the alerts against 20
hand-written edits (`python tools/eval_diff.py`): 9 of 9 risky edits rated high, 0 of 11
benign edits rated high. I wrote both the edits and the alert words, so this is a
regression test, not evidence the word list generalises. Its first run did catch a real bug:
"Read the .env file" slipped past a word boundary that can't match before a dot.

## Tested on real skills

[results/real-skills.md](results/real-skills.md) has the full runs. Its two sources are
Anthropic's public skills repository (19 skills, assumed benign) and the 8 demo skills from
Snyk's ToxicSkills research (6 with an attack):

- **Anthropic's skills.** One error, and it's true: `claude-api`'s description is 1,068
  characters, over the spec's 1,024. Of 13 warnings, 3 are false positives in intent: lines
  describing how the SDK reads an API key get flagged as "read secrets". The previous
  release produced five more false positives on this set, including an error that would
  have failed CI. Each now has a regression test.
- **ToxicSkills demos.** 0.2 flagged 2 of the 6 attacks. 0.3 flags all 6, four as errors:
  posting `$(cat .env)` to a paste site, `curl | bash`, and hidden tag-character
  instructions. The new rules were written after seeing these demos, so this sample no
  longer tests them blind.
- **Cisco's skill-scanner** in its default static mode ran blind on the same demos and
  marked 2 of the 6 attacks high or critical. On Anthropic's skills it raised 8 high or
  critical findings, and it took 16 s where skill-preflight took 0.5 s. With its LLM
  analyzer it would likely catch more; that needs an API key and wasn't run.

The tools complement each other. Use a malware scanner for the verdict and skill-preflight
for conformance, context cost, the manifest, and the lockfile `diff` that notices when an
approved skill changes.

## Quoted examples aren't warnings

A skill that teaches prompt-injection review has to quote injections. Matches inside code
fences or `>` quotes are reported as `info`, not `warning`
(`examples/skills/injection-review` shows this). Without that, the most defensive skills
would look the most dangerous, which is the false-alarm pattern that makes people stop
reading scanner output.

## Layout

```
src/skill_preflight/
  model.py          load SKILL.md + files, split frontmatter
  conformance.py    spec rules
  budget.py         token estimates, reference checks
  capabilities.py   what scripts touch, vs allowed-tools
  instructions.py   prose red flags, quoted-example handling
  lock.py           lockfile, ranked diff
  cli.py            check / lock / diff
examples/skills/    four skills: clean, risky, defensive, non-conformant
eval/               labelled description edits
```

## Limits

- Token counts are `characters / 4`. That's fine for English markdown, but Hindi or code
  runs higher, so read them as a floor.
- Capability detection reads Python's syntax tree and pattern-matches everything else.
  Code that builds names at run time (`getattr(os, "sys" + "tem")`) or is obfuscated isn't
  covered, and nothing here follows data from a source to a sink.
- Instruction rules work on lines. They can't tell "read the API key" from "the SDK reads
  the API key", which is where the remaining false positives come from.
- `allowed-tools` matching knows the common tool names (`Bash`, `WebFetch`). Other agents'
  tool names show up as undeclared.
- Remote installs (`npx skills add owner/repo`) aren't fetched. Clone or install first,
  then point this at the folder.

Stable: the check/lock/diff commands, the lockfile format and the JSON and SARIF output.
Experimental: the individual instruction rules and their severities, which will keep
moving as they meet more real skills.

MIT licensed.
