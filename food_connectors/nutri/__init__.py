"""Nutrition / quality databases: OFF (Nutri-Score, NOVA, Eco-Score, additives), USDA FDC, CIQUAL,
plus a local implementation of the official Nutri-Score 2023 algorithm (results marked 'berechnet')."""
from .nutriscore import compute_nutriscore
from .sources import NUTRI_SOURCES, nutri_lookup
