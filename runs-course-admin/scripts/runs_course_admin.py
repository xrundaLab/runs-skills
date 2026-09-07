#!/usr/bin/env python3
"""Safe CLI for the RunSi course admin API."""
import argparse
import json
import mimetypes
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

HOSTS = {"development": "https://api.dev.xruns.cn", "production": "https://api.xruns.cn"}
KEYCHAIN_SERVICE_PREFIX = "runs-course-admin-token"
CLIENT_ID = "e5cd7e4891bf95d1d19206ce24a7b32e"


def die(message):
    raise SystemExit(f"error: {message}")


def keychain_service(env):
    return f"{KEYCHAIN_SERVICE_PREFIX}-{env}"


def token_from_keychain(env):
    service = keychain_service(env)
    try:
        value = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", service, "-w"],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        die(f"No {env} token is configured. Ask the user for a {env} admin token, then run: python3 scripts/runs_course_admin.py --env {env} configure-token")
    if not value:
        die(f"Configured {env} token is empty. Re-run configure-token for this environment.")
    return value


def configure_token(env):
    value = os.environ.get("RUNS_ADMIN_TOKEN")
    if not value:
        die("Set RUNS_ADMIN_TOKEN in the environment before configuring the token.")
    # Accept a copied Authorization header as well as the raw JWT. Store only the JWT
    # because headers() consistently applies the required Bearer prefix at request time.
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if not value:
        die("Token is empty after removing the optional Bearer prefix.")
    try:
        subprocess.run(
            ["security", "add-generic-password", "-U", "-a", os.environ.get("USER", ""), "-s", keychain_service(env), "-w", value],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        die("macOS Keychain utility 'security' is unavailable.")
    except subprocess.CalledProcessError as exc:
        die(f"Could not save token to Keychain: {exc.stderr.strip()}")
    print(json.dumps({"ok": True, "message": f"{env} token saved to macOS Keychain."}, ensure_ascii=False))


def headers(token, content_type=None):
    output = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Authorization": f"Bearer {token}",
        "clientid": CLIENT_ID,
        "content-language": "zh_CN",
        "Origin": "http://localhost:81",
        "Referer": "http://localhost:81/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    }
    if content_type:
        output["Content-Type"] = content_type
    return output


def request(env, method, path, body=None, content_type=None):
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = Request(HOSTS[env] + "/api/v1" + path, data=data, method=method, headers=headers(token_from_keychain(env), content_type))
    try:
        with urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        die(f"HTTP {exc.code}: {raw}")
    except URLError as exc:
        die(f"Network error: {exc.reason}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        die(f"Non-JSON response: {raw}")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    if isinstance(parsed, dict) and parsed.get("code") not in (None, 200):
        raise SystemExit(2)


def load_payload(path):
    try:
        payload = json.load(sys.stdin) if path == "-" else json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"Cannot read JSON payload: {exc}")
    if not isinstance(payload, dict):
        die("Payload must be a JSON object.")
    return payload


def require(payload, fields):
    missing = [field for field in fields if payload.get(field) in (None, "", [])]
    if missing:
        die("Missing required fields: " + ", ".join(missing))


def write(args, kind, update):
    if not args.confirm:
        die("Write blocked. Review the payload with the user, then rerun with --confirm.")
    payload = load_payload(args.json)
    if kind == "package":
        if update:
            require(payload, ["id"])
        else:
            require(payload, ["courseName", "coverImageOssId", "chapterBo"])
            if not all(isinstance(item, dict) and item.get("title") for item in payload["chapterBo"]):
                die("Every chapterBo item must include title.")
        path = "/business/course/package"
    else:
        if update:
            require(payload, ["id"])
        else:
            require(payload, ["name", "sort", "desc", "coursePackageId", "chapterId", "coverImageOssId"])
        if isinstance(payload.get("lessonKeywords"), list):
            die("lessonKeywords must be a delimiter-joined string, not a JSON array.")
        path = "/business/course"
    request(args.env, "PUT" if update else "POST", path, json.dumps(payload, ensure_ascii=False), "application/json;charset=UTF-8")


def upload(args):
    file_path = Path(args.file)
    if not file_path.is_file():
        die(f"Upload file not found: {file_path}")
    boundary = "----RunsSkill" + uuid.uuid4().hex
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"assetType\"\r\n\r\n{args.asset_type}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_path.name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode(),
        file_path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode(),
    ]
    request(args.env, "POST", "/console/resource/oss/upload/public", b"".join(parts), f"multipart/form-data; boundary={boundary}")


def find_package(args):
    url = HOSTS[args.env] + "/api/v1/business/admin/course_package/list?pageNum=1&pageSize=100&courseName=" + quote(args.name)
    req = Request(url, headers=headers(token_from_keychain(args.env)))
    try:
        with urlopen(req, timeout=45) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        die(f"Package lookup failed: {exc}")
    rows = (parsed.get("data") or {}).get("rows") or parsed.get("rows") or []
    matches = [row for row in rows if row.get("name") == args.name]
    if len(matches) != 1:
        die(f"Expected exactly one exact package name match; found {len(matches)}.")
    print(json.dumps(matches[0], ensure_ascii=False, indent=2))


def find_course(args):
    url = HOSTS[args.env] + "/api/v1/business/course/list?pageNum=1&pageSize=100&name=" + quote(args.name)
    req = Request(url, headers=headers(token_from_keychain(args.env)))
    try:
        with urlopen(req, timeout=45) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        die(f"Course lookup failed: {exc}")
    rows = (parsed.get("data") or {}).get("rows") or parsed.get("rows") or []
    matches = [row for row in rows if row.get("name") == args.name]
    if len(matches) != 1:
        die(f"Expected exactly one exact course name match; found {len(matches)}.")
    print(json.dumps(matches[0], ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=HOSTS, help="Explicit target environment")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("configure-token")
    for name in ("get-package", "get-course"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--id", required=True)
    find = sub.add_parser("find-package")
    find.add_argument("--name", required=True)
    find_course_command = sub.add_parser("find-course")
    find_course_command.add_argument("--name", required=True)
    sub.add_parser("learning-methods")
    up = sub.add_parser("upload")
    up.add_argument("--file", required=True)
    up.add_argument("--asset-type", default="image")
    for name in ("create-package", "update-package", "create-course", "update-course"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--json", required=True)
        cmd.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "configure-token":
        if not args.env:
            die("--env development or --env production is required when configuring a token.")
        configure_token(args.env)
        return
    if not args.env:
        die("--env development or --env production is required for every API request.")
    if args.command == "get-package":
        request(args.env, "GET", "/business/course/package/" + quote(args.id))
    elif args.command == "get-course":
        request(args.env, "GET", "/business/course/" + quote(args.id))
    elif args.command == "learning-methods":
        request(args.env, "GET", "/business/admin/learning-method/enabled-list")
    elif args.command == "find-package":
        find_package(args)
    elif args.command == "find-course":
        find_course(args)
    elif args.command == "upload":
        upload(args)
    else:
        kind = "package" if args.command.endswith("package") else "course"
        write(args, kind, args.command.startswith("update-"))


if __name__ == "__main__":
    main()
