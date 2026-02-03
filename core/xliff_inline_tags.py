import re

INLINE_TAG_LOCALNAMES = (
    "bpt",
    "ept",
    "ph",
    "it",
    "mrk",
    "g",
    "x",
    "bx",
    "ex",
)

INLINE_TAG_REGEX = re.compile(
    r"(<(?:"
    + "|".join(INLINE_TAG_LOCALNAMES)
    + r")[^>]*?>.*?</(?:"
    + "|".join(INLINE_TAG_LOCALNAMES)
    + r")>|<(?:"
    + "|".join(INLINE_TAG_LOCALNAMES)
    + r")[^>]*?/>)",
    re.DOTALL,
)

