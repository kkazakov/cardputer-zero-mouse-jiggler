# Usage

## First pairing

1. Open **Mouse Jiggler** from APPLaunch.
2. The home screen starts with **Pair** centred when no host has ever connected
   (`OFFLINE` badge).
3. Press `OK`. The pairing page appears: `CardputerZero Mouse`, a countdown and
   `ESC Cancel`. The adapter is discoverable and pairable for 180 seconds.
4. On the computer: *Bluetooth settings → Add device* and pick
   **CardputerZero Mouse**. No PIN is required (SSP "Just Works"); the agent
   auto-accepts.
5. When the link comes up the page switches to the home screen with a
   `CONNECTED` badge, and **Start** is centred.

BlueZ stores the link key, so the host reconnects on its own later. The
CardputerZero side keeps the HID profile and both L2CAP channels open for the
lifetime of the app.

## Controls

| Input | Action |
| --- | --- |
| `Z` / `←` | previous card |
| `C` / `→` | next card |
| `OK` / `Enter` | activate the centred card |
| `ESC` tap | **exit** from the main screen; cancel pairing / leave Rename or the re-pair page |

The carousel order is **Pair → Start/Stop → Mode → Rename**; the centred card
is the one `OK` acts on. While the rename editor is open, `Z` and `C` type
letters instead of moving the carousel.

## Cards

### Pair

- `OFFLINE` → opens the pairing window.
- `CONNECTED` → asks `Re-pair?` with the current host name. `OK` forgets the
  bond, drops the link and opens a fresh pairing window; `ESC` cancels.

### Start / Stop

- `CONNECTED` → **Start**: begins the current mode, resets the counters.
- `RUNNING` → **Stop**: sends a zero report immediately and stops all motion.
  The Bluetooth link stays up.
- `OFFLINE` → **Start** opens the pairing window instead of failing silently.

The card subtitle shows the mode rate while stopped and
`HH:MM:SS · N reports` while running.

### Rename

Opens an editor prefilled with the current Bluetooth name:

- the first typed character **replaces** the old name (select-all behaviour);
  `Backspace` cancels that and edits normally;
- `OK` / `Enter` saves, `ESC` cancels;
- up to 20 characters: letters, digits, space, `-`, `_`, `.`;
- the name is written to `config.json`, applied to the adapter alias and the SDP
  record immediately, and used again after a reboot.

A host that is already connected may keep showing the previous name until it
reconnects (or is re-paired); new scans see the new name right away.

### Mode

Cycles Slow → Fast → Jiggle. The choice is saved to
`config.json` and survives restarts. Changing the mode while running applies on
the next tick.

## Modes

| # | Name | Movement | Report period | Speed |
| --- | --- | --- | --- | --- |
| 1 | Slow | 2 px horizontal, alternating sign | 30 s | 0.067 px/s |
| 2 | Fast | 5 px horizontal, alternating sign | 10 s | 0.5 px/s |
| 3 | Jiggle | 20–30 px random direction, exact inverse next tick | 100 ms | 200–300 px/s |

Why alternating: a HID mouse uses **relative** movement, so repeated
same-direction reports would walk the cursor across the desktop and eventually
into a screen corner. Alternating (Slow/Fast) and inverse hops (Jiggle) keep
the net displacement at 0 px (Jiggle bounded to ≤30 px), which is what an
anti-idle nudge needs.

Every delta is clamped to ±127, the range the HID descriptor advertises.

## States and badges

| Badge | Meaning | What you can do |
| --- | --- | --- |
| `OFFLINE` | no host link | Pair, or Start (opens pairing) |
| `PAIRING 2:41` | discoverable window, countdown | `ESC` cancels |
| `CONNECTED` | host linked, idle | Start, Mode, Pair (re-pair) |
| `RUNNING` | reports being sent | Stop, Mode |
| `BT ERROR` | setup failed, reason on screen | `OK` retries, `ESC` exits |
| `RENAME` | name editor open | type, `Backspace`, `OK` save, `ESC` cancel |

Link loss at any point stops motion immediately and returns to `OFFLINE`.

## Stop semantics

- Stop sends `A1 02 00 00 00 00` — buttons released, no movement — before the
  timer is cancelled.
- Exit does the same if the app is running.
- A killed process cannot send the zero report, but the last report always had
  buttons released, so nothing sticks on the host.

## Screen, battery, sleep

- The OS blanks the screen after the configured `Settings → Screen → DarkTime`
  (30 s by default). The app keeps running; the first key wakes the screen and
  is consumed by the wake, exactly like Ultimate-Remote.
- Stop leaves the Bluetooth link connected (idle, low traffic). If you want to
  save power, exit the app or turn Bluetooth off in Settings.
- Jiggle is 10 reports/s, a negligible CPU load on the CM0; the radio dominates
  the power draw in every mode.

## Multiple hosts

One host at a time. Pairing a second computer while connected requires
`Pair → OK` (forget), then pairing the new host. The old bond is removed.

## Using it responsibly

The app exists to keep a machine you control awake (long builds, dashboards,
reading). Defeating idle/lock policy on a managed computer may violate its
acceptable-use rules. There is no stealth mode and none is planned.
