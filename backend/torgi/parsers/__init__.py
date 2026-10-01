from torgi.parsers.adilet import AdiletParser
from torgi.parsers.alatau import AlatauParser
from torgi.parsers.base import Parser
from torgi.parsers.bcc import BccParser
from torgi.parsers.bereke import BerekeParser
from torgi.parsers.eurasian import EurasianParser
from torgi.parsers.forte import ForteParser
from torgi.parsers.freedom import FreedomParser
from torgi.parsers.halyk import HalykParser
from torgi.parsers.nurbank import NurbankParser
from torgi.parsers.rbk import RbkParser
from torgi.parsers.sauda import SaudaParser

PARSERS: dict[str, type[Parser]] = {
    p.name: p
    for p in (AdiletParser, SaudaParser, HalykParser, AlatauParser, ForteParser, BccParser, FreedomParser,
              EurasianParser, NurbankParser, BerekeParser, RbkParser)
}
