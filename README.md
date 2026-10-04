# shotmemo

Takes a region screenshot on macOS and writes what was open at the time
(a browser URL, the file open in Preview, and so on) into the screenshot's comments.

## What it writes

The first line is a heading and the second line is the URL or path. The same text goes into both the Finder comment and the EXIF UserComment (on one line in EXIF).

| Front app | Comment |
|---|---|
| Safari / Chrome family (on an NDL Digital Collections page) | `bibliographic info pNNN` + URL (via `ndl_tools.biblio` in ndl-tools) |
| Safari / Chrome family (other pages) | page title + URL |
| Preview (`biblio.txt` in the book folder) | `bibliographic info p<file name>` + path |
| Other apps with a document open (including Preview) | file name + path |
| Anything else | `app name: window title` |

- If ndl-tools (`$NDL_TOOLS_DIR`, default `~/Documents/github/ndl-tools`) can't be loaded, NDL pages get only the title + URL.
- Reading Preview's document and other apps' window titles needs Accessibility permission (granted to Karabiner).

## Save location

`~/Pictures/ScreenShot/<year>/`, file names like the standard ones (`ScreenShot 2026-10-04 9.05.03.png`).
Before every shot it checks `com.apple.screencapture location` and resets it to the current year if it differs,
so the standard Cmd+Shift+3/5 also save to the current year's folder. launchd switches it over on January 1 as well.

## Setup

- Karabiner: add the rule in `karabiner-rule.json` (Cmd+Shift+4 in every app) to `~/.config/karabiner/karabiner.json`
- launchd: copy `launchd/com.user.shotmemo-location.plist` to `~/Library/LaunchAgents/` and
  `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.shotmemo-location.plist`
- Log: `/tmp/shotmemo.log`
- Python: `~/.pyenv/versions/3.10.9/bin/python3` (standard library only, plus exiftool)

## Notes

- Finder's comment field reads `.DS_Store`, so writing only the xattr doesn't show up in Finder. Write through Finder (AppleScript).
  For the same reason, a file moved with `mv` loses its visible comment. `tools/move_by_year.py` rewrites the comment after moving.
- exiftool rewrites with `-overwrite_original_in_place` (plain `-overwrite_original` drops the xattrs).
- `tools/move_by_year.py SRC_DIR [--apply]` moves files into folders by the year in their file name (lists only, unless `--apply`).
