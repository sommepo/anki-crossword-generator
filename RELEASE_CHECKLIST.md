# Release checklist

## Before release

- Update `ADDON_VERSION` in `anki_jp_crossword_generator/version.py`.
- Add a dated entry to `CHANGELOG.md`.
- Run `python -m pytest`.
- Run `python scripts/package_addon.py`.
- Install the resulting `.ankiaddon` in a clean Anki profile.
- Test Native → Japanese and Japanese → Native generation.
- Test interactive checking, clue selection, Browse, solved tags, and history.
- Test PDF preview, PDF, PNG, SVG, and Print with Japanese text.
- Confirm the README, screenshots, AnkiWeb link, and license are current.

## Publish

- Create a GitHub release and attach the `.ankiaddon` file.
- Publish the same package on AnkiWeb.
- Verify installation from both release locations.
