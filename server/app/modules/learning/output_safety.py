"""Shared conservative markup filter with a narrow inert C++ type exception.

This recognizes common vector/pair type spellings, not arbitrary text preceding
an angle bracket. It is a syntax heuristic and does not establish semantic safety.
"""

import re

_SCALAR = (
    r"(?:std::string|string|bool|char|short|int|float|double|size_t|std::size_t|"
    r"int32_t|int64_t|uint32_t|uint64_t|long(?:\s+(?:long|double))?|"
    r"unsigned(?:\s+(?:char|short|int|long(?:\s+long)?))?)"
)
_INERT_CPP_TYPE = re.compile(
    r"(?<![A-Za-z0-9_:])(?:std::)?(?:"
    r"vector\s*<\s*" + _SCALAR + r"\s*>|"
    r"pair\s*<\s*" + _SCALAR + r"\s*,\s*" + _SCALAR + r"\s*>)"
)
_MARKUP = re.compile(r"```|<\s*/?\s*[a-zA-Z][\w:-]*(?:\s[^>]*)?>")


def has_forbidden_markup(text: str) -> bool:
    # Remove only the recognized type expression; scan neighboring tags normally.
    return bool(_MARKUP.search(_INERT_CPP_TYPE.sub("", text)))
