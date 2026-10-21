#!/usr/bin/env python3
"""範囲指定スクリーンショットを撮り、撮影時に開いていたものの情報をコメントに書く。

    shotmemo.py                    # 撮影（Karabiner の Cmd+Shift+4 から呼ぶ）
    shotmemo.py --dry-run          # 撮影せず、書き込むコメントだけ表示
    shotmemo.py --update-location  # 標準スクショの保存先を今年のフォルダにする（launchd 用）

コメントは Finder コメントと EXIF UserComment の両方に書く。
保存先は ~/Pictures/ScreenShot/<西暦>/。標準の Cmd+Shift+3/5 も同じフォルダに入るよう、
撮影のたびに com.apple.screencapture の location を今年に合わせる。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

SCREENSHOT_ROOT = Path.home() / "Pictures" / "ScreenShot"
NDL_TOOLS_DIR = Path(
    os.environ.get("NDL_TOOLS_DIR", str(Path.home() / "Documents" / "github" / "ndl-tools"))
).expanduser()

SAFARI_IDS = {"com.apple.Safari", "com.apple.SafariTechnologyPreview"}
CHROMIUM_IDS = {
    "com.google.Chrome",
    "com.brave.Browser",
    "com.microsoft.edgemac",
    "com.vivaldi.Vivaldi",
    "company.thebrowser.Browser",  # Arc
}
PREVIEW_ID = "com.apple.Preview"
# Karabiner の shell_command は PATH に /opt/homebrew/bin を含まない
EXIFTOOL = shutil.which("exiftool") or "/opt/homebrew/bin/exiftool"


def log(msg: str):
    print(f"shotmemo: {msg}", file=sys.stderr)


def osascript(script: str) -> str:
    """AppleScript を実行して結果を返す。失敗時は空文字（理由は stderr に出す）。"""
    try:
        r = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10
        )
    except subprocess.TimeoutExpired:
        log("osascript timed out")
        return ""
    if r.returncode != 0:
        log(f"osascript: {r.stderr.strip()}")
        return ""
    out = r.stdout.strip()
    return "" if out == "missing value" else out


def as_str(s: str) -> str:
    """AppleScript の文字列リテラルにする。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# === 保存先 ===
def year_dir(now: datetime) -> Path:
    return SCREENSHOT_ROOT / str(now.year)


def update_location(now: datetime):
    """標準スクショの保存先を今年のフォルダにする。変わったときだけ書き換える。"""
    target = year_dir(now)
    target.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["defaults", "read", "com.apple.screencapture", "location"],
        capture_output=True, text=True,
    )
    current = Path(r.stdout.strip()).expanduser() if r.returncode == 0 else None
    if current == target:
        return
    subprocess.run(
        ["defaults", "write", "com.apple.screencapture", "location", str(target)], check=True
    )
    # 標準のショートカットに新しい保存先を読ませる
    subprocess.run(["killall", "SystemUIServer"], capture_output=True)
    log(f"location: {current} -> {target}")


def screenshot_path(now: datetime) -> Path:
    """標準と同じ名前（ScreenShot 2026-10-04 9.05.03.png）で、今年のフォルダに置く。"""
    r = subprocess.run(
        ["defaults", "read", "com.apple.screencapture", "name"], capture_output=True, text=True
    )
    prefix = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "ScreenShot"
    stem = f"{prefix} {now:%Y-%m-%d} {now.hour}.{now:%M.%S}"
    path = year_dir(now) / f"{stem}.png"
    n = 1
    while path.exists():
        path = year_dir(now) / f"{stem} ({n}).png"
        n += 1
    return path


# === 開いているものの情報 ===
def frontmost_app() -> tuple[str, str]:
    """(bundle id, 表示名)。lsappinfo はアクセシビリティ許可なしで使える。"""
    asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(
        ["lsappinfo", "info", "-only", "bundleid", "-only", "name", asn],
        capture_output=True, text=True,
    )
    bundle = re.search(r'"CFBundleIdentifier"="([^"]*)"', r.stdout)
    name = re.search(r'"LSDisplayName"="([^"]*)"', r.stdout)
    return (bundle.group(1) if bundle else "", name.group(1) if name else "")


def browser_tab(bundle: str) -> tuple[str, str]:
    """(URL, タイトル)"""
    if bundle in SAFARI_IDS:
        tab = "current tab of front window"
        title = "name"
    else:
        tab = "active tab of front window"
        title = "title"
    out = osascript(
        f"tell application id {as_str(bundle)} to "
        f"return (URL of {tab}) & linefeed & ({title} of {tab})"
    )
    url, _, name = out.partition("\n")
    return url, name


def front_window(app_name: str) -> tuple[str, str]:
    """(開いているファイルのパス, ウィンドウ名)。System Events 経由なのでアクセシビリティ許可が要る。"""
    out = osascript(
        f"""
tell application "System Events" to tell process {as_str(app_name)}
    set w to front window
    set doc to ""
    try
        set doc to value of attribute "AXDocument" of w
    end try
    if doc is missing value then set doc to ""
    return doc & linefeed & (name of w)
end tell"""
    )
    doc, _, title = out.partition("\n")
    if doc.startswith("file://"):
        doc = unquote(doc[len("file://"):])
    return doc, title


def book_biblio(file_path: Path) -> str:
    """書籍フォルダ（…/書籍/original/001.jpg の「書籍」）の biblio.txt の1行目。"""
    for d in (file_path.parent, file_path.parent.parent):
        f = d / "biblio.txt"
        if f.is_file():
            try:
                return f.read_text(encoding="utf-8").splitlines()[0].strip()
            except (OSError, IndexError, UnicodeDecodeError):
                return ""
    return ""


def ndl_biblio(url: str) -> str:
    """NDLデジコレの URL なら「書誌情報 pNNN」を返す。ndl-tools が無ければ空文字。"""
    if "ndl.go.jp" not in url:
        return ""
    try:
        sys.path.insert(0, str(NDL_TOOLS_DIR))
        from ndl_tools.biblio import extract_pid_and_page, get_biblio_text
    except ImportError as e:
        log(f"ndl_tools を読めないので書誌情報なし: {e}")
        return ""
    pid, page = extract_pid_and_page(url)
    if not pid:
        return ""
    try:
        biblio = get_biblio_text(pid)
    except Exception as e:  # ネットワーク等。書誌なしで続行
        log(f"書誌情報の取得に失敗: {e}")
        return ""
    return f"{biblio} p{page.zfill(3)}" if biblio else ""


def gather_context() -> dict:
    """撮影前に取る（速い AppleScript だけ）。ネットワークを使う書誌取得は撮影後に回す。"""
    bundle, name = frontmost_app()
    ctx = {"bundle": bundle, "app": name, "url": "", "title": "", "path": ""}
    if bundle in SAFARI_IDS or bundle in CHROMIUM_IDS:
        ctx["url"], ctx["title"] = browser_tab(bundle)
    elif name:
        ctx["path"], ctx["title"] = front_window(name)
    return ctx


def build_comment(ctx: dict) -> str:
    """1行目に見出し（書誌・タイトル・ファイル名）、2行目に URL かパス。"""
    if ctx["url"]:
        title = ctx["title"]
        # PDF を直接開いたタブはタイトルが URL そのものになるので、ファイル名にする
        if not title or title == ctx["url"]:
            title = unquote(urlparse(ctx["url"]).path.rstrip("/").rpartition("/")[2])
        head = ndl_biblio(ctx["url"]) or title
        return "\n".join(s for s in (head, ctx["url"]) if s)
    if ctx["path"]:
        p = Path(ctx["path"])
        head = p.name
        if ctx["bundle"] == PREVIEW_ID:
            biblio = book_biblio(p)
            if biblio:
                head = f"{biblio} p{p.stem}"
        return f"{head}\n{p}"
    return ": ".join(s for s in (ctx["app"], ctx["title"]) if s)


# === 書き込み ===
def write_comment(path: Path, comment: str):
    # exiftool は in_place で書き換えるとファイルの xattr を残す。Finder コメントより先に書く
    try:
        r = subprocess.run(
            [EXIFTOOL, "-q", "-overwrite_original_in_place",
             f"-UserComment={comment.replace(chr(10), ' ')}", str(path)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log(f"exiftool: {r.stderr.strip()}")
    except OSError as e:  # exiftool が無くても Finder コメントは書く
        log(f"exiftool: {e}")
    # Finder のコメント欄は .DS_Store を見るので、xattr ではなく Finder 経由で書く
    osascript(
        f"tell application \"Finder\" to set comment of (POSIX file {as_str(str(path))} as alias)"
        f" to {as_str(comment)}"
    )


def main():
    ap = argparse.ArgumentParser(description="スクリーンショットに開いているものの情報をコメントで付ける")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="撮影せず、書き込むコメントだけ表示")
    g.add_argument("--update-location", action="store_true", help="標準スクショの保存先を今年のフォルダにする")
    args = ap.parse_args()

    now = datetime.now()
    if args.update_location:
        update_location(now)
        return

    ctx = gather_context()
    if args.dry_run:
        print(ctx)
        print(build_comment(ctx))
        return

    update_location(now)
    path = screenshot_path(now)
    subprocess.run(["screencapture", "-i", str(path)])
    if not path.exists():  # Esc でキャンセル
        return
    comment = build_comment(ctx)
    log(f"{path.name}: {comment!r}")
    if comment:
        write_comment(path, comment)


if __name__ == "__main__":
    main()
