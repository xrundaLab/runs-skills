"""Canonical page-type names shared by the bundled S1-S6 tools."""

POST_CLASS_CANONICAL_PAGE_TYPE = "拓展练习"
POST_CLASS_INPUT_ALIASES = frozenset(
    {"课后任务", "课后练习", POST_CLASS_CANONICAL_PAGE_TYPE}
)


def is_post_class_page_type(value: object) -> bool:
    return isinstance(value, str) and value in POST_CLASS_INPUT_ALIASES


def canonical_page_type(value: object) -> object:
    return POST_CLASS_CANONICAL_PAGE_TYPE if is_post_class_page_type(value) else value


def canonical_capsule(page_type: object, capsule: object) -> object:
    return (
        POST_CLASS_CANONICAL_PAGE_TYPE
        if is_post_class_page_type(page_type)
        else capsule
    )
