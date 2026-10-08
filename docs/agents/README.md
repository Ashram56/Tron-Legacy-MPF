# Master plan: from a Stern SAM ROM to an MPF game

**Read this first.** It says what you (the owner) provide, which agents turn it into a playable MPF game, in
what order, and where each agent's instructions live. It is game agnostic: Tron Legacy LE 1.74 is the worked
example throughout, and every agent file names the Tron result to copy from.

> **Have a Visual Pinball X table of the game? Run the [VPX extraction agent](vpx_extraction.md) early.**
> From the `.vpx` alone it gives MPF Monitor a real playfield picture with every switch, lamp and flasher
> placed on it (`monitor.yaml`), plus the table script the VPX bridge needs. Two commands, a few seconds:
> `python scripts/vpx_extract.py TABLE.vpx OUT` then `python scripts/vpx_map.py OUT --names <MPF config files>`.
> Without it, MPF Monitor only has a labelled grid. On Tron it placed 44 switches, 64 lamps and 8 flashers.

## 0. Getting started (once)

The agents are Markdown files in public repositories: there is nothing to install or copy. Claude reads them
when a repository is attached or when you point it at them.

1. **GitHub.** For Tron, the repositories exist: [Tron-Legacy-MPF](https://github.com/Ashram56/Tron-Legacy-MPF)
   (game, this plan) and [Tron-Legacy-LE-ROM-Decryption](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption)
   (ROM extraction). For another game, create two empty repositories of your own, one for the extraction and
   one for the game, plus a private one if third-party media will be involved. The agents' instructions stay
   in the Tron repositories and are read from there.
2. **Connect Claude to GitHub** at [claude.ai/connect-github](https://claude.ai/connect-github) and install the
   Claude GitHub App on your repositories when asked.
3. **Create a Claude project** (claude.ai, Projects) and add your repositories to it in the project settings.
   Put the large inputs in the project's files: the ROM zip(s) and the `.vpx` (section 1).
4. **Point the project at this plan.** Paste into the project's instructions:
   > Before any work, read docs/agents/README.md in Ashram56/Tron-Legacy-MPF (the master plan) and follow the
   > agent file that matches the task. Update that agent file whenever you learn something it should say.
   >
   > Project: `<game, ROM set, model>`. Extraction repo: `<owner/repo>`. Game repo: `<owner/repo>`.
5. **Start one thread per agent** with the message from section 4, in the order of section 3. Each agent
   names what it needs from you; answer in the thread.

Working in Claude Code on your own computer instead: clone the repositories and run `claude` in one of them.
Each repository's `CLAUDE.md` loads its agent automatically (`AGENTS.md` in the extraction repository, this
plan in the game repository), as it also does in a cloud session that has the repository attached.

## 1. What you provide

| Input | Needed for | Required? | How to hand it over |
|---|---|---|---|
| **The game ROM**, one per model (Pro, Premium, LE): the PinMAME set zip, e.g. `trn_174h.zip` (LE 1.74), `trn_17402.zip` (Pro 1.74) | Everything: rules, sounds, DMD, lamp shows, settings, coil timing | **Yes** | Upload it to the ROM extraction thread, or a download link. It is copyrighted: it is never committed to any repository. Say which version and model it is if you know. |
| **The VPX table** (`.vpx`) of the same game | MPF Monitor layout and playfield picture; playing the game in VPX with MPF instead of PinMAME | Recommended | Tables are 150-300 MB: put it in the project's files (Tron: `Tron Legacy (Stern 2011) VPW Mod v1.1.vpx`), give a download link, or let an agent work on your PC through Remote Control. Say which table it is (author, version) and which model it simulates. |
| Your target hardware | Which overlays to build: desktop only, VPX, a P-ROC on the original boards, other | Yes (one line) | Tron: P-ROC on the SAM boards, Pro by default, LE selectable; VPX on Windows. |
| GitHub repositories | Where the agents write | Yes | One for the ROM extraction (asset/spec repo), one for the game. Private work (third-party colourisation) goes in a separate private repo. Connect GitHub to Claude once. |
| A Windows PC with VPX | Testing the VPX bridge (VPX runs only on Windows) | For the bridge | Run the checks the bridge agent lists, or allow Remote Control on a folder. |
| Optional: operator manual, switch/lamp matrix | Cross-checking IO numbers | No | Upload the PDF. |
| Optional: schematics, logic analyzer captures | Hardware work (P-ROC, replacement boards) | No | Upload; say which ROM the machine ran when captured. |
| Optional: third-party media (videos, colourisation files) | Improvements only | No | Private repo only; never named or described in the public game repo. |
| Your decisions | Model, defaults, look and feel | As they come up | Agents pick sensible defaults, say which, and ask only for what they cannot decide. |

## 2. The agents

| # | Agent | Instructions | Input | Output |
|---|---|---|---|---|
| A | **ROM extraction** | [`AGENTS.md` in the ROM decryption repo](https://github.com/Ashram56/Tron-Legacy-LE-ROM-Decryption/blob/main/AGENTS.md) (summary: [rom_extraction.md](rom_extraction.md)) | ROM image(s) | The asset/spec repo: rules specs, reference traces, decompile, MPF package (config, sounds, DMD frames, shows), `rom_data/` tables |
| B | **VPX extraction** (MPF Monitor) | [vpx_extraction.md](vpx_extraction.md) | `.vpx` table (+ A's MPF config for names) | `playfield.png`, `monitor.yaml`, switch/lamp/flasher CSVs with numbers and positions, `script.vbs`, overlay to check by eye |
| C | **Strict recreation** | [recreation.md](recreation.md) | A's repo (as a submodule), B's layout | The game repo: the ROM's game exactly (rules, display, sound, lamps, service menu, settings, audits, credits, hardware overlays), checked against A's traces |
| D | **VPX bridge** (work in progress) | [vpx_bridge.md](vpx_bridge.md) | C's game, B's table script | VPX plays the ball, MPF replaces PinMAME and the ROM |
| E | **Improvements** (optional) | [improvement.md](improvement.md) | C's game | Switchable departures: HD DMD, clean fonts, colour, new modes; the ROM's behaviour stays one option away |

Reference docs the agents share (not agents themselves): [sam_to_mpf_playbook.md](../handover/sam_to_mpf_playbook.md)
(how C builds), [dmd_hd_upscaling.md](../handover/dmd_hd_upscaling.md) (how E's HD display works),
[rom_decomp_feedback.md](../handover/rom_decomp_feedback.md) (what C needed from A),
[rom_differences.md](../rom_differences.md) (every departure from the ROM), [vpx.md](../vpx.md) (VPX set-up for players).

## 3. Order

```
ROM ──► A ROM extraction ──► C strict recreation ──► E improvements (optional)
                                   ▲        │
.vpx ─► B VPX extraction ──────────┘        └──► D VPX bridge ◄── B's table script
```

1. **A and B in parallel.** They need nothing from each other; B only borrows A's MPF config for device names
   (without it B writes placeholder names that carry the numbers, which C renames).
2. **C** starts when A has delivered the IO tables, sounds and DMD frames; rules features follow A's specs
   and traces mode by mode. C feeds missing-data requests back to A (Tron: [rom_decomp_feedback.md](../handover/rom_decomp_feedback.md)).
3. **D** once C boots a game on virtual hardware. **E** any time after C's display works, always switchable.
4. Every new ROM version or model: A again (A's section 15 ports a second model), then C's asset sync.

## 4. Starting an agent

Start a thread and paste one line, filling in the brackets:

| Agent | Message |
|---|---|
| A | "Act as the ROM extraction agent: follow AGENTS.md in `<asset repo>` on the attached ROM `<set name>`." |
| B | "Act as the VPX extraction agent (docs/agents/vpx_extraction.md in `<game repo>`) on `<table.vpx>`; names from `<asset repo>`'s MPF config." |
| C | "Act as the strict recreation agent (docs/agents/recreation.md) for `<game>` from `<asset repo>`." |
| D | "Act as the VPX bridge agent (docs/agents/vpx_bridge.md); the table is `<table.vpx>`." |
| E | "Act as the improvement agent (docs/agents/improvement.md): `<what to improve>`." |

## 5. Rules every agent follows

- **Keep these docs current.** When a thread learns something that changes how a later agent would work (a
  method, a fact, a mistake and its fix, an owner decision), fold it into the agent file that owns it, in the
  same session: ROM facts in A's `AGENTS.md`, build facts in the playbook or recreation.md, VPX facts in
  vpx_extraction.md or vpx_bridge.md, look-and-feel in improvement.md. Update the "Last updated" line.
- **Strict first, improvements second.** C reproduces the ROM; anything that differs is E's, is switchable,
  and gets a row in [rom_differences.md](../rom_differences.md).
- **Label facts**: observed (emulator or machine), code (decompile/table, with the ROM address), inferred.
- **Machine-readable first**: tables (CSV/JSON) that code reads, prose second.
- **Never commit the ROM**, and never name or describe third-party colourisation or media work in a public
  repo beyond a pointer to the private repo.
- **Test locally before pushing.** CI on the game repo runs only on pushes to `main`; don't wait on it for a
  branch. Run `pytest -q tests` (and the trace and render checks for rules or display work).
- **Owner preferences (Tron):** go ahead without asking for approval; pick a default, say which, and list what
  needs the owner's judgement as a short numbered list. Small update zips of changed files only, never a full
  rebuild (A). Answer in the owner's language (Vincent sometimes writes in French).

Last updated 2026-10-08.
