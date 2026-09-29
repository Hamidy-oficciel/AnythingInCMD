# Engine/Renderer Protocol

This is the planned local IPC contract between the Python engine and native renderer. It is implemented and tested incrementally; this document does not imply that messages already work.

## Transport and framing

The renderer is a child process. Its stdin carries engine-to-renderer messages and its stdout carries renderer-to-engine messages. Each direction is a byte stream of frames with this 12-byte little-endian header:

| Offset | Size | Meaning |
|---|---:|---|
| 0 | 4 | ASCII magic `BCMD` |
| 4 | 2 | Protocol version, currently `1` |
| 6 | 2 | Message type |
| 8 | 4 | Payload length in bytes |

A receiver must read the complete header and payload, reject a wrong magic or unsupported version, and reject a length greater than 64 MiB before allocating payload storage. Unknown message types are rejected. A truncated header or payload is a protocol error. Strings are UTF-8. Integers in binary structures are unsigned little-endian. JSON payloads must be valid UTF-8 JSON objects, must not contain duplicate keys, and are subject to a 4 MiB limit. Implementations must impose narrower per-field and collection limits as applicable.

Message type numbers:

| Value | Name | Direction |
|---:|---|---|
| 1 | `HELLO` | Engine to renderer |
| 2 | `FRAME` | Engine to renderer |
| 3 | `TEXTLAYER` | Engine to renderer |
| 4 | `CHROME_STATE` | Engine to renderer |
| 5 | `TOAST` | Engine to renderer |
| 6 | `EVENT` | Renderer to engine |

## Payloads

`HELLO`: JSON object with `protocol` (must be 1), `columns`, `rows`, and `cell_width` / `cell_height` in CSS pixels. Dimensions must be positive and bounded. It is the first message from the engine.

`FRAME`: binary payload: `width:u32`, `height:u32`, `timestamp_ms:u64`, `jpeg_length:u32`, then exactly `jpeg_length` JPEG bytes. The total payload is at most 24 MiB; dimensions are each at most 8192 and the decoded image is at most 64 million pixels. The declared JPEG length must exactly match the remaining payload. Only the latest frame is retained; a pending older frame may be dropped.

`TEXTLAYER`: JSON object with `viewport` (`width`, `height`, `scroll_x`, `scroll_y`) and `runs`, an array of at most 20,000 entries. A run has `text`, CSS-pixel rectangle (`x`, `y`, `width`, `height`), foreground/background RGB colors, `bold`, `italic`, `underline`, and `link`. Text and numeric values are bounded and validated. Invalid or unsupported text runs are omitted in favor of the image layer.

`CHROME_STATE`: JSON object containing tabs, active tab id, sanitized URL and title, loading state/progress, zoom, mode, and theme. Tabs are limited to nine.

`TOAST`: JSON object with a sanitized message, severity (`info`, `success`, `warning`, `error`), and bounded display duration.

`EVENT`: JSON object with event kind (`key`, `mouse`, `resize`, or `command`) and kind-specific bounded fields. Page-derived strings are never accepted as terminal escape sequences.

## Failure behavior

Malformed, oversized, truncated, or unsupported messages terminate the protocol session with a diagnostic on stderr. Page data must be sanitized before terminal output. Neither side may silently continue after losing framing synchronization.
