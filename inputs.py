# inputs.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List

class SoilType(Enum):
    SAND = "رمل"
    CLAY = "طين"
    ROCK = "صخر"

class PileHeadType(Enum):
    FIXED = "رأس ثابت"
    FREE = "رأس حر"

class RockMethod(Enum):
    ADHESION = "التصاق بسيط (α)"
    WILLIAMS_PELLS = "Williams & Pells"
    ROSENBERG_JOURNEAUX = "Rosenberg & Journeaux"

@dataclass
class Project:
    name: str = "مشروع جديد"
    job_number: str = "000"
    owner: str = ""
    consultant: str = ""
    contractor: str = ""
    location: str = ""

@dataclass
class SoilLayer:
    name: str = "طبقة"
    soil_type: SoilType = SoilType.SAND
    depth_top: float = 0.0      # m (Relative to ground level)
    depth_bottom: float = 5.0   # m
    # Parameters for Sand / Clay
    gamma: float = 18.0         # kN/m³
    phi: float = 30.0           # degree (for Sand)
    Cu: float = 50.0            # kPa (for Clay)
    Es: float = 25000.0         # kPa (Elastic Modulus)
    # Bearing coefficients
    Nq: float = 100.0           # for Sand
    Nc: float = 9.0             # for Clay
    # Adhesion / Lateral
    alpha: float = 0.5          # for Clay
    Ks: float = 1.0             # for Sand
    ignore_skin_friction: bool = False # For socket only analysis
    # Parameters for Rock
    quc: float = 10.0           # kg/cm²
    rock_reduction_factor: float = 0.4 # alpha factor (e.g. 0.4 for Abu Dhabi)
    RQD: float = 0.5

    rock_method: RockMethod = RockMethod.ROSENBERG_JOURNEAUX

@dataclass
class PileGeometry:
    diameter: float = 700            # mm
    pile_length: float = 20.0        # m
    cut_off_level: float = 0.0       # m
    ground_level: float = 0.0        # m
    gwt_level: float = -5.0          # m
    cover: float = 75.0              # mm
    
    @property
    def toe_level(self):
        return self.cut_off_level - self.pile_length

@dataclass
class Reinforcement:
    bar_diameter: int = 16
    num_bars: int = 8
    stirrup_diameter: int = 8
    stirrup_spacing: int = 200

@dataclass
class Loads:
    working_vertical: float = 1000.0 # kN
    horizontal: float = 0.0          # kN
    moment_at_head: float = 0.0      # kN.m

@dataclass
class DesignOptions:
    fos_geotech: float = 3.0
    fos_structural: float = 1.5
    head_type: PileHeadType = PileHeadType.FIXED
    fcu: float = 40.0                # N/mm²
    fy: float = 460.0                # N/mm²
    E_concrete: float = 30000.0      # MN/m²
    nh: float = 5.0                 # MN/m³
    out_of_position: float = 0.075   # m
    assumed_horizontal_pct: float = 0.03

# --- SOIL DATABASE FOR LIBRARY ---
SOIL_DB = {
    "Sand": {
        "Loose Sand": {"gamma": 17.0, "phi": 28.0, "Nq": 30.0, "Es": 15000.0},
        "Medium Sand": {"gamma": 18.5, "phi": 32.0, "Nq": 60.0, "Es": 30000.0},
        "Dense Sand": {"gamma": 20.0, "phi": 38.0, "Nq": 120.0, "Es": 50000.0},
    },
    "Clay": {
        "Soft Clay": {"gamma": 16.0, "Cu": 25.0, "alpha": 0.9, "Es": 5000.0},
        "Medium Clay": {"gamma": 18.0, "Cu": 50.0, "alpha": 0.7, "Es": 15000.0},
        "Stiff Clay": {"gamma": 20.0, "Cu": 100.0, "alpha": 0.45, "Es": 30000.0},
    },
    "Rock": {
        "Weak Rock": {"gamma": 22.0, "quc": 5.0, "Nc": 10.0, "alpha_rock": 0.1, "RQD": 0.3},
        "Medium Rock": {"gamma": 24.0, "quc": 20.0, "Nc": 20.0, "alpha_rock": 0.3, "RQD": 0.6},
        "Hard Rock": {"gamma": 26.0, "quc": 50.0, "Nc": 40.0, "alpha_rock": 0.5, "RQD": 0.9},
    }
}
