#!/usr/bin/env python3
"""~/Pictures/ScreenShot/<年>/ に、ファイル名の撮影年と違う年のファイルが混ざっているのを振り分ける。

    move_by_year.py SRC_DIR            # 何をどこへ移すかの一覧と件数だけ表示（既定）
    move_by_year.py SRC_DIR --apply    # 実際に移す

撮影年はファイル名（ScreenShot 2024-… / 2024_…）から読む。名前に年が無いもの、
SRC_DIR の年と同じものは動かさない。移した先に同名があれば止める。
Finder のコメント欄は .DS_Store を見るので、mv するとコメントが見えなくなる。
移したあと xattr に残っているコメントを Finder 経由で書き直す。
"""

import argparse
import plistlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

NAME_YEAR = re.compile(r"^(?:ScreenShot )?(20\d\d)[-_]")
COMMENT_XATTR = "com.apple.metadata:kMDItemFinderComment"


def xattr_comment(path: Path) -> str:
    r = subprocess.run(["xattr", "-px", COMMENT_XATTR, str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        return ""
    value = plistlib.loads(bytes.fromhex("".join(r.stdout.split())))
    return value if isinstance(value, str) else ""


def set_finder_comment(path: Path, comment: str):
    def q(s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    subprocess.run(
        ["osascript", "-e",
         f'tell application "Finder" to set comment of (POSIX file {q(str(path))} as alias) to {q(comment)}'],
        check=True, capture_output=True,
    )


def plan(src: Path) -> list[tuple[Path, Path]]:
    moves = []
    for p in sorted(src.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        m = NAME_YEAR.match(p.name)
        if not m or m.group(1) == src.name:
            continue
        moves.append((p, src.parent / m.group(1) / p.name))
    return moves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    src = args.src.expanduser().resolve()

    moves = plan(src)
    clash = [d for _, d in moves if d.exists()]
    for year, n in sorted(Counter(d.parent.name for _, d in moves).items()):
        print(f"{src.name}/ -> {year}/: {n}")
    print(f"計 {len(moves)} 件")
    if clash:
        print(f"移動先に同名あり（{len(clash)} 件）。中止:", *clash[:10], sep="\n  ")
        sys.exit(1)
    if not args.apply:
        for s, d in moves if len(moves) <= 10 else moves[:5] + moves[-5:]:
            print(f"  {s.name} -> {d.parent.name}/")
        print("（--apply で実行）")
        return

    recommented = 0
    for s, d in moves:
        comment = xattr_comment(s)
        d.parent.mkdir(exist_ok=True)
        s.rename(d)
        if comment:
            set_finder_comment(d, comment)
            recommented += 1
    print(f"移動 {len(moves)} 件、Finder コメント書き直し {recommented} 件")


if __name__ == "__main__":
    main()
