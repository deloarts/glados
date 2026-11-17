"""
Validation for AdminPdmSettings.made_feature_tree_template and
bought_feature_tree_template (docs/FIELD_OWNERSHIP.md's "Label properties
and the feature-tree template" section). A template is the literal value
the SolidWorks add-in writes into the custom property mapped to
feature_tree_representation (item_field_ownership.
FEATURE_TREE_MAPPABLE_FIELD), e.g.
'$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'.
Each `$PRP:"name"` is SolidWorks' own link to another custom property,
which SolidWorks resolves itself, so the feature tree, BOMs and the PDM
datacard always show the current values without anyone re-saving the file.

Glados never renders a template. It only rejects one that cannot work as
a single custom property value: a line break or other control character,
more than MAX_FEATURE_TREE_TEMPLATE_LENGTH characters, or a link to the
property the template itself is written into. A link to any other
property is accepted, because it may name a SolidWorks property Glados
does not know, and a link to a missing property resolves to nothing. Pure
Python, no I/O.
"""

import re

MAX_FEATURE_TREE_TEMPLATE_LENGTH = 255

# SolidWorks matches property names regardless of case, so the
# self-reference check does too.
_PROPERTY_LINK = re.compile(r'\$PRP:"([^"]*)"', re.IGNORECASE)
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


def validate_feature_tree_template(kind: str, template: str, own_property: str) -> None:
    """Raises ValueError when `template` holds a line break or another
    control character, is longer than MAX_FEATURE_TREE_TEMPLATE_LENGTH, or
    links to `own_property`, the custom property `kind`'s template is
    written into, which SolidWorks cannot resolve. `own_property` is ""
    when feature_tree_representation is unmapped, and then no link counts
    as a self-reference. AdminPdmSettings.assert_feature_tree_templates_valid
    wraps this into PdmSettingsInvalidError, the convention every other
    cross-field PDM settings rule uses."""
    if _CONTROL_CHARACTER.search(template):
        raise ValueError(f"{kind} feature tree template must be a single line of text.")
    if len(template) > MAX_FEATURE_TREE_TEMPLATE_LENGTH:
        raise ValueError(
            f"{kind} feature tree template is longer than "
            f"{MAX_FEATURE_TREE_TEMPLATE_LENGTH} characters."
        )
    if own_property and any(
        name.casefold() == own_property.casefold() for name in _PROPERTY_LINK.findall(template)
    ):
        raise ValueError(
            f"{kind} feature tree template links to its own property {own_property!r}."
        )
