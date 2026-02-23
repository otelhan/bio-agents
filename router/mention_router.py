import re
from dataclasses import dataclass


MENTION_PATTERN = re.compile(r"@(designer|farmer|cfo)\b", re.IGNORECASE)


@dataclass
class ParsedMessage:
    target_agent: str | None  # "designer" | "farmer" | "cfo" | None
    clean_text: str
    has_image: bool
    image_id: str | None


def parse_message(raw_text: str, image_id: str | None = None) -> ParsedMessage:
    """
    Extract @mention from message text.
    Falls back to 'designer' if an image is attached with no @mention.
    Returns None target if no mention and no image (caller must classify).
    """
    match = MENTION_PATTERN.search(raw_text)
    target = match.group(1).lower() if match else None

    if target is None and image_id:
        target = "designer"

    clean = MENTION_PATTERN.sub("", raw_text).strip()
    return ParsedMessage(
        target_agent=target,
        clean_text=clean,
        has_image=image_id is not None,
        image_id=image_id,
    )
