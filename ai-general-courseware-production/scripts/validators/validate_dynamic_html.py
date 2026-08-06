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
DIFF_MARKER_RE = re.compile(
    r"^\+\s*(?:[.#@]|</?|const\b|let\b|var\b|function\b)",
    re.I | re.M,
)


def chrome68_incompatibilities(html: str) -> list[str]:
    styles = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", html, re.I | re.S))
    scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.I | re.S))
    found = [name for name, pattern in CHROME68_CSS_PATTERNS.items() if pattern.search(styles)]
    for block in re.findall(r"\{([^{}]*)\}", styles, re.S):
        if re.search(r"display\s*:\s*(?:inline-)?flex\b", block, re.I) and re.search(r"(?:^|;)\s*gap\s*:", block, re.I):
            found.append("flex gap")
            break
    found.extend(name for name, pattern in CHROME68_JS_PATTERNS.items() if pattern.search(scripts))
    if DIFF_MARKER_RE.search(html):
        found.append("diff marker")
    return sorted(set(found))


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def visual_lightbox_contract_incompatibilities(html: str) -> list[str]:
    required = (
        "visual-lightbox-dialog",
        "visual-lightbox-stage",
        "touchstart",
        "touchmove",
        "resetVisualTransform",
        "positionVisualClose",
        "getBoundingClientRect",
        "Math.min(4",
    )
    found = [marker for marker in required if marker not in html]
    lightbox_start = html.find('class="visual-lightbox"')
    stage_start = html.find('class="visual-lightbox-stage"', lightbox_start)
    image_start = html.find('class="visual-lightbox-image"', stage_start)
    close_start = html.find('class="visual-lightbox-close"', lightbox_start)
    if min(lightbox_start, stage_start, image_start, close_start) < 0 or not (
        lightbox_start < stage_start < image_start < close_start
    ):
        found.append("close button below image stage")
    elif "visual-caption" in html[lightbox_start:close_start]:
        found.append("caption inside lightbox")
    if re.search(r">\s*查看大图\s*<", html):
        found.append("visible view-large control")
    close_css = re.search(r"\.visual-lightbox-close\s*\{([^}]*)\}", html, re.I | re.S)
    if not close_css:
        found.append("round fixed close button")
    else:
        declarations = close_css.group(1)
        if not re.search(r"position\s*:\s*fixed", declarations, re.I):
            found.append("fixed close button")
        if not re.search(r"left\s*:\s*50%", declarations, re.I):
            found.append("horizontally centered close button")
        if not re.search(r"border-radius\s*:\s*50%", declarations, re.I):
            found.append("round close button")
    stage_css = re.search(r"\.visual-lightbox-stage\s*\{([^}]*)\}", html, re.I | re.S)
    if not stage_css or not all(
        re.search(pattern, stage_css.group(1), re.I)
        for pattern in (r"align-items\s*:\s*center", r"justify-content\s*:\s*center")
    ):
        found.append("viewport-centered lightbox image")
    close_button = re.search(
        r"<button\b[^>]*class=([\"'])[^\"']*visual-lightbox-close[^\"']*\1[^>]*>(.*?)</button>",
        html,
        re.I | re.S,
    )
    if not close_button or "×" not in re.sub(r"<[^>]+>", "", close_button.group(2)):
        found.append("icon-only close button")
    elif "关闭" in re.sub(r"<[^>]+>", "", close_button.group(2)):
        found.append("visible close text")
    return sorted(set(found))


def block_text(block: dict[str, Any]) -> str:
    text = block.get("text")
    if isinstance(text, str):
        return text
    items = block.get("items")
    return "".join(item for item in items if isinstance(item, str)) if isinstance(items, list) else ""


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class ContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.content_depth = 0
        self.skip_depth = 0
        self.visible_parts: list[str] = []
        self.top_regions = 0
        self.block_stack: list[tuple[str, list[str]]] = []
        self.block_texts: list[str] = []
        self.visual_gallery_depth = 0
        self.visual_gallery_count = 0
        self.visual_group_layouts: list[str] = []
        self.visual_terminal_policies: list[str] = []
        self.semantic_after_gallery: list[str] = []
        self.visual_paired_list_count = 0
        self.visual_pairs: list[dict[str, Any]] = []
        self.current_visual_pair: dict[str, Any] | None = None
        self.visual_pair_item_depth = 0
        self.visual_paired_copy_depth = 0
        self.visual_paired_copy_parts: list[str] = []

    @staticmethod
    def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self.attrs_dict(attrs)
        classes = set(values.get("class", "").split())
        if self.content_depth == 0 and tag == "article" and classes & CONTENT_CLASSES:
            self.content_depth = 1
        elif self.content_depth and tag not in VOID_TAGS:
            self.content_depth += 1
        if not self.content_depth:
            return
        if self.visual_gallery_depth:
            if tag not in VOID_TAGS:
                self.visual_gallery_depth += 1
            if "visual-paired-list" in classes:
                self.visual_paired_list_count += 1
            if "visual-paired-item" in classes:
                pair = {
                    "assetId": values.get("data-visual-pair-asset-id", ""),
                    "copies": [],
                }
                self.visual_pairs.append(pair)
                self.current_visual_pair = pair
                self.visual_pair_item_depth = self.visual_gallery_depth
            if "visual-paired-copy" in classes:
                self.visual_paired_copy_depth = self.visual_gallery_depth
                self.visual_paired_copy_parts = []
            return
        if "visual-gallery" in classes:
            self.visual_gallery_depth = 1
            self.visual_gallery_count += 1
            self.visual_group_layouts.append(values.get("data-visual-group-layout", ""))
            self.visual_terminal_policies.append(values.get("data-visual-placement-terminal", ""))
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
        if self.visual_gallery_depth:
            if (
                self.visual_paired_copy_depth
                and self.visual_gallery_depth == self.visual_paired_copy_depth
            ):
                paired_text = "".join(self.visual_paired_copy_parts).strip()
                if self.current_visual_pair is not None:
                    self.current_visual_pair["copies"].append(paired_text)
                self.block_texts.append(paired_text)
                self.visual_paired_copy_depth = 0
                self.visual_paired_copy_parts = []
            if (
                self.visual_pair_item_depth
                and self.visual_gallery_depth == self.visual_pair_item_depth
            ):
                self.current_visual_pair = None
                self.visual_pair_item_depth = 0
            self.visual_gallery_depth -= 1
            self.content_depth -= 1
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
        if self.visual_gallery_depth:
            if self.visual_paired_copy_depth:
                self.visual_paired_copy_parts.append(data)
                self.visible_parts.append(data)
            return
        self.visible_parts.append(data)
        if self.visual_gallery_count:
            self.semantic_after_gallery.append(data)
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
    visual = page.get("visual")
    if isinstance(visual, dict):
        assets = visual.get("assets")
        if not isinstance(assets, list) or not assets:
            issues.append({"code": "DYNAMIC_HTML_VISUAL_INPUT_INVALID", "message": "S5 visual.assets 不是非空数组。"})
        else:
            required = ("image-zoom-trigger", "visual-lightbox", "visual-lightbox-close", "Escape", "object-fit: contain")
            missing = [marker for marker in required if marker not in html]
            if missing:
                issues.append({"code": "DYNAMIC_HTML_VISUAL_LIGHTBOX_CONTRACT_MISSING", "message": "动态 HTML 缺少同页灯箱合同：" + "、".join(missing)})
            lightbox_incompatible = visual_lightbox_contract_incompatibilities(html)
            if lightbox_incompatible:
                issues.append(
                    {
                        "code": "DYNAMIC_HTML_VISUAL_LIGHTBOX_CONTRACT",
                        "message": "动态 HTML 大图交互不符合非开篇合同："
                        + "、".join(lightbox_incompatible),
                    }
                )
            if "window.open" in html or 'target="_blank"' in html or "target='_blank'" in html:
                issues.append({"code": "DYNAMIC_HTML_VISUAL_EXTERNAL_PREVIEW_FORBIDDEN", "message": "配图缩放不得打开新窗口、外链或新标签页。"})
            if parser.visual_gallery_count != 1:
                issues.append(
                    {
                        "code": "DYNAMIC_HTML_VISUAL_PLACEMENT_CONTAINER_INVALID",
                        "message": "正文内必须且只能有一个 visual-gallery 配图容器。",
                    }
                )
            if len(assets) >= 2 and parser.visual_group_layouts != ["vertical_stack"]:
                issues.append(
                    {
                        "code": "DYNAMIC_HTML_VISUAL_GROUP_LAYOUT_INVALID",
                        "message": "两张及以上配图必须声明并使用 vertical_stack 纵向全宽布局。",
                    }
                )
            if parser.visual_terminal_policies != ["forbidden"] or not compact_text(
                "".join(parser.semantic_after_gallery)
            ):
                issues.append(
                    {
                        "code": "DYNAMIC_HTML_VISUAL_TERMINAL_PLACEMENT",
                        "message": "配图不得成为正文最后一块，必须在 visual-gallery 后保留学生正文。",
                    }
                )
            label_positions: list[int] = []
            for asset in assets:
                if not isinstance(asset, dict):
                    issues.append({"code": "DYNAMIC_HTML_VISUAL_INPUT_INVALID", "message": "S5 visual.assets 含非对象。"})
                    continue
                url = str(asset.get("url") or "")
                alt = str(asset.get("alt") or "")
                image_tags = re.findall(r"<img\b[^>]*>", html, re.I | re.S)
                matching_tags = [tag for tag in image_tags if url and url in tag]
                if len(matching_tags) != 1 or html.count(url) != 1:
                    issues.append({"code": "DYNAMIC_HTML_VISUAL_URL_CARDINALITY", "message": f"配图 URL 必须且只能作为一个 img src 出现一次：{asset.get('assetId')}"})
                elif not re.search(rf"\balt\s*=\s*([\"']){re.escape(alt)}\1", matching_tags[0], re.I | re.S):
                    issues.append({"code": "DYNAMIC_HTML_VISUAL_ALT_MISMATCH", "message": f"配图 alt 未按 S5 原样投影：{asset.get('assetId')}"})
                label = asset.get("displayLabel")
                if isinstance(label, str) and label:
                    label_positions.append(html.find(label))
                    if html.count(label) != 1:
                        issues.append({"code": "DYNAMIC_HTML_VISUAL_LABEL_CARDINALITY", "message": f"配图标签必须原样且单次出现：{asset.get('assetId')}"})
            if label_positions and (any(position < 0 for position in label_positions) or label_positions != sorted(label_positions)):
                issues.append({"code": "DYNAMIC_HTML_VISUAL_ORDER_MISMATCH", "message": "组图标签顺序与 S5 planVisualAssets 不一致。"})
            paired_assets = [
                asset
                for asset in assets
                if isinstance(asset, dict) and "pairedStudentText" in asset
            ]
            if paired_assets:
                invalid_pairs = (
                    len(paired_assets) != len(assets)
                    or parser.visual_paired_list_count != 1
                    or len(parser.visual_pairs) != len(paired_assets)
                )
                if not invalid_pairs:
                    for asset, rendered in zip(paired_assets, parser.visual_pairs):
                        expected_text = asset.get("pairedStudentText")
                        if (
                            rendered.get("assetId") != asset.get("assetId")
                            or not isinstance(expected_text, str)
                            or len(rendered.get("copies") or []) != 1
                            or compact_text(rendered["copies"][0]) != compact_text(expected_text)
                        ):
                            invalid_pairs = True
                            break
                if invalid_pairs:
                    issues.append(
                        {
                            "code": "DYNAMIC_HTML_VISUAL_TEXT_PAIRING_INVALID",
                            "message": "含 pairedStudentText 的组图必须按 S5 顺序逐项渲染为 visual-paired-list；每个 visual-paired-item 内必须相邻包含本图、图注和唯一对应文案。",
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
