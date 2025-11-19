# DPFCALC – Diesel Particulate Filter Clogging Model

DPFCALC is a physics- and chemistry-inspired model of diesel particulate filter (DPF) clogging.

The project combines:
- a **driving-profile-based soot/ash model** (relative DPF fill level vs mileage),
- a **chemical ash calculator (RDPF)** based on:
  - engine oil technical data (sulfated ash %, density),
  - fuel sulfur content (ppm) and density,
  - user-reported mileage, oil consumption and fuel consumption.

The goal is to show how workshop/domain knowledge (automotive + lubrication + fuel chemistry)
can be turned into a reproducible, parameterized Python model suitable for:
- predictive maintenance,
- “what-if” simulations,
- integration into diagnostic tools,
- data / AI portfolio projects.

---

## Features

### 1. Driving-profile DPF model (soot + ash, relative units)

Implemented in `src/dpf_model.py`:

- `DPFInputs` / `DPFParams` / `DPFState` dataclasses:
  - explicit configuration of driving profile and model parameters,
- `predict_dpf_state(...)`:
  - point prediction of soot/ash load and relative fill level,
- `simulate_vehicle_lifecycle(...)`:
  - generates a full mileage curve, ideal for plotting and scenario comparisons.

The model uses:
- mileage,
- average speed,
- city driving ratio,
- oil ash content,
- fuel sulfur ppm,

to produce a **relative DPF fill level**. This is used mainly for visual analysis in the notebook
e.g. city-heavy vs mixed driving).

Example usage is shown in the notebook:
- `notebooks/01_dpf_model_demo.ipynb`

---

### 2. Chemical DPF ash calculator (RDPF)

Also in `src/dpf_model.py`:

- `OilSpec` – oil technical data:
  - `sulfated_ash_pct` (SAPS) from technical data sheet,
  - `density_kg_per_l`,
- `FuelSpec` – fuel data:
  - `sulfur_ppm`,
  - `density_kg_per_l`,
- `UsageProfile` – user input:
  - mileage from new DPF / last cleaning,
  - oil consumption (l/1000 km),
  - fuel consumption (l/100 km).

Core functions:

- `calc_oil_ash_mass_g(profile, oil)`  
  → grams of ash coming from burned engine oil.

- `calc_fuel_ash_mass_g(profile, fuel, sulfur_to_ash_factor=3.0)`  
  → grams of ash from sulfur in the diesel fuel
    (simple model: 1 g S → ~3 g sulfate ash, configurable).

- `calc_dpf_ash_fill(profile, oil, fuel, dpf_capacity_ash_g=1100.0, sulfur_to_ash_factor=3.0)`  
  → combined result:
  - oil-derived ash [g],
  - fuel-derived ash [g],
  - total ash in DPF [g],
  - assumed DPF ash capacity [g],
  - relative fill (0–1),
  - fill in percent.

This is the **RDPF calculator**: user inputs mileage and consumptions, selects oil and fuel type, and the model
returns how many grams of ash are estimated to sit in the DPF and what percentage of the assumed capacity that is.

---

### 3. CSV-based oil and fuel database

Data is stored in CSV files under `data/`:

- `data/oils.csv` – example engine oil specs (generic ACEA classes and one OEM-like entry):
  - `oil_id`
  - `brand`
  - `product_name`
  - `acea_class`
  - `viscosity_grade`
  - `sulfated_ash_pct`
  - `phosphorus_pct`
  - `sulfur_pct`
  - `density_kg_per_l`
  - `base_oil_type`
  - `notes`

- `data/fuels.csv` – example fuel specs:
  - `fuel_id`
  - `region`
  - `name`
  - `standard`
  - `sulfur_ppm`
  - `density_kg_per_l`
  - `notes`

Loaders in `src/dpf_model.py`:

- `load_oils_csv(filename: str = "oils.csv") -> Dict[str, OilSpec]`
- `load_fuels_csv(filename: str = "fuels.csv") -> Dict[str, FuelSpec]`

These functions return dictionaries keyed by `oil_id` / `fuel_id`, which are then used in the notebook and in any potential frontend / API.

---

## Project structure

```text
DPFCALC/
├─ src/
│  ├─ __init__.py
│  ├─ dpf_model.py        # core models: driving-based DPF model + chemical ash calculator
├─ notebooks/
│  ├─ 01_dpf_model_demo.ipynb   # main demo: plots + RDPF example
├─ data/
│  ├─ oils.csv             # example oil technical data
│  ├─ fuels.csv            # example fuel data (sulfur, density)
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## Installation & setup

Clone the repository and set up a virtual environment:

```bash
python -m venv .venv
```

Activate it:

* Windows (CMD):

  ```bash
  .venv\Scripts\activate.bat
  ```

* PowerShell (if execution policy allows):

  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```

* Linux/macOS:

  ```bash
  source .venv/bin/activate
  ```

Install dependencies:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not yet generated:

```bash
pip install numpy pandas matplotlib jupyter
pip freeze > requirements.txt
```

---

## Running the demo notebook

Start Jupyter:

```bash
python -m notebook
```

In the browser:

1. Navigate to the project folder (`DPFCALC`),
2. Open `notebooks/01_dpf_model_demo.ipynb`,
3. Run all cells (Kernel → Restart & Run All).

The notebook demonstrates:

1. Comparison of DPF relative fill level for:

   * city-heavy driving profile,
   * mixed driving profile,
2. Chemical RDPF ash calculation for a realistic scenario based on CSV data.

---

## Example: Chemical RDPF calculation

Scenario (example from the notebook):

* mileage: **180 000 km**
* oil consumption: **0.3 l / 1000 km**
* fuel consumption: **7.0 l / 100 km**
* oil: `OIL_C3_5W30_GENERIC`

  * ACEA C3 5W-30 Low SAPS
  * sulfated ash: **0.8 %**
  * density: **0.850 kg/l**
* fuel: `FUEL_EURO6_ON`

  * modern European ULSD (EN 590)
  * sulfur: **10 ppm**
  * density: **0.835 kg/l**
* assumed DPF ash capacity: **1100 g**
  (typical ballpark for passenger car DPFs in the ~1000–1200 g range)

The notebook calls:

```python
profile = UsageProfile(
    mileage_km=180_000,
    oil_consumption_l_per_1000km=0.3,
    fuel_consumption_l_per_100km=7.0,
)

result = calc_dpf_ash_fill(
    profile=profile,
    oil=oils["OIL_C3_5W30_GENERIC"],
    fuel=fuels["FUEL_EURO6_ON"],
    dpf_capacity_ash_g=1100.0,
)
```

Example output (values approximate):

```python
{
  "oil_ash_g":   ~367.2,
  "fuel_ash_g":  ~315.6,
  "total_ash_g": ~682.8,
  "dpf_capacity_ash_g": 1100.0,
  "fill_ratio":  ~0.62,
  "fill_percent": ~62.0
}
```

Interpretation:
* Around **367 g** of ash from engine oil (based on sulfated ash % and oil consumption),
* Around **316 g** of ash from fuel sulfur (10 ppm, converted via sulfur → sulfate factor),
* Total **~683 g** ash in the DPF,
* For an assumed ash capacity of 1100 g, that corresponds to **~62% DPF ash fill**.

This is exactly the kind of insight that can be used:
* in a workshop to justify DPF cleaning/replacement,
* in a fleet to estimate when vehicles approach DPF ash saturation,
* or as a backend for a customer-facing DPF health calculator.

---

## Assumptions and limitations

To keep the model focused and transparent, several assumptions are made:

* **DPF ash capacity** is modeled as a single scalar parameter (`dpf_capacity_ash_g`),
  defaulting to **1100 g** as a realistic ballpark (1000–1200 g) for passenger car DPFs.
  In practice, this should be customized per engine / vehicle family using OEM or experimental data.

* The **oil ash model** assumes:

  * sulfated ash % from the oil’s technical data sheet (SAPS),
  * constant density of oil (kg/l),
  * linear relation between consumed oil and ash mass.

* The **fuel ash model** assumes:

  * sulfur ppm from fuel spec / region,
  * constant density of fuel,
  * a configurable sulfur-to-ash factor (default 3.0, i.e. 1 g S → 3 g sulfate ash).

* The model is **linear in mileage**, which:
  * simplifies extrapolation (e.g. estimating mileage to reach a target ash load),
  * does not yet account for non-linear effects (e.g. regeneration behavior, partial ash losses, etc.).

* The project is designed as a **portfolio / R&D demonstration**, not as a certified OEM calculator.
  It shows how domain knowledge (mechanics, oil chemistry, fuel standards) can be formalized and
  implemented in a reproducible data/model pipeline.

---

## Possible future work

Ideas for extending the project:
* Import real-world workshop / fleet data and:
  * calibrate `sulfur_to_ash_factor`,
  * calibrate `dpf_capacity_ash_g` for specific engine families.
* Add a small CLI or web UI (e.g. Streamlit) to let users:
  * select oil and fuel from dropdowns,
  * input their mileage and consumption,
  * see ash mass and DPF fill percentage.
* Extend the soot model to:
  * include regeneration events,
  * integrate with OBD / ECU log data.
* Add a dedicated `dpf_capacity_examples.csv` with approximate capacities for different vehicle classes.

---

This project is intentionally structured like a production-grade data/ML/R&D project:
* Python package in `src/`,
* data in `data/`,
* analysis and visualization in `notebooks/`,
* clear assumptions and limitations documented in this README.
