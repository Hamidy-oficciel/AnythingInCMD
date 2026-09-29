# BrowserCMD Plan

## Product

BrowserCMD is a Windows-first browser controlled by the system Edge or Chrome and displayed in a CMD-compatible terminal. Python owns browser automation and browser state; a C++17 renderer owns the terminal. Windows Terminal is the primary target, conhost is secondary, and POSIX systems are compile-and-unit-test targets only.

The project is being delivered milestone by milestone. This file records intended work separately from verified behavior; completed claims are updated only after the corresponding checks run.

## Milestones

### M0: Reconnaissance and scaffold

- Record architecture, wire protocol, and implementation decisions.
- Add self-contained launcher, Python package/test layout, native build script, and CI.
- Build and run the native hello self-test on supported CI platforms.
- Acceptance: native build and Python test runner work.

### M1: Browser spike

- Launch installed Edge/Chrome headless with an ephemeral loopback CDP port and temporary profile.
- Navigate, capture JPEG screencast frames, acknowledge frames, and collect bounded DOM text runs.
- Save a diagnostic image and JSON snapshot for static, Wikipedia, and JavaScript-heavy fixtures where the environment permits.
- Record measured capture rate and limitations.

### M2: Renderer core

- Add exception-safe terminal setup/restore, VT keyboard and mouse input, half-block rendering, cell diffing, self-test, and recorded-frame replay.
- Acceptance: renderer restores terminal state on normal and interrupted exits; native checks pass.

### M3: Hybrid pipeline

- Implement bounded IPC, image and text layers, resize/debounce behavior, and eased scroll feedback.
- Acceptance: local article text is readable and matches extracted content; resize does not crash.

### M4: Chrome UI and navigation

- Add tabs, address bar, start page, navigation controls, progress, status, themes, and styled navigation errors.
- Acceptance: navigation and the applicable documented keybindings work against local fixtures.

### M5: Interaction

- Add mouse input, link hints, editable forms, find, zoom, and multi-tab handling.
- Acceptance: search and form flows work; Unicode input is covered by tests/manual checks.

### M6: Modes and extras

- Add TEXT, PIXEL, and READER modes, bookmarks, history, palette, help, config UI, bidi handling, and tracker blocking.
- Acceptance: modes switch without navigation and extras work against fixtures.

### M7: Hardening

- Cover security boundaries, malformed IPC, terminal-string sanitization, process cleanup, resource limits, performance budgets, and soak behavior.
- Acceptance: each security requirement has a test or a clearly labeled manual check; measurements are recorded or marked NOT VERIFIED with reason.

### M8: Polish and documentation

- Update the user README, Windows build guide, changelog, and manual checklist to describe only behavior that was actually run.
- Acceptance: clean-clone setup instructions match verified behavior; Windows CI is green.

## Verification policy

A milestone is not complete until its build and relevant tests pass and its docs reflect the observed state. Windows-specific behavior is NOT VERIFIED until run on Windows. Public internet checks are diagnostic, not CI requirements; deterministic integration tests use a local HTTP server.

## Current status

M0 is complete for the POSIX build-and-unit-test target. M1's implementation is
in progress: URL policy, browser discovery/lifecycle, runtime CDP schema checks,
bounded screencast and DOM snapshot capture, and diagnostic file output are
implemented. The full Python suite reports 41 passing tests on Ubuntu with
Python 3.14.2. No supported browser is installed in this workspace, so real
CDP operation, screenshots, Wikipedia/JavaScript-heavy captures, and measured
frame rate are NOT VERIFIED; M1 acceptance is not yet met. Windows behavior
also remains NOT VERIFIED.
