from .rewe import Billa, Penny
from .gurkerl import Gurkerl
from .lidl import Lidl
from .off import OpenFoodFacts
from .heisse import HeissePreise, Spar, Hofer, Dm, Mpreis, Unimarkt
from .catalog import CATALOG
from .mealprep import PrepMyMeal, LiveFresh, Gourmetfein
from .mpreis_shop import MpreisShop
from .dm_shop import DmShop
from .spar_shop import SparShop
from .denns import Denns
from .nah_frisch import NahFrisch
from .penny_shop import PennyShop
from .juit import Juit
from .bofrost import Bofrost
from .fittogo import FitToGo
from .every import Every
from .loewenanteil import Loewenanteil
from .kernbeisser import Kernbeisser
from .goldblatt import Goldblatt
from .alfies import Alfies
from .issmich import IssMich
from .myproduct import MyProduct
from .hofer_shop import HoferShop
from .biohof_achleitner import BiohofAchleitner
from .adamah import Adamah
from .subway_at import SubwayAT
from .osm_stores import OsmStores, fetch_stores
ADAPTERS = {a.id: a for a in [c() for c in CATALOG] + [Billa(), Penny(), Gurkerl(), Lidl(), Spar(), Hofer(), Dm(), DmShop(), Mpreis(), Unimarkt(), OpenFoodFacts(), HeissePreise(), PrepMyMeal(), LiveFresh(), Gourmetfein(), MpreisShop(), SparShop(), Denns(), NahFrisch(), PennyShop(), Juit(), Bofrost(), FitToGo(), Every(), Loewenanteil(), Kernbeisser(), Goldblatt(), IssMich(), Alfies(), MyProduct(), HoferShop(), BiohofAchleitner(), SubwayAT(), Adamah()]}  # live adapters override catalog-only stubs with the same id
def get_adapter(i): return ADAPTERS[i]
STORE_ADAPTERS = {'osm-stores': OsmStores()}
