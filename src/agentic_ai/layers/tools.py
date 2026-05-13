from __future__ import annotations

from typing import List

from langchain.tools import BaseTool

from ..tools.knowledge import KbAdd, KbSearch
from ..tools.ops import Calculator, Emailer, FileWrite
from ..tools.webtools import WebFetch, get_web_search_tool


def registry() -> List[BaseTool]:
    return [get_web_search_tool(), WebFetch(), KbSearch(), KbAdd(), Calculator(), FileWrite(), Emailer()]
