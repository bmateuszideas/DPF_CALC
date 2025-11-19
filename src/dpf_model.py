from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from typing import Dict
from pathlib import Path


@dataclass
class DPFInputs:
    mileage_km: float              # aktualny przebieg
    avg_speed_kmh: float           # średnia prędkość z okresu
    city_ratio: float              # 0–1, ile miasta
    oil_ash_content_pct: float     # % popiołu w oleju
    fuel_sulfur_ppm: float         # siarka w ppm
    regen_interval_km: float = 400.0  # średnia odległość między dopaleniami


@dataclass
class DPFParams:
    dpf_capacity_units: float = 100.0              # umowna pojemność
    base_soot_rate_per_1000km: float = 1.0         # bazowe tempo odkładania sadzy
    ash_factor_per_pct_per_1000km: float = 0.1     # ile “jednostek” popiołu / 1% / 1000 km
    sulfur_factor_per_1000ppm: float = 1.0         # wpływ siarki
    low_speed_threshold_kmh: float = 60.0          # poniżej tego jest “miasto”
    low_speed_sensitivity: float = 1.0             # jak mocno niska prędkość podbija sadzę
    city_sensitivity: float = 1.5                  # jak mocno miasto podbija sadzę


@dataclass
class DPFState:
    soot_load: float
    ash_load: float
    total_ratio: float
    soot_ratio: float
    ash_ratio: float


def predict_dpf_state(inputs: DPFInputs, params: DPFParams = DPFParams()) -> DPFState:
    """
    Uproszczony model stanu DPF na bazie warunków pracy silnika.

    Zwraca obciążenie sadzą i popiołem w jednostkach umownych oraz
    w relacji do pojemności filtra.
    """
    km_thousands = inputs.mileage_km / 1000.0

    # --- SADZA (regenerowalna) ---

    # wpływ miasta
    soot_factor_city = 1.0 + params.city_sensitivity * np.clip(inputs.city_ratio, 0.0, 1.0)

    # wpływ niskiej prędkości
    low_speed_delta = max(0.0, params.low_speed_threshold_kmh - inputs.avg_speed_kmh)
    speed_factor = 1.0 + params.low_speed_sensitivity * (low_speed_delta / params.low_speed_threshold_kmh)

    # wpływ siarki w paliwie
    sulfur_factor = 1.0 + params.sulfur_factor_per_1000ppm * (inputs.fuel_sulfur_ppm / 1000.0)

    soot_rate = params.base_soot_rate_per_1000km * soot_factor_city * speed_factor * sulfur_factor
    soot_load = soot_rate * km_thousands

    # --- POPIÓŁ (nie regeneruje się w dopalaniu) ---
    ash_rate = params.ash_factor_per_pct_per_1000km * inputs.oil_ash_content_pct
    ash_load = ash_rate * km_thousands

    # --- NORMALIZACJA DO POJEMNOŚCI DPF ---
    soot_ratio = soot_load / params.dpf_capacity_units
    ash_ratio = ash_load / params.dpf_capacity_units
    total_ratio = soot_ratio + ash_ratio

    return DPFState(
        soot_load=soot_load,
        ash_load=ash_load,
        total_ratio=total_ratio,
        soot_ratio=soot_ratio,
        ash_ratio=ash_ratio,
    )


def simulate_vehicle_lifecycle(
    base_inputs: DPFInputs,
    max_mileage_km: float = 300_000,
    step_km: float = 5_000.0,
    params: DPFParams = DPFParams(),
) -> pd.DataFrame:
    """
    Prosta symulacja narastania obciążenia DPF w funkcji przebiegu.
    Zwraca DataFrame, idealny pod wykresy / analizę.
    """
    mileages = np.arange(0, max_mileage_km + step_km, step_km)
    records = []

    for m in mileages:
        inp = DPFInputs(
            mileage_km=m,
            avg_speed_kmh=base_inputs.avg_speed_kmh,
            city_ratio=base_inputs.city_ratio,
            oil_ash_content_pct=base_inputs.oil_ash_content_pct,
            fuel_sulfur_ppm=base_inputs.fuel_sulfur_ppm,
            regen_interval_km=base_inputs.regen_interval_km,
        )
        state = predict_dpf_state(inp, params=params)

        row = {
            **asdict(inp),
            "soot_load": state.soot_load,
            "ash_load": state.ash_load,
            "total_ratio": state.total_ratio,
            "soot_ratio": state.soot_ratio,
            "ash_ratio": state.ash_ratio,
        }
        records.append(row)

    return pd.DataFrame(records)
# --- CHEMICZNY KALKULATOR POPIOŁU ---



@dataclass
class OilSpec:
    name: str
    sulfated_ash_pct: float      # [% masowych] z karty technicznej (SAPS)
    density_kg_per_l: float      # [kg/l]


@dataclass
class FuelSpec:
    name: str
    sulfur_ppm: float            # [ppm masowo] zawartość siarki
    density_kg_per_l: float      # [kg/l]


@dataclass
class UsageProfile:
    mileage_km: float                    # przebieg od nowego DPF / ostatniego czyszczenia
    oil_consumption_l_per_1000km: float  # zużycie oleju [l/1000 km]
    fuel_consumption_l_per_100km: float  # zużycie paliwa [l/100 km]


def calc_oil_ash_mass_g(profile: UsageProfile, oil: OilSpec) -> float:
    """
    Liczy masę popiołu z oleju silnikowego [g] na zadanym przebiegu.
    """
    # ile litrów oleju spalił silnik
    oil_liters = (profile.mileage_km / 1000.0) * profile.oil_consumption_l_per_1000km
    # masa oleju
    oil_mass_kg = oil_liters * oil.density_kg_per_l
    # masa popiołu (sulfated ash) z karty [%]
    ash_mass_kg = oil_mass_kg * (oil.sulfated_ash_pct / 100.0)
    return ash_mass_kg * 1000.0  # [g]


def calc_fuel_ash_mass_g(
    profile: UsageProfile,
    fuel: FuelSpec,
    sulfur_to_ash_factor: float = 3.0,
) -> float:
    """
    Liczy przybliżoną masę popiołu z siarki w paliwie [g].

    sulfur_to_ash_factor ~3.0 oznacza, że 1 g siarki daje ok. 3 g popiołu siarczanowego.
    Można to potem doprecyzować / skalibrować.
    """
    fuel_liters = (profile.mileage_km / 100.0) * profile.fuel_consumption_l_per_100km
    fuel_mass_kg = fuel_liters * fuel.density_kg_per_l

    # siarka w paliwie: ppm = mg/kg → 1 ppm = 1e-6 masowo
    sulfur_mass_kg = fuel_mass_kg * (fuel.sulfur_ppm * 1e-6)
    ash_mass_kg = sulfur_mass_kg * sulfur_to_ash_factor
    return ash_mass_kg * 1000.0  # [g]


def calc_dpf_ash_fill(
    profile: UsageProfile,
    oil: OilSpec,
    fuel: FuelSpec,
    dpf_capacity_ash_g: float = 120.0,
    sulfur_to_ash_factor: float = 3.0,
) -> dict:
    """
    Zwraca słownik z:
    - masą popiołu z oleju,
    - masą popiołu z paliwa,
    - sumą,
    - procentowym zapełnieniem DPF (tylko popiół, bez sadzy).
    """
    oil_ash_g = calc_oil_ash_mass_g(profile, oil)
    fuel_ash_g = calc_fuel_ash_mass_g(profile, fuel, sulfur_to_ash_factor=sulfur_to_ash_factor)
    total_ash_g = oil_ash_g + fuel_ash_g

    fill_ratio = total_ash_g / dpf_capacity_ash_g
    fill_percent = fill_ratio * 100.0

    return {
        "oil_ash_g": oil_ash_g,
        "fuel_ash_g": fuel_ash_g,
        "total_ash_g": total_ash_g,
        "dpf_capacity_ash_g": dpf_capacity_ash_g,
        "fill_ratio": fill_ratio,
        "fill_percent": fill_percent,
    }
# =========================
# ŁADOWANIE BAZY CSV (oils.csv, fuels.csv)
# =========================

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_oils_csv(filename: str = "oils.csv") -> Dict[str, OilSpec]:
    """
    Wczytuje oils.csv i zwraca słownik:
    klucz = oil_id z CSV,
    wartość = OilSpec.
    """
    path = DATA_DIR / filename
    df = pd.read_csv(path)
    oils: Dict[str, OilSpec] = {}
    for _, row in df.iterrows():
        oils[row["oil_id"]] = OilSpec(
            name=str(row["product_name"]),
            sulfated_ash_pct=float(row["sulfated_ash_pct"]),
            density_kg_per_l=float(row["density_kg_per_l"]),
        )
    return oils


def load_fuels_csv(filename: str = "fuels.csv") -> Dict[str, FuelSpec]:
    """
    Wczytuje fuels.csv i zwraca słownik:
    klucz = fuel_id z CSV,
    wartość = FuelSpec.
    """
    path = DATA_DIR / filename
    df = pd.read_csv(path)
    fuels: Dict[str, FuelSpec] = {}
    for _, row in df.iterrows():
        fuels[row["fuel_id"]] = FuelSpec(
            name=str(row["name"]),
            sulfur_ppm=float(row["sulfur_ppm"]),
            density_kg_per_l=float(row["density_kg_per_l"]),
        )
    return fuels
