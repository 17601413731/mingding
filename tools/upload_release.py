# -*- coding: utf-8 -*-
"""把已打好的 dist\\mingding 上传到 GitHub Releases。

用法：
    build_mingding.bat                  # 先打包
    Compress-Archive -Path dist\\mingding -DestinationPath dist\\mingding-win64.zip -Force
    python tools\\upload_release.py v1.0.0

两点经验：
- 本机直连 github 会被重置，必须走 git 里配的那个 SOCKS5 代理（http.proxy）。
- 传大文件交给 curl：urllib 没走代理时会传到一半 ConnectionReset。
  token 写进临时 curl config 文件，不出现在命令行参数里。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = "17601413731/mingding"
API = "https://api.github.com"
PROXY = "socks5h://127.0.0.1:10808"
UPLOAD_ATTEMPTS = 3
NOTES = Path(".github/release-notes.md")


def token() -> str:
    out = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    raise SystemExit("git credential helper 里没有 github.com 的密码")


def _temp(prefix: str, suffix: str, content: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)  # 不关的话 Windows 上 unlink 会 WinError 32
    path = Path(name)
    path.write_text(content, encoding="utf-8")
    return path


def curl(args: list[str], tok: str | None = None) -> subprocess.CompletedProcess:
    """跑一次 curl；给了 tok 就写临时 config，避免 token 进命令行。"""
    cfg = None
    argv = ["curl.exe", "-sS", "--ssl-no-revoke", "--proxy", PROXY]
    try:
        if tok:
            cfg = _temp(".curl-", ".cfg", f'header = "Authorization: token {tok}"\n')
            argv += ["--config", str(cfg)]
        return subprocess.run(argv + args, capture_output=True, text=True, encoding="utf-8")
    finally:
        if cfg:
            cfg.unlink(missing_ok=True)


def api_get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url)
    for k, v in {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "mingding-release",
    }.items():
        req.add_header(k, v)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": PROXY}))
    with opener.open(req, timeout=120) as resp:
        return json.loads(resp.read())


def create_release(tag: str, title: str, tok: str) -> dict:
    body = {
        "tag_name": tag,
        "name": title,
        "body": NOTES.read_text(encoding="utf-8"),
        "draft": False,
        "prerelease": False,
    }
    path = _temp(".rel-", ".json", json.dumps(body, ensure_ascii=False))
    try:
        out = curl([
            "-X", "POST", f"{API}/repos/{REPO}/releases",
            "-H", "Accept: application/vnd.github+json",
            "-H", "User-Agent: mingding-release",
            "-H", "Content-Type: application/json; charset=utf-8",
            "--data-binary", f"@{path}",
        ], tok)
    finally:
        path.unlink(missing_ok=True)
    if out.returncode != 0:
        raise SystemExit(f"创建 Release 失败：{out.stderr.strip()}")
    return json.loads(out.stdout)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tag = args[0] if args else "v1.0.0"
    notes = NOTES.read_text(encoding="utf-8")
    if "--dry-run" in sys.argv:
        print(json.dumps({"tag_name": tag, "name": f"{tag} · 命定", "body_head": notes[:100]},
                         ensure_ascii=False, indent=2))
        return

    zips = sorted(Path("dist").glob("*.zip"))
    if not zips:
        raise SystemExit("dist 下没有 zip，先跑 build_mingding.bat 再压缩")
    asset_path = zips[-1]

    tok = token()
    try:
        rel = api_get(f"{API}/repos/{REPO}/releases/tags/{tag}", tok)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        print(f"{tag} 还没有 Release，创建一个……")
        rel = create_release(tag, f"{tag} · 命定", tok)
    print(f"Release：{rel['html_url']}")

    names = [a["name"] for a in rel["assets"]]
    if asset_path.name in names:
        print(f"已有同名 asset，跳过上传：{names}")
        return

    size_mb = asset_path.stat().st_size / 1024 / 1024
    url = (f"https://uploads.github.com/repos/{REPO}/releases/{rel['id']}"
           f"/assets?name={asset_path.name}")
    for attempt in range(1, UPLOAD_ATTEMPTS + 1):
        print(f"上传 {asset_path.name}（{size_mb:.1f} MB）第 {attempt}/{UPLOAD_ATTEMPTS} 次……",
              flush=True)
        started = time.time()
        out = curl([
            "-X", "POST", url,
            "-H", "Accept: application/vnd.github+json",
            "-H", "User-Agent: mingding-release",
            "-H", "Content-Type: application/zip",
            "--data-binary", f"@{asset_path}",
            "--http1.1",
            "--retry", "3", "--retry-all-errors", "--retry-delay", "5",
        ], tok)
        if out.returncode == 0:
            asset = json.loads(out.stdout)
            print(f"上传完成：{asset['name']}  {asset['size'] / 1024 / 1024:.1f} MB  "
                  f"用了 {time.time() - started:.0f} 秒")
            print(f"下载地址：{asset['browser_download_url']}")
            return
        print(f"第 {attempt} 次失败：{out.stderr.strip()[:400]}")
        if attempt < UPLOAD_ATTEMPTS:
            time.sleep(10 * attempt)
    raise SystemExit("三次都失败，asset 没有上传成功")


if __name__ == "__main__":
    main()
