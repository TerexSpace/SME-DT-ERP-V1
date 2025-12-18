# SME-DT-ERP Development Guide

SimPy-based warehouse digital twin with ERP integration using Ports & Adapters pattern.  
**Target Journal**: EJISDC (Electronic Journal of Information Systems in Developing Countries)
**Manuscript Status**: ~11,000 words, 30 APA references with DOIs, Kazakhstan case study with 12 practitioner interviews

## Architecture

```
core.py (955 LOC)     → Simulation engine, domain models, ERPAdapterPort interface
run_simulation.py     → Batch scenarios, sensitivity analysis → results/*.json, *.csv
tests/test_core.py    → Pytest with fixtures (default_config, digital_twin, sample_order)
paper/                → EJISDC manuscript (ejisdc_digital_twin_erp.tex)
```

**Data Flow**: `ERP → fetch_orders() → order_generator() [Poisson] → order_process() → PICKING → PACKING → SHIPPING → COMPLETED → _record_event() → ERP sync`

**Import pattern** (root-level files):
```python
from core import WarehouseDigitalTwin, SimulationConfig, MockERPAdapter
```

## Critical: SimPy Generator Pattern

**Use `yield`, NOT `async/await`**:
```python
def order_process(self, order: Order):
    with self.workers.request() as req:  # Context manager for resource release
        yield req                          # BLOCK until available
        yield self.env.timeout(pick_time)  # ADVANCE clock
        order.status = OrderStatus.PICKED  # Instant state change
```

## Key Conventions

| Convention | Rule |
|------------|------|
| **Time units** | Simulation in MINUTES; `order_arrival_rate` per HOUR (convert `/60.0`) |
| **Config** | Never mutate directly—use `run_what_if_scenario({'num_workers': 7})` |
| **Order states** | Strict sequence: `RECEIVED → PICKING → PICKED → PACKING → PACKED → SHIPPING → COMPLETED` |
| **Events** | Always `_record_event(EventType.*, {..., 'sim_time': self.env.now})` for ERP sync |
| **Time samples** | Use `max(0.1, np.random.normal(mean, std))` to avoid negative timeouts |
| **Random seeds** | Always `random.seed(config.random_seed)` for reproducibility |

## Paper Guidelines (EJISDC Focus)

| Section | Key Focus |
|---------|-----------|
| **Theory** | ICT4D, Capability Approach (Zheng & Walsham), Design-Reality Gap (Heeks) |
| **Methodology** | DSR (Hevner, Peffers, Gregor) + Practitioner interviews (N=12) + Thematic analysis |
| **References** | APA style, DOIs required, 2020-2025 priority, include Avgerou, Walsham, Sahay |
| **Case Context** | Kazakhstan SMEs, Digital Kazakhstan initiative, Belt & Road logistics |
| **Ethics** | Informed consent for practitioner interviews, anonymized data, synthetic simulation data |

## Commands

```powershell
# Setup
pip install -r requirements.txt

# Run
python core.py                    # Demo (8-hour shift)
python run_simulation.py          # Full analysis → results/

# Test (use 60-min sim time for speed)
pytest tests/test_core.py -v
pytest tests/ -v --cov=. --cov-report=html

# Quality
black . --check; isort . --check-only; flake8 . --max-line-length=120

# Paper figures (run before LaTeX)
cd paper && python generate_figures.py
```

## Adding New Features

**New resource type** (e.g., packing stations):
1. Add `num_packing_stations: int = 3` to `SimulationConfig`
2. Create `self.packing_stations = simpy.Resource(env, capacity=...)` in `_initialize_resources()`
3. Request with context manager: `with self.packing_stations.request() as req: yield req`

**New order stage** (e.g., inspection):
1. Add `INSPECTING = "inspecting"` to `OrderStatus` enum
2. Add timing fields to `Order` dataclass
3. Add config params (`inspect_time_mean`, `inspect_time_std`)
4. Insert `yield` block in `order_process()` workflow

**Custom ERP adapter**: Implement `ERPAdapterPort` abstract methods (`connect`, `disconnect`, `fetch_orders`, `fetch_inventory`, `update_order_status`, `update_inventory`, `subscribe_to_events`)
