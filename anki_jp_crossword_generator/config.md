# Anki Crossword Generator

Phase 5: search your collection, keep separate Japanese and Native crossword fields, preview normalised cells, generate a connected grid, solve it interactively, and export a printable A4 puzzle and answer key.

## Selection

- **Deck** — dropdown of decks in the profile. Starts blank; nothing is assumed.
- **Extra search** — optional Anki search (`tag::N2`, `prop:ivl>30`, …).
- **Native → Japanese / Japanese → Native** — each has its own answer field, clue field, and clue template builder. Japanese → Native also has **Maximum answer words** (None, 1, 2, or 3), which can keep multi-word phrases out of the grid. Field lists come from note types in the selected deck.
- **Clue template builder** — assemble the clue with `{{Field}}` placeholders, or use **Insert field…** to pick them. Example: `{{Meaning}}` or `{{Expression}} — {{Meaning}}`. Blank uses the Clue field alone.
- **Marked words** — how bold or highlighted words from the card appear on clues: highlight, highlight and bold, bold only, or underline.
- **Highlight** — background behind marked words: black, gold, green, pink, blue, or match the window. Default is black.
- **Text colour** — colour of the marked word itself: red, white, black, gold, or auto (from the highlight). Default is red on black, matching a typical Anki highlighter.
- **Card states** — Due now, Learning, Review, New/unreviewed, Suspended, and Solved crosswords.

New/unreviewed and suspended cards are excluded unless you tick them. Blank clue and answer fields — including HTML-only values such as `<br>` — are skipped while scanning. The scan cap applies to eligible notes, not the first matching IDs.

## Completed puzzles

**Mark puzzle solved** tags every source note in the placed grid as `anki_crossword::solved::YYYY-MM-DD`. The ISO date keeps tags sortable and makes a particular completed puzzle easy to find in Browse. Solved notes are excluded by default; tick **Solved crosswords** to include them. Removing that dated tag in Browse makes the note eligible again.

- **Pick** — Random, listed order, prefer due, or notes selected in Browse.
- **Words** — unique answers to keep (default 20).
- **Minimum cells** — crossword suitability in cells, for every language (default 3).

Preview lists valid words only. Tick **Show skipped notes** to see excluded rows and a status column. Double-click a preview row, right-click, or use **Open in Browse** to show that note in the Browser. Generated puzzles keep a **Browse** button on each clue for the same jump.

## Generation

- **candidate_count** — layouts to try (default 250). Quality `fast` / `medium` caps this at 50 / 100.
- **grid_size** — `auto`, or an N×N bound such as `15x15`.
- The engine may omit words rather than produce a disconnected or bloated grid.

## Solving

- Click a cell or clue and type. **Space** switches Across/Down. **Tab** moves to the next clue. **Backspace** deletes.
- **Check** colours correct cells green and incorrect cells red.
- **Show answers** reveals the solution without wiping guesses. **Clear** erases guesses only.

Settings are stored with Anki’s add-on configuration.
