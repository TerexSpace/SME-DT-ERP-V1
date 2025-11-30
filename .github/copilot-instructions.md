# SME-DT-ERP Development Guide

## Project Overview

**Repository**: https://github.com/TerexSpace/SME-DT-ERP-V1  
**Author**: Almas Ospanov (a.ospanov@astanait.edu.kz)  
**Institution**: Astana IT University, School of Software Engineering  
**License**: Research-Only (Academic and educational use only)  
**DOI**: 10.5281/zenodo.17738548  
**Status**: Submitted to JUCS (Journal of Universal Computer Science)

## Architecture

**SimPy discrete-event simulation** framework for warehouse digital twins with ERP integration using **Ports & Adapters** pattern.

### Project Structure
```
SME-DT-ERP-V1/
├── core.py                    # Main simulation engine and domain models
├── run_simulation.py          # Batch runner for scenarios & sensitivity analysis
├── setup.py                   # Package configuration
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container configuration
├── docker-compose.yml         # Multi-service orchestration
├── tests/
│   ├── __init__.py
│   └── test_core.py          # Unit & integration tests (pytest)
├── paper/
│   ├── jucs_digital_twin_erp.tex  # JUCS LaTeX manuscript
│   ├── jucs_references.bib        # Bibliography
│   ├── jucs2e.sty                 # JUCS journal style file
│   ├── generate_figures.py        # Script to generate figures
│   ├── paper.md                   # Original JOSS paper (archived)
│   ├── paper.bib                  # Original bibliography (archived)
│   └── figures/                   # Generated figures directory
│       ├── figure1_architecture.png
│       ├── figure2_scalability.png
│       ├── figure3_cost.png
│       └── figure4_outcomes.png
├── results/                  # Simulation outputs (JSON, CSV)
└── .github/
    └── workflows/
        ├── ci.yml            # CI/CD pipeline (tests, linting, Docker)
        └── draft-pdf.yml     # JOSS paper compilation
```

**Import pattern**: Since files are in root, import directly:
```python
from core import WarehouseDigitalTwin, SimulationConfig, MockERPAdapter
# NOT: from sme_dt_erp.core import ...
```

### Core Files
- `core.py` (955 LOC): Simulation engine (`WarehouseDigitalTwin`), domain models, `ERPAdapterPort` interface, `MockERPAdapter`
- `run_simulation.py` (383 LOC): Batch scenario runner with what-if analysis and sensitivity sweeps
- `tests/test_core.py` (680 LOC): Pytest suite with fixtures (`default_config`, `mock_erp_adapter`, `digital_twin`, `sample_order`)
- `paper/jucs_digital_twin_erp.tex`: JUCS journal manuscript (modular microservices architecture for SME digital twins)
- `paper/generate_figures.py`: Automated figure generation for paper (architecture, scalability, cost, outcomes)
- `setup.py`: Package configuration for pip installation
- `requirements.txt`: Dependencies (simpy, numpy, pandas, matplotlib, pytest, etc.)

### Data Flow
```
ERP → fetch_orders() → order_generator() [Poisson arrival] → order_process() per order
                                                                    ↓
                                              PICKING → PACKING → SHIPPING → COMPLETED
                                                                    ↓
                                              _record_event() → event_buffer → ERP sync
```

## Critical: SimPy Generator Pattern

**SimPy uses `yield`, NOT `async/await`**. Every time-passing operation requires `yield`:

```python
def order_process(self, order: Order):
    with self.workers.request() as req:
        yield req  # BLOCK until resource available
        yield self.env.timeout(pick_time)  # ADVANCE simulation clock
        order.status = OrderStatus.PICKED  # Instant state change
```

Always use context managers for resources to guarantee release.

## Key Conventions

### Time Units
- **All simulation times in MINUTES** (not seconds/hours)
- `order_arrival_rate`: Per HOUR, converted via `/60.0` internally
- `erp_sync_interval`: Exception - in SECONDS

### Configuration Immutability
Never mutate config during simulation. Use `run_what_if_scenario()` which saves/restores:
```python
results = dt.run_what_if_scenario({'num_workers': 7})  # Isolated scenario
```

### Order State Machine (strict sequence)
`RECEIVED → PICKING → PICKED → PACKING → PACKED → SHIPPING → COMPLETED`

Use enums: `order.status = OrderStatus.PICKING` (not strings)

### Event Recording
Record all state changes for ERP sync and calibration:
```python
self._record_event(EventType.ORDER_STATUS_CHANGED, {
    'order_id': order.order_id,
    'status': OrderStatus.COMPLETED.value,  # Use .value for enums
    'sim_time': self.env.now
})
```

## Development Commands

```powershell
# Setup (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
# OR install in development mode with test dependencies:
pip install -e ".[dev]"

# Run simulations
python core.py                    # Quick demo (8-hour shift)
python run_simulation.py          # Full suite → results/*.json, results/*.csv

# Tests (use 60-min sim time for speed)
pytest tests/test_core.py -v
pytest tests/test_core.py::TestWarehouseDigitalTwin -v  # Single class
pytest tests/ -v --cov=sme_dt_erp --cov-report=html     # With coverage

# Code quality
black . --check                   # Auto-format check
isort . --check-only              # Sort imports check
flake8 . --max-line-length=120    # Linting (allow 120 char lines)
mypy core.py                      # Type checking

# Docker
docker build -t sme-dt-erp:latest .
docker run --rm -v ${PWD}/results:/app/results sme-dt-erp:latest python run_simulation.py

# JUCS paper compilation (requires LaTeX with XeLaTeX)
cd paper
xelatex jucs_digital_twin_erp.tex
bibtex jucs_digital_twin_erp
xelatex jucs_digital_twin_erp.tex
xelatex jucs_digital_twin_erp.tex

# Generate figures (must run before LaTeX compilation)
python generate_figures.py
```

## Figure Generation for JUCS Paper

The `paper/generate_figures.py` script automatically generates all figures required for the JUCS manuscript:

### Figures Generated

1. **Figure 1 - Architecture Diagram** (`figure1_architecture.png`)
   - Shows Digital Twin Runtime with 6 layers
   - IoT integration: sensors, GPS trackers, RFID tags
   - Microservices components: inventory, order fulfillment, predictive maintenance, supply chain
   - Data flows with color-coded arrows
   - Resolution: 300 DPI for publication quality

2. **Figure 2 - Scalability Analysis** (`figure2_scalability.png`)
   - Line chart: response latency vs. order arrival rate
   - Compares monolithic vs. microservices architectures
   - Highlights saturation point at 12 orders/hour for monolithic
   - Shows microservices maintains <1s latency up to 18 orders/hour

3. **Figure 3 - Cost-Benefit Analysis** (`figure3_cost.png`)
   - Dual subplot: TCO over 36 months + cost breakdown
   - Demonstrates 37% cost reduction
   - Categories: infrastructure, licenses, maintenance, development, operations
   - Shaded area shows cumulative savings ($43K over 3 years)

4. **Figure 4 - Operational Outcomes** (`figure4_outcomes.png`)
   - Bar chart + horizontal improvement percentages
   - Key metrics: 31% faster fulfillment, 76% fewer stockouts
   - 42% better resource utilization, 28% higher throughput
   - Color-coded by metric type

### Customizing Figures

To modify figures, edit `paper/generate_figures.py`:
- **Colors**: Update color scheme in each function (e.g., `color_iot`, `color_dt`)
- **Data**: Modify arrays for scalability/cost data to reflect updated simulations
- **Layout**: Adjust `figsize`, fonts, or positions of components
- **Resolution**: Change `dpi=300` parameter in `savefig()` calls

```python
# Example: Update scalability data
arrival_rates = np.array([5, 7, 9, 11, 13, 15, 17, 19, 21])
latency_microservices = np.array([0.12, 0.16, 0.21, 0.27, 0.35, 0.45, 0.58, 0.75, 0.98])
```

## CI/CD Pipeline

**GitHub Actions** runs automatically on push/PR to `main`:
- `.github/workflows/ci.yml`: Tests (Python 3.9-3.12), linting, coverage, Docker build
- `.github/workflows/draft-pdf.yml`: JOSS paper PDF compilation (triggered on `paper/**` changes)

**Test matrix**: Ubuntu + Python 3.9, 3.10, 3.11, 3.12  
**Coverage target**: 80%+ (current: tracked via Codecov)

## Test Fixtures

Available fixtures in all test methods via parameters:

```python
@pytest.fixture
def default_config():
    """Short simulation for testing - 60 minutes (not 480)."""
    return SimulationConfig(
        simulation_time=60.0,  # 1 hour for speed
        random_seed=42,
        num_storage_locations=20,
        num_workers=3,
        num_forklifts=1,
        order_arrival_rate=5.0
    )

@pytest.fixture
def sample_order():
    """Order with 2 SKUs, 5 total items."""
    return Order(
        order_id="TEST-001",
        customer_id="CUST-001",
        lines=[
            OrderLine(sku="SKU-0001", quantity=2, location="A-01-01"),
            OrderLine(sku="SKU-0002", quantity=3, location="A-02-02")
        ],
        priority=3
    )

# Use in tests:
def test_example(default_config, mock_erp_adapter, digital_twin, sample_order):
    assert digital_twin.config.simulation_time == 60.0
```

## Calibration Algorithm Internals

**Purpose**: Automatically estimate simulation parameters from historical ERP transaction logs.

### Algorithm Implementation (lines 718-810 in core.py)

1. **Event Parsing**: Correlate events per order
   ```python
   order_starts[order_id] = event.timestamp  # ORDER_CREATED
   order_picks[order_id] = event.timestamp   # Status → PICKED
   order_packs[order_id] = event.timestamp   # Status → PACKED
   ```

2. **Duration Calculation**: Compute phase durations in minutes
   ```python
   pick_time = (picked_timestamp - created_timestamp).total_seconds() / 60
   pack_time = (packed_timestamp - picked_timestamp).total_seconds() / 60
   ```

3. **Parameter Estimation**: Use sample statistics
   ```python
   calibrated['pick_time_mean'] = statistics.mean(pick_times)
   calibrated['pick_time_std'] = statistics.stdev(pick_times) if len(pick_times) > 1 else 0.5
   ```

4. **Auto-Apply**: Update `SimulationConfig` with calibrated values
   ```python
   for key, value in calibrated.items():
       if hasattr(self.config, key):
           setattr(self.config, key, value)
   ```

### Usage Example

```python
# Generate synthetic ERP events
erp_events = []
base_time = datetime.now()

for i in range(50):
    order_id = f"TEST-{i:04d}"
    
    # Order created
    erp_events.append(WarehouseEvent(
        event_id=f"EV-{len(erp_events):04d}",
        event_type=EventType.ORDER_CREATED,
        timestamp=base_time,
        data={'order_id': order_id}
    ))
    
    # Picked (2-5 minutes later)
    pick_duration = random.gauss(3.0, 0.8)
    picked_time = base_time + timedelta(minutes=pick_duration)
    erp_events.append(WarehouseEvent(
        event_id=f"EV-{len(erp_events):04d}",
        event_type=EventType.ORDER_STATUS_CHANGED,
        timestamp=picked_time,
        data={'order_id': order_id, 'new_status': OrderStatus.PICKED.value}
    ))

# Calibrate
dt = WarehouseDigitalTwin(config, erp_adapter)
calibrated_params = dt.calibrate_from_erp_logs(erp_events)
# Result: {'pick_time_mean': 2.87, 'pick_time_std': 0.64, ...}
```

### Drift Detection
Monitors divergence between DT and ERP inventory (lines 813-835):

```python
drift = calculate_sync_drift()  # Returns 0.0-1.0
if drift > config.sync_threshold:  # Default 0.05 (5%)
    self._record_event(EventType.CALIBRATION_TRIGGER, {'drift': drift})
```

## Sensitivity Analysis

**Purpose**: Understand how input parameters affect outputs (throughput, cycle time, utilization).

### Implementation in `run_simulation.py` (lines 193-243)

```python
def run_sensitivity_analysis(base_config: SimulationConfig) -> List[Dict[str, Any]]:
    results = []
    
    # Worker sensitivity (3-10)
    for num_workers in range(3, 11):
        erp_adapter = MockERPAdapter(base_config)
        erp_adapter.connect()
        dt = WarehouseDigitalTwin(base_config, erp_adapter)
        scenario_result = dt.run_what_if_scenario({'num_workers': num_workers})
        
        results.append({
            'parameter': 'num_workers',
            'value': num_workers,
            'throughput': scenario_result['results']['metrics']['throughput_orders_per_hour'],
            'avg_order_time': scenario_result['results']['metrics']['avg_order_time'],
            'orders_completed': scenario_result['results']['orders_completed']
        })
        erp_adapter.disconnect()
    
    # Forklift sensitivity (1-5)
    for num_forklifts in range(1, 6):
        # Similar pattern...
    
    # Demand rate sensitivity (5-20 orders/hour)
    for arrival_rate in range(5, 21, 3):
        # Similar pattern...
    
    return results
```

### Running & Visualization

```powershell
# Run analysis
python run_simulation.py
# Output: results/sensitivity_analysis_<timestamp>.csv

# Visualize (external tool)
python -c "
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('results/sensitivity_analysis_20251126.csv')
worker_data = df[df['parameter'] == 'num_workers']

plt.plot(worker_data['value'], worker_data['throughput'])
plt.xlabel('Number of Workers')
plt.ylabel('Throughput (orders/hour)')
plt.savefig('worker_sensitivity.png')
"
```

### Interpreting Results
- **Linear scaling**: Output ∝ input (2x workers → 2x throughput)
- **Diminishing returns**: Output increase slows (beyond bottleneck)
- **Saturation**: No improvement beyond certain point

## Code Modification Patterns

### Adding a New Resource Type

**Example**: Add "packing stations" as limited resource

```python
# 1. Add to SimulationConfig
@dataclass
class SimulationConfig:
    # ... existing fields ...
    num_packing_stations: int = 3  # NEW

# 2. Initialize in WarehouseDigitalTwin.__init__
self.packing_stations = None  # NEW

# 3. Create SimPy resource in _initialize_resources()
def _initialize_resources(self):
    if self.env:
        self.workers = simpy.Resource(self.env, capacity=self.config.num_workers)
        self.forklifts = simpy.Resource(self.env, capacity=self.config.num_forklifts)
        self.packing_stations = simpy.Resource(self.env, capacity=self.config.num_packing_stations)  # NEW

# 4. Request resource in order_process()
def order_process(self, order: Order):
    # ... picking phase ...
    
    # PACKING PHASE with station
    order.status = OrderStatus.PACKING
    with self.packing_stations.request() as station_req:  # NEW
        with self.workers.request() as worker_req:
            yield station_req  # NEW
            yield worker_req
            pack_time = self._sample_time(...)
            yield self.env.timeout(pack_time)
```

### Adding a New Order Processing Stage

**Example**: Add "quality inspection" after packing

```python
# 1. Add status to OrderStatus enum
class OrderStatus(Enum):
    # ... existing statuses ...
    INSPECTING = "inspecting"  # NEW
    INSPECTED = "inspected"    # NEW

# 2. Add timing fields to Order dataclass
@dataclass
class Order:
    # ... existing fields ...
    inspect_start_time: Optional[float] = None  # NEW
    inspect_end_time: Optional[float] = None    # NEW

# 3. Add config parameters
@dataclass
class SimulationConfig:
    # ... existing fields ...
    inspect_time_mean: float = 1.5  # NEW
    inspect_time_std: float = 0.3   # NEW

# 4. Insert stage in order_process() workflow
def order_process(self, order: Order):
    # ... picking phase ...
    # ... packing phase ...
    
    # INSPECTION PHASE
    order.status = OrderStatus.INSPECTING  # NEW
    order.inspect_start_time = self.env.now
    
    with self.workers.request() as worker_req:
        yield worker_req
        inspect_time = self._sample_time(
            self.config.inspect_time_mean,
            self.config.inspect_time_std
        )
        yield self.env.timeout(inspect_time)
    
    order.status = OrderStatus.INSPECTED
    order.inspect_end_time = self.env.now
    
    # ... shipping phase ...
```

## Creating Custom ERP Adapters

**Example**: Odoo ERP adapter using XML-RPC

```python
import xmlrpc.client

class OdooERPAdapter(ERPAdapterPort):
    """Odoo ERP adapter using XML-RPC API."""
    
    def __init__(self, config: SimulationConfig, url: str, db: str, username: str, password: str):
        self.config = config
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.models = None
        self.connected = False
    
    def connect(self) -> bool:
        """Authenticate with Odoo."""
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            self.connected = True
            logger.info(f"Connected to Odoo at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Odoo connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        self.connected = False
    
    def fetch_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """Fetch orders from Odoo sale.order model."""
        if not self.connected:
            return []
        
        # Build domain filter
        domain = []
        if status:
            domain.append(('state', '=', self._map_status_to_odoo(status)))
        
        # Query Odoo
        order_ids = self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'search', [domain]
        )
        
        orders_data = self.models.execute_kw(
            self.db, self.uid, self.password,
            'sale.order', 'read', [order_ids],
            {'fields': ['name', 'partner_id', 'order_line']}
        )
        
        # Convert to Order objects
        orders = []
        for odoo_order in orders_data:
            lines = self._fetch_order_lines(odoo_order['order_line'])
            order = Order(
                order_id=odoo_order['name'],
                customer_id=str(odoo_order['partner_id'][0]),
                lines=lines
            )
            orders.append(order)
        
        return orders
    
    def _map_status_to_odoo(self, status: OrderStatus) -> str:
        """Map internal status to Odoo state."""
        return {
            OrderStatus.RECEIVED: 'sale',
            OrderStatus.PICKING: 'picking',
            OrderStatus.COMPLETED: 'done'
        }.get(status, 'draft')
    
    # Implement other abstract methods: fetch_inventory(), update_order_status(), etc.
```

## JUCS Submission Status

**Current Status**: Submitted to JUCS (Journal of Universal Computer Science)  
**DOI**: 10.5281/zenodo.17738548  
**Repository**: https://github.com/TerexSpace/SME-DT-ERP-V1  
**Paper**: `paper/jucs_digital_twin_erp.tex`  
**Focus**: Implementation of Digital Twins in ERP Systems for SMEs using Modular Microservices Architecture

### Paper Preparation Workflow

**Prerequisites**

1. **Get ORCID identifier**: Register at https://orcid.org/ (Already completed: 0009-0004-3834-130X)
2. **LaTeX environment**: XeLaTeX with required packages (fontspec, graphicx, etc.)
3. **Python environment**: For figure generation (matplotlib, numpy)

### Step 1: Generate Figures

```powershell
# Navigate to paper directory
cd paper

# Generate all figures (4 PNG files in figures/ directory)
python generate_figures.py

# Verify figures created
ls figures/
# Should show: figure1_architecture.png, figure2_scalability.png, 
#              figure3_cost.png, figure4_outcomes.png
```

### Step 2: Compile LaTeX Manuscript

```powershell
# Compile with XeLaTeX (required for fontspec/Times New Roman)
xelatex jucs_digital_twin_erp.tex

# Generate bibliography
bibtex jucs_digital_twin_erp

# Recompile for references (2 passes)
xelatex jucs_digital_twin_erp.tex
xelatex jucs_digital_twin_erp.tex

# Output: jucs_digital_twin_erp.pdf
```

**Common LaTeX Issues:**
- **Missing fonts**: Install Times New Roman or use `\setmainfont{TeX Gyre Termes}` as fallback
- **Missing packages**: Install via `tlmgr install <package>` or use full TeX Live distribution
- **Figure paths**: Ensure `\graphicspath{{./figures/}}` matches actual directory structure

### Step 3: Submit to JUCS

1. Go to https://www.jucs.org/ujs/jucs/submission
2. Create author account if needed
3. Follow submission wizard:
   - Upload PDF manuscript
   - Enter metadata (title, abstract, keywords)
   - Provide author details (ORCID, affiliation)
   - Suggest reviewers (optional)
4. Submit supplementary materials:
   - LaTeX source files (.tex, .bib, .sty)
   - Figures (PNG, high resolution 300 DPI)
   - Code repository link: https://github.com/TerexSpace/SME-DT-ERP-V1

### Step 4: Respond to Review

JUCS uses double-blind peer review. Typical timeline:
- Initial review: 4-8 weeks
- Major revisions: 2-4 weeks for author response
- Minor revisions: 1-2 weeks
- Final decision: 1-2 weeks after final revision

**Revision workflow:**
1. Address each reviewer comment in a response letter
2. Update LaTeX source with tracked changes (use `\usepackage{changes}`)
3. Regenerate figures if methodology changes
4. Recompile PDF and submit revision package

## Common Pitfalls & Solutions

### 1. SimPy vs. Async/Await Confusion
**Problem**: Using `async/await` syntax instead of `yield`

```python
# ❌ WRONG - async/await doesn't work with SimPy
async def order_process(self, order):
    await self.workers.request()
    await asyncio.sleep(pick_time)

# ✅ CORRECT - use generator with yield
def order_process(self, order):
    with self.workers.request() as req:
        yield req
        yield self.env.timeout(pick_time)
```

**Why**: SimPy uses **generator-based coroutines** (pre-Python 3.5 style), not native async/await.

### 2. Time Unit Conversions
**Problem**: Mixing time units causes incorrect inter-arrival times

```python
# ❌ WRONG - treats per-hour rate as per-minute
arrival_rate = self.config.order_arrival_rate  # 10.0/hr
inter_arrival = np.random.exponential(1.0 / arrival_rate)  # Wrong scale!

# ✅ CORRECT - convert to per-minute first
arrival_rate = self.config.order_arrival_rate / 60.0  # 10.0/60 = 0.167/min
inter_arrival = np.random.exponential(1.0 / arrival_rate)
```

**Why**: Config stores arrival rate per **hour**, but simulation clock is in **minutes**.

### 3. Resource Leak Without Context Managers
**Problem**: Manual request/release can leak resources on exceptions

```python
# ❌ WRONG - resource may not release if exception occurs
worker_req = self.workers.request()
yield worker_req
# ... work ...
self.workers.release(worker_req)  # May never execute

# ✅ CORRECT - context manager guarantees release
with self.workers.request() as worker_req:
    yield worker_req
    # ... work ...
# Auto-released here, even on exception
```

**Why**: Context managers ensure `__exit__` runs even with exceptions.

### 4. Config Mutation Between Scenarios
**Problem**: Modifying config in-place affects subsequent runs

```python
# ❌ WRONG - mutates global config
self.config.num_workers = 7
results1 = self.run_simulation()
self.config.num_workers = 5  # Hard to track state

# ✅ CORRECT - use run_what_if_scenario()
results1 = self.run_what_if_scenario({'num_workers': 7})
results2 = self.run_what_if_scenario({'num_workers': 5})
# Each scenario saves/restores config
```

**Why**: `run_what_if_scenario()` saves original config and restores after scenario.

### 5. Forgetting to Record Events
**Problem**: State changes without event recording break calibration

```python
# ❌ WRONG - invisible to ERP sync and calibration
self.inventory[sku].quantity -= line.quantity

# ✅ CORRECT - always record inventory changes
self.inventory[sku].quantity -= line.quantity
self._record_event(EventType.INVENTORY_UPDATED, {
    'sku': sku,
    'change': -line.quantity,
    'sim_time': self.env.now
})
```

**Why**: Events are used for ERP sync and calibration algorithm input.

### 6. Not Seeding Random Number Generators
**Problem**: Non-reproducible simulations make debugging impossible

```python
# ❌ WRONG - different results every run
random.seed()  # Seeds with system time
np.random.seed()

# ✅ CORRECT - use config seed for reproducibility
random.seed(self.config.random_seed)
np.random.seed(self.config.random_seed)
```

**Why**: Reproducibility is critical for debugging and what-if comparisons.

### 7. Negative Time Samples
**Problem**: Normal distribution can produce negative durations

```python
# ❌ WRONG - can return negative time
pick_time = np.random.normal(mean, std)
yield self.env.timeout(pick_time)  # CRASH if negative!

# ✅ CORRECT - truncate to minimum positive value
pick_time = max(0.1, np.random.normal(mean, std))
yield self.env.timeout(pick_time)
```

**Why**: SimPy `timeout()` requires positive values. Use `max(0.1, ...)` truncation.

### 8. Testing with Production Time Scales
**Problem**: 8-hour simulations make tests slow

```python
# ❌ WRONG - tests take too long
@pytest.fixture
def default_config():
    return SimulationConfig(simulation_time=480.0)  # 8 hours

# ✅ CORRECT - use short test duration
@pytest.fixture
def default_config():
    return SimulationConfig(simulation_time=60.0)  # 1 hour for tests
```

**Why**: Tests should run in seconds, not minutes. Use 60-minute sim time (8x speedup).
