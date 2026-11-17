"""
Server-side belt-and-braces for SendMail: the frontend already escapes item
data and sanitizes the HTML it renders (orderMailTemplate.ts /
sanitizeMailHtml.ts) before a user ever sees a composed mail, but this is
the last point before an arbitrary POST body reaches SMTP, /mail/send
takes html_body straight from the request, and nothing upstream of this
use case is trusted to have sanitized it (a direct API call, a future
caller, or a frontend regression could all reach this unescaped).

Allowlist mirrors the frontend's sanitizeMailHtml.ts so a template that
renders correctly in the browser preview also survives the trip through
mail. Keep the two in sync if either changes.
"""

import nh3

_TAGS = {
    "p",
    "br",
    "div",
    "span",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"style"},
    "a": {"href"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}


def sanitize_mail_html(html: str) -> str:
    """Strips anything script-capable (event handlers, <script>, <iframe>,
    javascript: URLs, ...) while keeping the basic formatting + table
    markup a resolved order-mail template actually uses."""
    return nh3.clean(
        html,
        tags=_TAGS,
        attributes=_ATTRIBUTES,
        set_tag_attribute_values={"a": {"target": "_blank"}},
        link_rel="noopener noreferrer",
    )
