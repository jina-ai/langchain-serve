from typing import List
from typing import Literal
from itertools import zip_longest

from pydantic import BaseModel


class SectionText(BaseModel):
    type: Literal["plain_txt", "mrkdwn"] = "mrkdwn"
    text: str = ''


class Block(BaseModel):
    type: Literal["section"] = "section"
    text: SectionText = SectionText()


class TextOrBlock(BaseModel):
    kind: Literal["text", "block"]
    blocks: List[Block] = []
    text: str = ''


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
