# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — M0: Research & Planning (2026-09-03)

- `docs/RESEARCH.md` — structured research with citations covering:
  - the JARVIS/Iron Man HUD design language, sourced from primary interviews with its
    designers (Jayse Hansen, Kent Seki), Cantina Creative/Prologue coverage, and the
    sci-fi-interface critical literature, distilled into eight design principles (D1–D8);
  - a survey of six existing open-source JARVIS GUI projects, recording the patterns
    worth adopting, the credits owed, and the gap this project fills;
  - an evidence-based toolkit evaluation of Qt 6, Flutter, Tauri and GTK4/GSK,
    including the GTK 4.16 deprecation of `GskGLShader`;
  - PySide6 (LGPLv3) vs PyQt6 (GPLv3) licensing analysis;
  - a `VERIFIED-LOCAL` record of what was actually executed in this workspace,
    including a successful headless QML render.
- `docs/PLAN.md` — scope and requirements with acceptance criteria, architecture,
  tech-stack decision table, coding standards and quality gates, six milestones,
  risk register, changelog/experience workflow, folder structure, and a starter
  vertical-slice outline.
- `AGENT-EXPERIENCE.md` — development log for M0.

### Notes

- **No product code has been written.** Per the project guidelines, implementation is
  gated on stakeholder sign-off of the toolkit choice, the v1 scope boundary, and the
  backend language.

[Unreleased]: https://github.com/thecyberexpert123-stack/J.A.V.R.I.S.-GUI/commits/main
