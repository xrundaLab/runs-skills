#!/usr/bin/env python3
"""Validate generated dynamic-page HTML without authorizing RunS operations."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CONTENT_CLASSES = {"knowledge-content", "case-content"}
BLOCK_TAGS = {"p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
ORPHAN_PUNCTUATION_RE = re.compile(r"^[，。！？；：、,.!?;:]")
ONLY_PUNCTUATION_RE = re.compile(r"^[，。！？；：、,.!?;:]+$")
PUNCTUATED_ROLE_BLOCK_RE = re.compile(r"^(?:文字|图片|图像|声音|音频).+[，；,;]$")
CHROME68_CSS_PATTERNS = {
    "clamp()": re.compile(r"\bclamp\s*\(", re.I),
    "min()/max()": re.compile(r"\b(?:min|max)\s*\(", re.I),
    "dynamic viewport unit": re.compile(r"\d(?:dvh|svh|lvh)\b", re.I),
    "aspect-ratio": re.compile(r"\baspect-ratio\s*:", re.I),
    "inset shorthand": re.compile(r"(?:^|[;{])\s*inset\s*:", re.I),
    "env()": re.compile(r"\benv\s*\(", re.I),
    "backdrop-filter": re.compile(r"backdrop-filter\s*:", re.I),
    "text-wrap": re.compile(r"\btext-wrap\s*:", re.I),
    "overflow-wrap:anywhere": re.compile(r"\boverflow-wrap\s*:\s*anywhere\b", re.I),
    "logical spacing": re.compile(r"\b(?:margin|padding|inset)-(?:inline|block)(?:-start|-end)?\s*:", re.I),
    "modern color": re.compile(r"\b(?:oklab|oklch|color-mix)\s*\(", re.I),
}
CHROME68_JS_PATTERNS = {
    "optional chaining": re.compile(r"\?\."),
    "nullish coalescing": re.compile(r"\?\?"),
    "logical assignment": re.compile(r"(?:\|\||&&|\?\?)="),
    "numeric separator": re.compile(r"\b\d[\d_]*_\d[\d_]*\b"),
    "regular expression indices flag": re.compile(r"/(?:\\.|[^/\n])+/[dgimsuvy]*d[dgimsuvy]*"),
    "class field or static block": re.compile(
        r"\bclass\s+[A-Za-z_$][\w$]*[^\{]*\{[^}]*?(?:\n\s*(?:static\s+)?[#A-Za-z_$][\w$]*\s*=|\bstatic\s*\{)",
        re.S,
    ),
    "unsupported DOM API": re.compile(r"\.(?:replaceChildren|toggleAttribute|getAnimations)\s*\(|\b(?:queueMicrotask|structuredClone)\s*\(|crypto\.randomUUID\s*\("),
    "unsupported builtin": re.compile(r"\.(?:flat|flatMap|at|matchAll|replaceAll)\s*\(|Object\.(?:fromEntries|hasOwn)\s*\(|Promise\.(?:allSettled|any)\s*\(|\bglobalThis\b"),
}


def chrome68_incompatibilities(html: str) -> list[str]:
    styles = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.I | re.S))
    scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.I | re.S))
    found = [name for name, pattern in CHROME68_CSS_PATTERNS.items() if pattern.search(styles)]
    for block in re.findall(r"\{([^{}]*)\}", styles, re.S):
        if re.search(r"display\s*:\s*(?:inline-)?flex\b", block, re.I) and re.search(r"(?:^|;)\s*gap\s*:", block, re.I):
            found.append("flex gap")
            break
    found.extend(name for name, pattern in CHROME68_JS_PATTERNS.items() if pattern.search(scripts))
    return sorted(set(found))


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def block_text(block: dict[str, Any]) -> str:
    text = block.get("text")
    if isinstance(text, str):
        return text
    items = block.get("items")
    return "".join(item for item in items if isinstance(item, str)) if isinstance(items, list) else ""


class ContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.content_depth = 0
        self.skip_depth = 0
        self.visible_parts: list[str] = []
        self.top_regions = 0
        self.block_stack: list[tuple[str, list[str]]] = []
        self.block_texts: list[str] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self.attrs_dict(attrs)
        classes = set(values.get("class", "").split())
        if self.content_depth == 0 and tag == "article" and classes & CONTENT_CLASSES:
            self.content_depth = 1
        elif self.content_depth:
            self.content_depth += 1
        if not self.content_depth:
            return
        if tag in {"script", "style"}:
            self.skip_depth += 1
        if values.get("data-visual-region") == "top":
            self.top_regions += 1
        if tag in BLOCK_TAGS:
            self.block_stack.append((tag, []))

    def handle_endtag(self, tag: str) -> None:
        if not self.content_depth:
            return
        if self.block_stack and self.block_stack[-1][0] == tag:
            _, parts = self.block_stack.pop()
            self.block_texts.append("".join(parts).strip())
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        self.content_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.content_depth or self.skip_depth:
            return
        self.visible_parts.append(data)
        for _, parts in self.block_stack:
            parts.append(data)


def validate_html(html: str, page: dict[str, Any]) -> list[dict[str, str]]:
    parser = ContentParser()
    parser.feed(html)
    issues: list[dict[str, str]] = []
    incompatible = chrome68_incompatibilities(html)
    if incompatible:
        issues.append(
            {
                "code": "DYNAMIC_HTML_CHROME68_INCOMPATIBLE",
                "message": "动态 HTML 使用 Chrome 68 不兼容特性：" + "、".join(incompatible),
            }
        )
    effective = page.get("effective_content")
    blocks = effective.get("blocks") if isinstance(effective, dict) else None
    if not isinstance(blocks, list) or not blocks:
        return [{"code": "DYNAMIC_HTML_INPUT_INVALID", "message": "S5 页面缺少 effective_content.blocks"}]

    expected = compact_text("".join(block_text(block) for block in blocks if isinstance(block, dict)))
    actual = compact_text("".join(parser.visible_parts))
    if actual != expected:
        issues.append(
            {
                "code": "DYNAMIC_HTML_SOURCE_PROJECTION_MISMATCH",
                "message": "动态 HTML 学生正文不是 S5 contentBlocks 的逐字、原序、单次投影。",
            }
        )
    if any(
        text
        and (ORPHAN_PUNCTUATION_RE.search(text) or ONLY_PUNCTUATION_RE.fullmatch(text))
        for text in parser.block_texts
    ):
        issues.append(
            {
                "code": "DYNAMIC_HTML_ORPHAN_PUNCTUATION",
                "message": "动态 HTML 存在句首孤立标点或独立标点块。",
            }
        )
    if sum(bool(PUNCTUATED_ROLE_BLOCK_RE.fullmatch(text.strip())) for text in parser.block_texts) >= 2:
        issues.append(
            {
                "code": "DYNAMIC_HTML_PUNCTUATED_CLAUSE_BLOCK_SPLIT",
                "message": "同一句中以逗号或分号连接的媒介/角色分句被拆成了独立块，应保持连续句流并只做行内强调。",
            }
        )
    if parser.top_regions > 4:
        issues.append(
            {
                "code": "DYNAMIC_HTML_TOP_LEVEL_REGION_OVERFLOW",
                "message": f"动态 HTML 顶层视觉区域为 {parser.top_regions}，超过上限 4。",
            }
        )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--effective-content", type=Path, required=True)
    parser.add_argument("--page-no", required=True)
    parser.add_argument("--html", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.effective_content.read_text(encoding="utf-8"))
        pages = payload.get("pages") if isinstance(payload, dict) else None
        page = next(
            item for item in pages or []
            if isinstance(item, dict) and item.get("page_no") == args.page_no
        )
        html = args.html.read_text(encoding="utf-8")
    except (OSError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INPUT_ERROR", "issues": [{"code": "DYNAMIC_HTML_INPUT_INVALID", "message": str(exc)}]}, ensure_ascii=False, indent=2))
        return 2
    issues = validate_html(html, page)
    print(
        json.dumps(
            {
                "status": "BLOCKED" if issues else "PASS",
                "page_no": args.page_no,
                "issues": issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
