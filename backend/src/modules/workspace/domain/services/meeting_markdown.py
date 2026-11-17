"""
The Markdown subset of meeting cards. A card's body is Markdown limited to
what the card editor offers, and every save passes through
`normalise_card_markdown`, which keeps that subset in one canonical spelling
and turns everything else into plain text. The browser editor writes the
same spelling, so a body that went through the editor and back is
unchanged. `backend/tests/fixtures/meeting_markdown_cases.json` holds the
cases both sides test against.

The subset:

- One heading level, written `### `. Other heading levels are plain text.
- Paragraphs. A single line break inside a paragraph stays a line break.
- Bold `**text**` and italic `*text*`. `__text__` and `_text_` are read as
  the same and written with asterisks.
- Bullet lists `- ` and numbered lists `1. ` two levels deep. `*` and `+`
  bullets and `1)` numbers are read as the same; deeper items join the
  second level; numbers run on from the first item's number.
- Links `[text](url)` to http, https and mailto addresses. Any other link
  keeps only its text.
- Inline code in backticks.
- Mentions `@[Name](user:<id>)` of users that exist. Another mention keeps
  only `@Name`.
- Images `![alt](file:<id>)` of the meeting's own files. Another image
  keeps only its alt text.

Everything else, such as block quotes, code blocks, tables, rules, raw HTML
and strike-through, becomes text: a character that would start such syntax
is escaped with a backslash, the way the editor's serializer escapes it.
Raw HTML needs no escape, since every renderer of card bodies has HTML off.
"""

import re
from collections.abc import Iterator
from collections.abc import Set
from dataclasses import dataclass
from dataclasses import field

# ── Inline nodes ──────────────────────────────────────────────────────


@dataclass
class _Text:
    text: str


@dataclass
class _Break:
    pass


@dataclass
class _Code:
    code: str


@dataclass
class _Mention:
    name: str
    user_id: int


@dataclass
class _Image:
    alt: str
    file_id: int


@dataclass
class _Link:
    children: list["_Inline"]
    url: str


@dataclass
class _Strong:
    children: list["_Inline"]


@dataclass
class _Em:
    children: list["_Inline"]


_Inline = _Text | _Break | _Code | _Mention | _Image | _Link | _Strong | _Em


@dataclass(frozen=True)
class NormalisedMarkdown:
    """A body in canonical form with the users it mentions and the files
    its images show."""

    text: str
    mentioned_user_ids: frozenset[int]
    image_file_ids: frozenset[int]


@dataclass
class _Refs:
    users: Set[int]
    files: Set[int]
    mentioned: set[int] = field(default_factory=set)
    images: set[int] = field(default_factory=set)


_PUNCTUATION = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_MENTION_RE = re.compile(r"@\[([^\[\]\n]+)\]\(user:(\d+)\)")
_IMAGE_RE = re.compile(r"!\[([^\[\]\n]*)\]\(([^()\s]*)\)")
_FILE_URL_RE = re.compile(r"file:(\d+)")
_LINK_RE = re.compile(r"\[((?:[^\[\]\n\\]|\\.)*)\]\(([^()\s]+)\)")
_ALLOWED_LINK = re.compile(r"(?i)(https?://|mailto:)\S+")


def _is_word(char: str) -> bool:
    return char.isalnum()


def _find_closer(s: str, start: int, delimiter: str) -> int:
    """The index of the delimiter that closes one opened before `start`: one
    preceded by a non-space, not part of a longer run of the same character
    for a single delimiter, and for an underscore not followed by a word
    character. -1 when there is none. Code spans are skipped."""
    char = delimiter[0]
    width = len(delimiter)
    i = start
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "`":
            run = _run_length(s, i, "`")
            end = _code_span_end(s, i, run)
            i = end + run if end != -1 else i + run
            continue
        if s[i] == char:
            run = _run_length(s, i, char)
            if (
                run >= width
                and i > start
                and not s[i - 1].isspace()
                and (width == 2 or run == 1)
                and not (char == "_" and i + run < len(s) and _is_word(s[i + run]))
            ):
                return i if width == 1 else i + run - width
            i += run
            continue
        i += 1
    return -1


def _code_span_end(s: str, start: int, run: int) -> int:
    """Where the backtick run that closes the code span opened at `start`
    begins: the next run of the same length on the same line, since the
    editor keeps code within a line. -1 when there is none."""
    line_end = s.find("\n", start)
    limit = len(s) if line_end == -1 else line_end
    i = start + run
    while i < limit:
        if s[i] == "`":
            length = _run_length(s, i, "`")
            if length == run:
                return i
            i += length
            continue
        i += 1
    return -1


def _run_length(s: str, i: int, char: str) -> int:
    end = i
    while end < len(s) and s[end] == char:
        end += 1
    return end - i


def _parse_inline(s: str, refs: _Refs, *, in_link: bool = False) -> list[_Inline]:
    return _InlineParser(s, refs, in_link=in_link).parse()


class _InlineParser:
    """Reads one span of inline markdown left to right. Each handler takes
    the construct at the cursor and returns True, or returns False when the
    character there starts none, so it is kept as plain text. Inside a link
    label no mention, image or nested link starts."""

    def __init__(self, s: str, refs: _Refs, *, in_link: bool) -> None:
        self.s = s
        self.refs = refs
        self.in_link = in_link
        self.nodes: list[_Inline] = []
        self.buf: list[str] = []
        self.i = 0

    def parse(self) -> list[_Inline]:
        while self.i < len(self.s):
            if not self._step():
                self.buf.append(self.s[self.i])
                self.i += 1
        self._flush()
        return self.nodes

    def _step(self) -> bool:
        char = self.s[self.i]
        if char in "*_":
            return self._emphasis(char)
        if char in "@![" and self.in_link:
            return False
        handler = {
            "\\": self._escape,
            "\n": self._break,
            "`": self._code_span,
            "@": self._mention,
            "!": self._image,
            "[": self._link,
        }.get(char)
        return handler is not None and handler()

    def _flush(self) -> None:
        if self.buf:
            self.nodes.append(_Text("".join(self.buf)))
            self.buf.clear()

    def _emit(self, node: _Inline) -> None:
        self._flush()
        self.nodes.append(node)

    def _escape(self) -> bool:
        s, i = self.s, self.i
        if i + 1 < len(s) and s[i + 1] in _PUNCTUATION:
            self.buf.append(s[i + 1])
            self.i += 2
            return True
        return False

    def _break(self) -> bool:
        self._emit(_Break())
        self.i += 1
        return True

    def _code_span(self) -> bool:
        s, i = self.s, self.i
        run = _run_length(s, i, "`")
        end = _code_span_end(s, i, run)
        if end == -1:
            self.buf.append("`" * run)
            self.i += run
            return True
        code = s[i + run : end]
        if len(code) > 1 and code.startswith(" ") and code.endswith(" ") and code.strip():
            code = code[1:-1]
        self._emit(_Code(code))
        self.i = end + run
        return True

    def _mention(self) -> bool:
        match = _MENTION_RE.match(self.s, self.i)
        if match is None:
            return False
        name, user_id = match.group(1).strip(), int(match.group(2))
        if user_id in self.refs.users and name:
            self._emit(_Mention(name, user_id))
            self.refs.mentioned.add(user_id)
        else:
            self.buf.append(f"@{name}")
        self.i = match.end()
        return True

    def _image(self) -> bool:
        match = _IMAGE_RE.match(self.s, self.i)
        if match is None:
            return False
        alt = match.group(1).strip()
        file_match = _FILE_URL_RE.fullmatch(match.group(2))
        if file_match is not None and int(file_match.group(1)) in self.refs.files:
            self._emit(_Image(alt, int(file_match.group(1))))
            self.refs.images.add(int(file_match.group(1)))
        else:
            self.buf.append(alt)
        self.i = match.end()
        return True

    def _link(self) -> bool:
        match = _LINK_RE.match(self.s, self.i)
        if match is None:
            return False
        children = _parse_inline(match.group(1), self.refs, in_link=True)
        url = match.group(2)
        self._flush()
        if _ALLOWED_LINK.fullmatch(url) and children:
            self.nodes.append(_Link(children, url))
        else:
            self.nodes.extend(children)
        self.i = match.end()
        return True

    def _emphasis(self, char: str) -> bool:
        """Strong for a run of two or more, emphasis for one, when the run
        can open (no space after it, and an underscore not inside a word)
        and a closer follows; else the run stays text."""
        s, i = self.s, self.i
        run = _run_length(s, i, char)
        opens = (
            i + run < len(s)
            and not s[i + run].isspace()
            and not (char == "_" and i > 0 and _is_word(s[i - 1]))
        )
        if opens:
            width = 2 if run >= 2 else 1
            end = _find_closer(s, i + width, char * width)
            if end != -1:
                inner = _parse_inline(s[i + width : end], self.refs, in_link=self.in_link)
                self._emit(_Strong(inner) if width == 2 else _Em(inner))
                self.i = end + width
                return True
        self.buf.append(char * run)
        self.i += run
        return True


# ── Serialising inline nodes ──────────────────────────────────────────

_ESCAPED = re.compile(r"[`*\\~\[\]_]")
_LINE_START_ESCAPES = (
    (re.compile(r"^(\+ |[-*>])"), r"\\\1"),
    (re.compile(r"^(#{1,6})(\s|$)"), r"\\\1\2"),
    (re.compile(r"^(\d+)([.)])(\s|$)"), r"\1\\\2\3"),
    (re.compile(r"^(=+\s*)$"), r"\\\1"),
)
_TABLE_DELIMITER = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")


def _escape_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        i = match.start()
        if (
            match.group() == "_"
            and 0 < i < len(text) - 1
            and _is_word(text[i - 1])
            and _is_word(text[i + 1])
        ):
            return "_"
        return "\\" + match.group()

    return _ESCAPED.sub(replace, text)


def _escape_line_start(text: str) -> str:
    if _TABLE_DELIMITER.match(text):
        text = text.replace("|", "\\|")
    for pattern, replacement in _LINE_START_ESCAPES:
        text = pattern.sub(replacement, text, count=1)
    return text


def _code(code: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", code)), default=0)
    fence = "`" * (longest + 1)
    # A reader strips one space on each side of a span that has both, so a
    # span that starts or ends with a backtick or a space gets one more.
    spaced = code.startswith(" ") and code.endswith(" ") and code.strip() != ""
    pad = " " if code.startswith("`") or code.endswith("`") or spaced else ""
    return f"{fence}{pad}{code}{pad}{fence}"


def _label(text: str) -> str:
    """A mention name or image alt text, with the characters that would end
    it taken out."""
    return re.sub(r"[\[\]\n]", "", text).strip()


def _serialise(nodes: list[_Inline], *, continuation: str = "", at_line_start: bool = True) -> str:
    out: list[str] = []
    line_start = at_line_start
    for node in nodes:
        if isinstance(node, _Break):
            out.append("\n" + continuation)
            line_start = True
            continue
        if isinstance(node, _Text):
            text = _escape_text(node.text)
            out.append(_escape_line_start(text) if line_start else text)
        elif isinstance(node, _Code):
            out.append(_code(node.code))
        elif isinstance(node, _Mention):
            out.append(f"@[{_label(node.name)}](user:{node.user_id})")
        elif isinstance(node, _Image):
            out.append(f"![{_label(node.alt)}](file:{node.file_id})")
        elif isinstance(node, _Link):
            inner = _serialise(node.children, continuation=continuation, at_line_start=False)
            out.append(f"[{inner}]({node.url})")
        else:
            inner = _serialise(node.children, continuation=continuation, at_line_start=False)
            if not inner.strip():
                out.append(inner)
            else:
                mark = "**" if isinstance(node, _Strong) else "*"
                out.append(f"{mark}{inner}{mark}")
        line_start = False
    return "".join(out)


# ── Blocks ────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^ {0,3}### +(.*?)(?: +#+)? *$")
_ITEM_RE = re.compile(r"^( *)([-*+]|\d{1,9}[.)])(?: +(.*))?$")


@dataclass
class _Item:
    ordered: bool
    number: int
    lines: list[str]
    children: list["_List"] = field(default_factory=list)


@dataclass
class _List:
    ordered: bool
    items: list[_Item]


@dataclass
class _Paragraph:
    lines: list[str]


@dataclass
class _Heading:
    text: str


_Block = _Paragraph | _Heading | _List


def _expand_tabs(line: str) -> str:
    stripped = line.lstrip(" \t")
    indent = line[: len(line) - len(stripped)].replace("\t", "    ")
    return indent + stripped


def _item_of(match: re.Match[str]) -> _Item:
    marker = match.group(2)
    ordered = marker[0].isdigit()
    return _Item(
        ordered=ordered,
        number=int(marker[:-1]) if ordered else 0,
        lines=[(match.group(3) or "").strip()],
    )


def _place_item(blocks: list[_Block], current: _List | None, item: _Item, indent: int) -> _List:
    """Adds a list item: under the last item of the open list when indented
    by two spaces or more, else to the open list when it is of the same
    kind, else to a new list. Returns the open top level list."""
    if indent >= 2 and current is not None and current.items:
        parent = current.items[-1]
        if parent.children and parent.children[-1].ordered == item.ordered:
            parent.children[-1].items.append(item)
        else:
            parent.children.append(_List(ordered=item.ordered, items=[item]))
        return current
    if current is not None and current.ordered == item.ordered:
        current.items.append(item)
        return current
    current = _List(ordered=item.ordered, items=[item])
    blocks.append(current)
    return current


def _parse_blocks(source: str) -> list[_Block]:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_expand_tabs(line).rstrip() for line in source.split("\n")]
    blocks: list[_Block] = []
    paragraph: list[str] | None = None
    current: _List | None = None
    last_item: _Item | None = None
    after_blank = False

    for line in lines:
        if not line.strip():
            paragraph = None
            after_blank = True
            continue
        # "**bold**" starts with a marker character but no space follows it,
        # so it is no list item.
        item_match = _ITEM_RE.match(line)
        if item_match is not None:
            item = _item_of(item_match)
            paragraph = None
            current = _place_item(blocks, current, item, len(item_match.group(1)))
            last_item = item
            after_blank = False
            continue
        if current is not None and last_item is not None:
            indented = len(line) - len(line.lstrip(" ")) >= 2
            if not after_blank or indented:
                last_item.lines.append(line.strip())
                after_blank = False
                continue
        current = None
        last_item = None
        after_blank = False
        heading = _HEADING_RE.match(line)
        if heading is not None and heading.group(1).strip():
            paragraph = None
            blocks.append(_Heading(heading.group(1).strip()))
            continue
        if paragraph is None:
            paragraph = []
            blocks.append(_Paragraph(paragraph))
        paragraph.append(line.strip())
    return blocks


def _render_list(block: _List, refs: _Refs, indent: str, level: int) -> list[str]:
    out: list[str] = []
    start = block.items[0].number if block.ordered else 0
    width = len(str(start + len(block.items) - 1)) if block.ordered else 0
    for offset, item in enumerate(block.items):
        if block.ordered:
            number = str(start + offset)
            marker = " " * (width - len(number)) + f"{number}. "
        else:
            marker = "- "
        continuation = indent + " " * len(marker)
        text = _serialise(_parse_inline("\n".join(item.lines), refs), continuation=continuation)
        out.append((indent + marker + text).rstrip() if text else (indent + marker).rstrip())
        for child in item.children:
            child_indent = continuation if level == 1 else indent
            out.extend(_render_list(child, refs, child_indent, 2))
    return out


def normalise_card_markdown(
    body: str, *, user_ids: Set[int], file_ids: Set[int]
) -> NormalisedMarkdown:
    """The body in canonical form. `user_ids` are the users a mention may
    name and `file_ids` the meeting files an image may show."""
    refs = _Refs(users=user_ids, files=file_ids)
    rendered: list[str] = []
    for block in _parse_blocks(body):
        if isinstance(block, _Heading):
            rendered.append(
                "### " + _serialise(_parse_inline(block.text, refs), at_line_start=False)
            )
        elif isinstance(block, _Paragraph):
            text = _serialise(_parse_inline("\n".join(block.lines), refs))
            if text.strip():
                rendered.append(text)
        else:
            rendered.append("\n".join(_render_list(block, refs, "", 1)))
    return NormalisedMarkdown(
        text="\n\n".join(rendered),
        mentioned_user_ids=frozenset(refs.mentioned),
        image_file_ids=frozenset(refs.images),
    )


def referenced_ids(body: str) -> tuple[set[int], set[int]]:
    """The user ids the body's mentions name and the file ids its images
    name, before checking that they exist."""
    users = {int(match.group(2)) for match in _MENTION_RE.finditer(body)}
    files = {
        int(file_match.group(1))
        for match in _IMAGE_RE.finditer(body)
        if (file_match := _FILE_URL_RE.fullmatch(match.group(2))) is not None
    }
    return users, files


# ── Plain text ────────────────────────────────────────────────────────


def _plain(nodes: list[_Inline]) -> str:
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, _Text):
            parts.append(node.text)
        elif isinstance(node, _Break):
            parts.append(" ")
        elif isinstance(node, _Code):
            parts.append(node.code)
        elif isinstance(node, _Mention):
            parts.append(f"@{node.name}")
        elif isinstance(node, _Image):
            continue
        else:
            parts.append(_plain(node.children))
    return "".join(parts)


def _plain_list(block: _List, refs: _Refs) -> list[str]:
    parts: list[str] = []
    for item in block.items:
        parts.append(_plain(_parse_inline("\n".join(item.lines), refs)))
        for child in item.children:
            parts.extend(_plain_list(child, refs))
    return parts


def plain_excerpt(bodies: list[str], limit: int = 240) -> str:
    """The text of the bodies without Markdown, one line, cut to `limit`
    characters, for the notes column of the meeting lists. Mentions show as
    @Name and images are left out."""
    everything = _Refs(users=_Everything(), files=_Everything())
    parts: list[str] = []
    for body in bodies:
        for block in _parse_blocks(body):
            if isinstance(block, _Heading):
                parts.append(_plain(_parse_inline(block.text, everything)))
            elif isinstance(block, _Paragraph):
                parts.append(_plain(_parse_inline("\n".join(block.lines), everything)))
            else:
                parts.extend(_plain_list(block, everything))
    text = " ".join(" ".join(parts).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class _Everything(Set[int]):
    """Every id, so an excerpt reads mentions and images whatever they name."""

    def __contains__(self, value: object) -> bool:
        return True

    def __iter__(self) -> Iterator[int]:
        return iter(())

    def __len__(self) -> int:
        return 0
