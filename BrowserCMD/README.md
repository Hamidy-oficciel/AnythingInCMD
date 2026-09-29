# BrowserCMD

BrowserCMD is the browser-based companion concept to YouTubeCMD. It keeps the
same simple workflow: provide a YouTube link, choose a source quality, and
watch the video. Instead of drawing frames as terminal characters, BrowserCMD
shows the actual video in a browser player.

## Concept

- A lightweight local app opens a browser page for playback.
- The page accepts a YouTube URL and offers 360p, 480p, 720p, 1080p, or best
  available quality.
- Video is displayed at its real frame dimensions and adapts when the browser
  window changes size.
- One browser media timeline handles picture and sound together, with play,
  pause, seek, volume, and fullscreen controls.
- Clear status and error messages cover invalid URLs, unavailable formats, and
  missing playback dependencies.

## Proposed Architecture

- A small local Python service validates links and uses `yt-dlp` to inspect
  available streams.
- The browser provides the player UI and native video rendering.
- The local service supplies a browser-playable media stream. If the selected
  YouTube format separates audio and video, the service must mux or synchronize
  them before playback rather than treating them as unrelated players.
- The service listens on localhost and is started and stopped with the app.

## Relationship to YouTubeCMD

YouTubeCMD is the terminal-first player and remains its own project. BrowserCMD
is a separate browser-first direction for users who want full video pixels,
standard browser controls, and synchronized audio without terminal rendering.

This folder currently documents the concept; it does not yet contain a working
browser player.
