from __future__ import annotations

from typing import List

from langchain.tools import BaseTool

from ..tools.knowledge import KbAdd, KbSearch
from ..tools.ops import Calculator, Emailer, FileWrite
from ..tools.webtools import WebFetch, WebSearch


def registry() -> List[BaseTool]:
    return [WebSearch(), WebFetch(), KbSearch(), KbAdd(), Calculator(), FileWrite(), Emailer()]
