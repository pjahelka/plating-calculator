"""Electroplating calculations based on Faraday's law of electrolysis.

Internal base units are cm² (area), µm (thickness), mA/cm² (current density)
and seconds (time). Each *_UNITS table maps a unit label to the factor that
converts one of that unit into the base unit.
"""
from __future__ import annotations

from dataclasses import dataclass

FARADAY = 96485.33212  # C/mol

AREA_UNITS = {"cm²": 1.0, "in²": 6.4516, "mm²": 0.01, "dm²": 100.0, "ft²": 929.0304}
THICKNESS_UNITS = {"µm": 1.0, "mil": 25.4, "µin": 0.0254, "nm": 0.001}
CURRENT_DENSITY_UNITS = {"mA/cm²": 1.0, "A/ft²": 1000.0 / 929.0304, "A/dm²": 10.0}
TIME_UNITS = {"s": 1.0, "min": 60.0, "h": 3600.0}


@dataclass(frozen=True)
class Metal:
    name: str
    ion: str
    molar_mass: float  # g/mol
    electrons: int  # electrons transferred per atom deposited
    density: float  # g/cm³ (bulk; electrodeposits can be slightly lower)
    typical_efficiency: float  # % cathode efficiency, a rough starting point only
    bath: str = ""

    @property
    def label(self) -> str:
        return f"{self.name} ({self.ion})"


METALS = [
    Metal("Nickel", "Ni²⁺", 58.6934, 2, 8.908, 95, "Watts / sulfamate"),
    Metal("Copper", "Cu²⁺", 63.546, 2, 8.96, 98, "acid sulfate"),
    Metal("Copper", "Cu⁺", 63.546, 1, 8.96, 70, "cyanide, 30–100 % depending on bath"),
    Metal("Silver", "Ag⁺", 107.8682, 1, 10.49, 99, "cyanide"),
    Metal("Gold", "Au⁺", 196.96657, 1, 19.30, 90, "cyanide / sulfite; acid hard gold often 30–60 %"),
    Metal("Zinc", "Zn²⁺", 65.38, 2, 7.14, 90, "acid ≈95 %, alkaline ≈60–80 %"),
    Metal("Tin", "Sn²⁺", 118.710, 2, 7.265, 95, "acid sulfate / MSA"),
    Metal("Tin", "Sn⁴⁺", 118.710, 4, 7.265, 70, "alkaline stannate"),
    Metal("Chromium", "Cr⁶⁺", 51.9961, 6, 7.19, 15, "hexavalent / hard chrome, 10–25 %"),
    Metal("Chromium", "Cr³⁺", 51.9961, 3, 7.19, 15, "trivalent, 10–25 %"),
    Metal("Cadmium", "Cd²⁺", 112.414, 2, 8.65, 90, "cyanide / acid"),
    Metal("Cobalt", "Co²⁺", 58.933194, 2, 8.90, 95, "sulfate / chloride"),
    Metal("Iron", "Fe²⁺", 55.845, 2, 7.874, 95, "sulfate / chloride"),
    Metal("Lead", "Pb²⁺", 207.2, 2, 11.34, 98, "fluoborate / MSA"),
    Metal("Palladium", "Pd²⁺", 106.42, 2, 12.02, 90, "ammine / chloride"),
    Metal("Platinum", "Pt²⁺", 195.084, 2, 21.45, 30, "P-salt; varies widely"),
    Metal("Rhodium", "Rh³⁺", 102.90549, 3, 12.41, 50, "sulfate / phosphate; varies widely"),
    Metal("Indium", "In³⁺", 114.818, 3, 7.31, 90, "sulfamate"),
]


@dataclass(frozen=True)
class Result:
    current: float  # A
    time: float  # s
    thickness: float  # µm
    rate: float  # µm/s
    charge: float  # C, total charge passed (including inefficiency losses)
    mass: float  # g of metal deposited


def deposition_rate(metal: Metal, current_density: float, efficiency: float) -> float:
    """Thickness growth rate in µm/s.

    current_density is in mA/cm²; efficiency is a fraction in (0, 1].
    """
    amps_per_cm2 = current_density * 1e-3
    cm_per_s = amps_per_cm2 * efficiency * metal.molar_mass / (
        metal.electrons * FARADAY * metal.density
    )
    return cm_per_s * 1e4


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if not value > 0:
            raise ValueError(f"{name.replace('_', ' ').capitalize()} must be greater than zero.")


def solve(
    metal: Metal,
    area: float,
    current_density: float,
    efficiency: float,
    *,
    thickness: float | None = None,
    time: float | None = None,
) -> Result:
    """Solve for plating time (given thickness) or thickness (given time).

    Units: area cm², current_density mA/cm², efficiency fraction (0, 1],
    thickness µm, time s. Exactly one of thickness/time must be given.
    """
    if (thickness is None) == (time is None):
        raise ValueError("Give exactly one of thickness or time.")
    _require_positive(area=area, current_density=current_density)
    if not 0 < efficiency <= 1:
        raise ValueError("Efficiency must be between 0 and 100 %.")
    _require_positive(
        molar_mass=metal.molar_mass, electrons=metal.electrons, density=metal.density
    )

    rate = deposition_rate(metal, current_density, efficiency)
    if time is None:
        _require_positive(thickness=thickness)
        time = thickness / rate
    else:
        _require_positive(time=time)
        thickness = rate * time

    current = current_density * 1e-3 * area
    return Result(
        current=current,
        time=time,
        thickness=thickness,
        rate=rate,
        charge=current * time,
        mass=metal.density * area * thickness * 1e-4,
    )
