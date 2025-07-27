from __future__ import annotations
from typing import List
from langchain.tools import BaseTool
from ..tools.webtools import WebSearch, WebFetch
from ..tools.ops import Calculator, FileWrite, Emailer
from ..tools.knowledge import KbSearch, KbAdd

def registry() -> List[BaseTool]:
    return [
        WebSearch(),
        WebFetch(),
        KbSearch(),
        KbAdd(),
        Calculator(),
        FileWrite(),
        Emailer()
    ]
