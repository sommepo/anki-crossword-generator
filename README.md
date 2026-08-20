# Anki Crossword Generator

Anki Crossword Generator creates printable, newspaper-style crosswords directly from your Anki collection. It supports two directions: Japanese reading answers with native-language word or sentence clues, and native-language word answers with Japanese word or sentence clues.

The add-on is built around printing, with a one-page A4 PDF and matching answer key, while also allowing puzzles to be completed and checked inside Anki. Everything runs locally; no card data is sent to an external service.

## At a glance

Choose a deck, choose a direction, select answer and clue fields, preview the eligible cards, then generate a puzzle. Solve it in Anki, or open PDF preview to print or export it.

<!-- SCREENSHOT 1: Main configuration window. Show the deck selector, the two direction panels, preview, and output selector. -->

## Installing

Install Anki Crossword Generator from [AnkiWeb](https://ankiweb.net/shared/info/ADDON_ID), or download the latest `.ankiaddon` file from this repository’s GitHub Releases page and open it with Anki.

Restart Anki, then open Tools → Anki Crossword Generator.

`ADDON_ID` will be replaced with the add-on’s AnkiWeb number before release.

## Getting started

Open Tools → Anki Crossword Generator, choose a deck, and set up either the Native → Japanese or Japanese → Native fields. The two sections remember their own answer field, clue field, clue template, and clue settings, so switching between them does not require reconfiguring everything.

Preview Native → Japanese or Preview Japanese → Native to see the eligible cards before generating a puzzle. Choose whether to open the puzzle inside Anki or as a printable PDF preview, then generate the crossword.

## Native → Japanese

Use Native → Japanese when the answer should be Japanese, usually a reading field, and the clue is in your native language.

A typical setup uses `Reading` as the answer field and an English meaning or sentence as the clue. Japanese answers are placed one written character per square, so small kana and long-vowel marks remain separate cells: `きょう` becomes `き / ょ / う`, and `スーパー` becomes `ス / ー / パ / ー`.

<!-- SCREENSHOT 2: Native → Japanese puzzle in Anki. Use a puzzle with English sentence clues and kana answers. -->

<!-- SCREENSHOT 3: The same Native → Japanese puzzle in PDF preview. -->

## Japanese → Native

Use Japanese → Native when the answer should be a native-language word and the clue is Japanese. A typical setup uses a field such as `englishWord` for answers and a Japanese word or sentence for clues.

Japanese → Native uses one alphabetic letter or digit per square. It suits languages with conventional letter-based crossword answers, including English, Spanish, French, and German. Spaces and punctuation are removed from the grid, so `mother-in-law` becomes `MOTHERINLAW`.

Use Maximum answer words to limit answers to one, two, or three words. Select `1 word` for a conventional single-word crossword; choose `None` to allow phrases.

<!-- SCREENSHOT 4: Japanese → Native puzzle in Anki. Use Japanese clues and English word answers. -->

<!-- SCREENSHOT 5: The same Japanese → Native puzzle in PDF preview. -->

## Choosing cards

Choose a deck, then use Extra search to narrow the source cards further. It accepts Anki’s normal search syntax, so you can use filters such as `tag::N2`, `is:due`, or `prop:ivl>30` (cards with a current review interval longer than 30 days). See Anki’s [search and filter documentation](https://docs.ankiweb.net/searching.html) for the full syntax.

Choose which card states to include, then select cards at random, in listed order, with due cards preferred, or from notes currently selected in Browse. Answers and clues are checked before selection, so blank or unsuitable cards are skipped and eligible cards are chosen instead.

## Clues and formatting

Choose a clue field or combine several fields with the clue template builder. For example, `{{Meaning}}` uses one field, while `{{Meaning}}` followed by `{{English sentence}}` combines a definition with an example sentence.

Fill-in-the-gap clues replace a matching answer in a sentence with a blank. Formatting from the original Anki field is retained, including bold and highlighted words. In Anki, choose how marked words appear; PDF clues use bold and underlining.

<!-- SCREENSHOT 6: Clue formatting and fill-in-the-gap example. Show bold or highlighted text in the clue list. -->

## Preview and generating

Preview Native → Japanese or Preview Japanese → Native to see the cards eligible for that crossword before generating it. The preview shows the answer, number of cells, and clue; double-click a row or use Open in Browse to inspect its source note.

Choose Within Anki to solve the puzzle in the add-on, or PDF preview to see the printable A4 version before saving it.

## Solving in Anki

Click a cell or clue, then type the answer. Space switches between Across and Down, Tab moves to the next clue, and Backspace deletes entered letters.

Check marks correct and incorrect cells. Show answers reveals the completed grid without clearing your entries, while Clear removes your entries and leaves the puzzle intact. Each clue includes a Browse button for opening its source card.

## Printing and exports

Choose PDF preview before generating to inspect the printable puzzle before saving it. The puzzle is laid out as a one-page landscape A4 crossword, with a matching answer key using the same grid and clue numbering.

Save the current puzzle or answer key as PDF, PNG, or SVG. Print opens the normal system print dialog for the current preview.

<!-- SCREENSHOT 7: PDF preview controls. Show Puzzle / Answer key, Save PDF, Save PNG, Save SVG, and Print. -->

## Completed puzzles

After finishing a puzzle, choose Mark puzzle solved. The add-on tags every note used in the completed grid with a dated tag such as `anki_crossword::solved::2026-08-20`.

Solved notes are excluded from future puzzles by default. Enable Solved crosswords when you want to include them again, or remove the dated tag in Browse to make an individual note eligible.

## Puzzle history

Every generated puzzle is saved as a self-contained snapshot in the current Anki profile. Open History from the main window to reopen an earlier puzzle in Anki or PDF preview, or remove it from the list.

History keeps the latest 100 puzzles. Saved puzzles do not change when their source cards are later edited.

<!-- SCREENSHOT 8: Puzzle history window with several saved puzzles. -->

## Known issues and limitations

Not every selected word will necessarily appear in a generated puzzle. The generator favours a connected, readable grid over forcing a weaker layout.

On some systems, Anki’s Browse window may open behind other add-on windows. It remains available through the taskbar or window switcher.

Japanese → Native is intended for alphabetic, letter-per-cell crossword answers. It is not suitable for Chinese, Korean, Arabic, or other scripts that need different cell rules.

## Development

To contribute or test changes locally, clone this repository and install the add-on in Anki’s add-ons folder. The test suite does not require Anki to be open.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python scripts/package_addon.py
```

See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) before publishing a release.

## License

Anki Crossword Generator is released under the [GNU General Public License v3.0](LICENSE).
