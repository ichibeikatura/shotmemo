# shotmemo

macOS で範囲指定のスクリーンショットを撮り、そのとき開いていたもの
（ブラウザの URL、プレビューで開いているファイルなど）をコメントに書き込む。

## 書き込む内容

1行目が見出し、2行目が URL かパス。Finder コメントと EXIF UserComment の両方に同じ内容を書く（EXIF は1行にまとめる）。

| 前面のアプリ | コメント |
|---|---|
| Safari / Chrome 系（NDLデジコレのページ） | `書誌情報 pNNN` + URL（ndl-tools の `ndl_tools.biblio` を使う） |
| Safari / Chrome 系（ほかのページ） | ページタイトル + URL |
| プレビュー（本のフォルダに `biblio.txt` がある） | `書誌情報 p<ファイル名>` + パス |
| 書類を開いているほかのアプリ（プレビューを含む） | ファイル名 + パス |
| 上記以外 | `アプリ名: ウィンドウ名` |

- ndl-tools（`$NDL_TOOLS_DIR`、既定は `~/Documents/github/ndl-tools`）を読み込めないときは、NDL のページもタイトル + URL だけになる。
- プレビューの書類やほかのアプリのウィンドウ名を読むにはアクセシビリティ権限が要る（Karabiner に付与済み）。

## 保存先

`~/Pictures/ScreenShot/<西暦>/`。ファイル名は標準と同じ形式（`ScreenShot 2026-10-04 9.05.03.png`）。
撮影のたびに `com.apple.screencapture location` を確かめ、今年と違えば書き換える。
これで標準の Cmd+Shift+3/5 も今年のフォルダに入る。1月1日には launchd でも切り替える。

## セットアップ

- Karabiner: `karabiner-rule.json` のルール（全アプリで Cmd+Shift+4）を `~/.config/karabiner/karabiner.json` に足す
- launchd: `launchd/com.user.shotmemo-location.plist` を `~/Library/LaunchAgents/` にコピーし、
  `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.shotmemo-location.plist`
- ログ: `/tmp/shotmemo.log`
- Python: `~/.pyenv/versions/3.10.9/bin/python3`（標準ライブラリのみ。ほかに exiftool を使う）

## 注意

- Finder のコメント欄は `.DS_Store` を読むので、xattr に書くだけでは Finder に出ない。Finder（AppleScript）経由で書く。
  同じ理由で、`mv` で移したファイルは Finder 上のコメントが見えなくなる。`tools/move_by_year.py` は移動後にコメントを書き直す。
- exiftool は `-overwrite_original_in_place` で書き換える（`-overwrite_original` だと xattr が消える）。
- `tools/move_by_year.py SRC_DIR [--apply]` はファイル名の年でフォルダに振り分ける（`--apply` なしなら一覧を出すだけ）。
