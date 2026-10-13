from .rewe import Billa, Penny
from .gurkerl import Gurkerl
from .lidl import Lidl
from .off import OpenFoodFacts
from .heisse import HeissePreise, Spar, Hofer, Dm, Mpreis, Unimarkt
from .catalog import CATALOG
ADAPTERS = {a.id: a for a in [Billa(), Penny(), Gurkerl(), Lidl(), Spar(), Hofer(), Dm(), Mpreis(), Unimarkt(), OpenFoodFacts(), HeissePreise()] + [c() for c in CATALOG]}
def get_adapter(i): return ADAPTERS[i]
