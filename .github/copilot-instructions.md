# SME-DT-ERP Development Guide

## Architecture Overview

This is a **discrete-event simulation (DES) framework** for warehouse digital twins with ERP integration. The architecture follows **Ports & Adapters (Hexagonal)** pattern to isolate domain logic from infrastructure concerns.

### Design Philosophy

- **Monolithic core by design**: All simulation logic in single `core.py` (955 LOC) for simplicity and atomic deployments
- **SimPy generator-based coroutines**: NOT async/await - uses `yield` for time-passing operations
- **ERP as external adapter**: Domain logic independent of any specific ERP system
- **Immutable configuration**: Create new `SimulationConfig` instances for what-if scenarios, never mutate in-place

### Core Components

**`core.py`** (955 lines) - Simulation engine & domain models:
- `SimulationConfig`: Frozen simulation parameters (timing, resources, sync thresholds)
- `WarehouseDigitalTwin`: Main DES engine orchestrating SimPy processes
- `ERPAdapterPort`: Abstract base (port) defining 6 required ERP operations
- `MockERPAdapter`: Reference implementation for testing (no real ERP)
- `DigitalTwinMetrics`: Statistical aggregation (throughput, cycle times, queue depths)

**`run_simulation.py`** (383 lines) - Batch scenario runner:
- Baseline simulation with default parameters
- 7 predefined what-if scenarios (worker count, demand spikes, picking efficiency)
- Sensitivity analysis (parameter sweeps on workers, forklifts, arrival rates)
- Calibration test with synthetic ERP event logs
- CSV/JSON export for plotting and analysis

**`tests/test_core.py`** (680 lines) - Pytest suite:
- Fixtures: `default_config`, `mock_erp_adapter`, `digital_twin`, `sample_order`
- Test classes mirroring module structure (TestSimulationConfig, TestWarehouseDigitalTwin, etc.)
- Shortened 60-minute simulations (vs. 480 production) for speed

### Data Flow Architecture

```
ERP System → fetch_orders() → orders_queue (deque)
                    ↓
         order_generator() SimPy process
                    ↓
         Poisson arrival (exponential inter-arrival)
                    ↓
         order_process() SimPy process per order
                    ↓
    ┌───────────────┼───────────────┐
    │               │               │
PICKING         PACKING        SHIPPING
(workers +    (workers only)   (handoff)
forklifts)
    │               │               │
    └───────────────┼───────────────┘
                    ↓
         Metrics aggregation + event recording
                    ↓
         update_order_status() → ERP System
```

**State Transitions** (enforced by `order_process()`):
RECEIVED → PICKING → PICKED → PACKING → PACKED → SHIPPING → COMPLETED

**Event Recording**: Every state change creates `WarehouseEvent` in `event_buffer` (deque, maxlen=1000) for:
- ERP synchronization via `update_order_status()`
- Calibration algorithm input (timing extraction)
- Drift detection between DT and ERP inventory

## Key Patterns

### SimPy Process Pattern (Generator-Based Coroutines)

**CRITICAL**: SimPy uses generator functions with `yield`, NOT `async`/`await`. Every time-passing operation requires `yield`:

```python
def order_process(self, order: Order):
    """SimPy process (generator function)."""
    with self.workers.request() as worker_req:
        yield worker_req  # BLOCK until resource available
        
        pick_time = self._sample_time(self.config.pick_time_mean, self.config.pick_time_std)
        yield self.env.timeout(pick_time)  # ADVANCE simulation clock
        
        # Do work (instant in sim time)
        order.status = OrderStatus.PICKED
```

**Resource Pattern**: Always use context managers to guarantee release:
```python
with self.workers.request() as req:
    yield req
    # Resource auto-released on exit
```

**Process Registration**: Start processes with `self.env.process(generator_func())`:
```python
self.env.process(self.order_generator())  # Adds to event queue
self.env.run(until=480.0)  # Run until 480 minutes
```

### Time Sampling with Stochasticity

Use `_sample_time(mean, std)` for all durations to inject realistic variance:

```python
def _sample_time(self, mean: float, std: float) -> float:
    """Truncated normal distribution (min 0.1 to avoid negative times)."""
    if NUMPY_AVAILABLE:
        return max(0.1, np.random.normal(mean, std))
    return max(0.1, random.gauss(mean, std))
```

**Scaling with Quantity**: Time increases sublinearly with item count:
```python
pick_time = self._sample_time(
    self.config.pick_time_mean * line.quantity,
    self.config.pick_time_std * (line.quantity ** 0.5)  # √n scaling
)
```

### Configuration Immutability Pattern

**NEVER mutate config during simulation**. Create new instances for scenarios:

```python
# ❌ WRONG - mutates shared state
self.config.num_workers = 7
self.run_simulation()

# ✅ CORRECT - creates isolated scenario
def run_what_if_scenario(self, scenario_params: Dict[str, Any]):
    original_config = self.config.to_dict()
    
    # Apply overrides
    for key, value in scenario_params.items():
        setattr(self.config, key, value)
    
    # Reset resources with new config
    self._initialize_resources()
    self.metrics = DigitalTwinMetrics()
    
    # Run scenario
    results = self.run_simulation()
    
    # RESTORE original state
    self.config = SimulationConfig.from_dict(original_config)
    self._initialize_resources()
    
    return results
```

### Event Recording for Calibration

Record ALL state changes with `_record_event()` for ERP sync and parameter estimation:

```python
self._record_event(EventType.ORDER_STATUS_CHANGED, {
    'order_id': order.order_id,
    'status': OrderStatus.COMPLETED.value,
    'total_time': self.env.now - order_start,
    'sim_time': self.env.now  # Current simulation clock
})
```

**Event Types**: Use enum, not strings:
- `ORDER_CREATED`, `ORDER_STATUS_CHANGED`
- `INVENTORY_UPDATED` (with `change` delta)
- `WORKER_ASSIGNED`, `WORKER_RELEASED`
- `CALIBRATION_TRIGGER` (drift exceeds threshold)


## Development Workflows

### Environment Setup

```powershell
# Create isolated virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install with development dependencies
pip install -e ".[dev]"

# Verify SimPy availability (MANDATORY)
python -c "import simpy; print(f'SimPy {simpy.__version__}')"
```

### Running Simulations

```powershell
# Quick demo - baseline + single what-if (7 workers)
python core.py
# Output: Console metrics for baseline vs. scenario

# Full scenario suite - 7 what-if + sensitivity analysis
python run_simulation.py
# Output: results/simulation_results_<timestamp>.json
#         results/sensitivity_analysis_<timestamp>.csv

# Run simulation programmatically
python -c "from core import *; c=SimulationConfig(); dt=WarehouseDigitalTwin(c, MockERPAdapter(c)); dt.erp_adapter.connect(); print(dt.run_simulation()['metrics'])"
```

**Result Locations**:
- JSON: Nested dict with config, metrics, inventory snapshot
- CSV: Tabular format for plotting (parameter, value, throughput, avg_time)

### Testing Workflow

```powershell
# All tests with verbose output
pytest tests/test_core.py -v

# With coverage report (HTML in htmlcov/)
pytest tests/test_core.py -v --cov=sme_dt_erp --cov-report=html

# Single test class (fast)
pytest tests/test_core.py::TestWarehouseDigitalTwin -v

# Single test method
pytest tests/test_core.py::TestSimulationConfig::test_to_dict -v

# Run only fast tests (skip long simulations)
pytest tests/test_core.py -v -m "not slow"
```

**Test Fixtures Pattern**:
```python
# Available in all test methods via parameters
def test_example(default_config, mock_erp_adapter, digital_twin, sample_order):
    # default_config: SimulationConfig(simulation_time=60.0)
    # mock_erp_adapter: Connected MockERPAdapter
    # digital_twin: Initialized WarehouseDigitalTwin
    # sample_order: Order with 2 SKUs (5 total items)
    assert digital_twin.config.simulation_time == 60.0
```

**Test Time Scaling**: Tests use `simulation_time=60.0` (1 hour) instead of production `480.0` (8 hours) for 8x speedup.

### Docker Workflow

```powershell
# Build image
docker build -t sme-dt-erp:latest .

# Run single simulation (outputs to stdout)
docker run --rm sme-dt-erp:latest

# Run with persistent results volume
docker run --rm -v ${PWD}/results:/app/results sme-dt-erp:latest python run_simulation.py

# Multi-service stack (web UI + database + simulation)
docker-compose up -d
docker-compose logs -f simulation
```

### Code Quality Checks

```powershell
# Format code (modifies in-place)
black core.py run_simulation.py tests/

# Lint (reports issues)
flake8 core.py run_simulation.py --max-line-length=120

# Type checking
mypy core.py --ignore-missing-imports
```


## Project-Specific Conventions

### Configuration Management
- **Immutable dataclass**: `SimulationConfig` uses `@dataclass` (not frozen but treat as immutable)
- **Serialization**: `config.to_dict()` → JSON, `SimulationConfig.from_dict(dict)` → instance
- **Reproducibility**: Always set `random_seed` (default 42) for deterministic runs
- **Validation**: No runtime validation - trust caller to provide valid values

### Time Units and Conversions
- **All simulation times in MINUTES** (not seconds or hours)
- `simulation_time`: 480.0 = 8-hour shift
- `order_arrival_rate`: Per HOUR, but converted to per-minute via `/60.0` for exponential sampling
- `erp_sync_interval`: In SECONDS (exception to minutes rule)
- Time tracking: `order.pick_start_time`, `order.pack_end_time` store `env.now` (minutes)

### Order State Machine
Orders MUST follow strict state sequence (no skipping):
```
RECEIVED → PICKING → PICKED → PACKING → PACKED → SHIPPING → COMPLETED
```

**Status Assignment**:
```python
# ✅ CORRECT - use enum
order.status = OrderStatus.PICKING

# ❌ WRONG - don't use strings
order.status = "picking"
```

**Timing Fields**:
- `pick_start_time`, `pick_end_time`: Float (sim minutes)
- `pack_start_time`, `pack_end_time`: Float (sim minutes)
- `created_at`, `completed_at`: `datetime` objects (real-world time)

### Event Recording Pattern
Every significant action records event via `_record_event()`:

```python
# Standard pattern
self._record_event(EventType.ORDER_STATUS_CHANGED, {
    'order_id': order.order_id,
    'status': OrderStatus.COMPLETED.value,  # Use .value for enum
    'sim_time': self.env.now
})

# Inventory changes include delta
self._record_event(EventType.INVENTORY_UPDATED, {
    'sku': line.sku,
    'change': -line.quantity,  # Negative for consumption
    'sim_time': self.env.now
})
```

**Event Buffer**: Fixed-size deque (maxlen=1000), auto-evicts oldest when full.

### Resource Naming
- `workers`: SimPy Resource for human workers (picking, packing)
- `forklifts`: SimPy Resource for material handling equipment (transport only)
- `num_storage_locations`: Capacity limit (not enforced by simulation, metadata only)

### Metrics Collection
- **In-simulation tracking**: `self.metrics.record_order_completion(order, total_time)` called at end of each `order_process()`
- **Derived metrics**: Throughput = `60 / avg_order_time` (orders per hour)
- **Sublinear scaling**: Time ~ `quantity ** 0.5` for batch operations

### Inventory Management
- **No automatic replenishment**: Inventory only decreases via picking
- **Drift detection**: `calculate_sync_drift()` compares DT vs ERP quantities
- **Threshold trigger**: When drift > `config.sync_threshold` (default 5%), record `CALIBRATION_TRIGGER` event


## Calibration Algorithm Details

### Purpose
Automatically estimate simulation parameters (`pick_time_mean`, `pack_time_mean`, etc.) from historical ERP transaction logs, eliminating manual timing studies.

### Algorithm: Statistical Inference from Event Logs

**Input**: List of `WarehouseEvent` objects from ERP with timestamps and order status changes

**Process**:
1. **Event Parsing**: Extract timing data by correlating events per order
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
   calibrated['pick_time_std'] = statistics.stdev(pick_times)
   ```

4. **Auto-Apply**: Update `SimulationConfig` with calibrated values
   ```python
   for key, value in calibrated.items():
       setattr(self.config, key, value)
   ```

### Usage Example

```python
# Generate synthetic ERP events (or load from real ERP)
erp_events = []
for i in range(100):
    # Create order
    erp_events.append(WarehouseEvent(
        event_type=EventType.ORDER_CREATED,
        timestamp=base_time,
        data={'order_id': f'ORD-{i}'}
    ))
    # ... add PICKED, PACKED, COMPLETED events with realistic delays

# Calibrate
dt = WarehouseDigitalTwin(config, erp_adapter)
calibrated_params = dt.calibrate_from_erp_logs(erp_events)

# Result: {'pick_time_mean': 2.87, 'pick_time_std': 0.64, ...}
```

### Limitations
- Requires minimum 30-50 orders for statistical validity
- Assumes order processing follows standard workflow (no skipped stages)
- Does not account for external factors (worker fatigue, equipment failures)
- Calibration data stored in `self.calibration_data` for audit trail

### Drift Detection
Monitors divergence between digital twin and ERP inventory:

```python
drift = calculate_sync_drift()  # Returns 0.0-1.0
if drift > config.sync_threshold:  # Default 0.05 (5%)
    # Trigger recalibration
    self._record_event(EventType.CALIBRATION_TRIGGER, {'drift': drift})
```

## Sensitivity Analysis Details

### Purpose
Understand how changes in input parameters affect simulation outputs (throughput, cycle time, utilization).

### Implementation in `run_simulation.py`

**Worker Count Sensitivity** (lines 193-215):
- Sweeps `num_workers` from 3 to 10
- Measures throughput and average order time at each level
- Identifies optimal staffing level (typically where marginal improvement < 5%)

**Demand Rate Sensitivity** (lines 217-243):
- Sweeps `order_arrival_rate` from 5 to 20 orders/hour
- Detects system saturation point (where completed orders plateau)
- Shows queuing behavior under increasing load

### Running Sensitivity Analysis

```powershell
# Full analysis with results export
python run_simulation.py

# Output files:
# results/sensitivity_analysis_<timestamp>.csv
# Columns: parameter, value, throughput, avg_order_time, orders_completed
```

### Visualization (external tool required)

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('results/sensitivity_analysis_20251126.csv')

# Worker sensitivity
worker_data = df[df['parameter'] == 'num_workers']
plt.plot(worker_data['value'], worker_data['throughput'])
plt.xlabel('Number of Workers')
plt.ylabel('Throughput (orders/hour)')
plt.title('Worker Staffing Sensitivity')
plt.savefig('worker_sensitivity.png')
```

### Interpreting Results
- **Linear scaling**: Output proportional to input (e.g., 2x workers → 2x throughput)
- **Diminishing returns**: Output increase slows (common beyond resource bottleneck)
- **Saturation**: No improvement beyond certain point (indicates different bottleneck)

## Common Modification Patterns

### Adding a New Resource Type

**Example**: Add "packing stations" as a limited resource

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

### Creating a Custom ERP Adapter

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
        """Close connection."""
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
                lines=lines,
                status=self._map_odoo_to_status(odoo_order.get('state', 'draft'))
            )
            orders.append(order)
        
        return orders
    
    def _map_status_to_odoo(self, status: OrderStatus) -> str:
        """Map internal status to Odoo state."""
        mapping = {
            OrderStatus.RECEIVED: 'sale',
            OrderStatus.PICKING: 'picking',
            OrderStatus.COMPLETED: 'done'
        }
        return mapping.get(status, 'draft')
    
    # ... implement other abstract methods ...
```

### Adding Custom Metrics

**Example**: Track worker utilization percentage

```python
# 1. Add to DigitalTwinMetrics
class DigitalTwinMetrics:
    def __init__(self):
        # ... existing fields ...
        self.worker_busy_time = 0.0  # NEW
        self.total_sim_time = 0.0    # NEW
    
    def record_worker_usage(self, duration: float):  # NEW
        """Track worker busy time."""
        self.worker_busy_time += duration
    
    def set_total_time(self, duration: float):  # NEW
        self.total_sim_time = duration
    
    def get_summary(self) -> Dict[str, Any]:
        summary = {
            # ... existing metrics ...
        }
        
        # Calculate utilization
        if self.total_sim_time > 0:
            summary['worker_utilization'] = (
                self.worker_busy_time / 
                (self.total_sim_time * self.config.num_workers)
            )
        
        return summary

# 2. Track in order_process()
def order_process(self, order: Order):
    with self.workers.request() as worker_req:
        request_start = self.env.now  # NEW
        yield worker_req
        
        pick_time = self._sample_time(...)
        yield self.env.timeout(pick_time)
        
        worker_duration = self.env.now - request_start  # NEW
        self.metrics.record_worker_usage(worker_duration)  # NEW
```

## JOSS Submission Workflow

### Prerequisites (5 minutes)

1. **Get ORCID identifier**: Register at https://orcid.org/ if you don't have one
2. **Update author info** in `paper/paper.md`:
   ```yaml
   authors:
     - name: Your Full Name
       orcid: 0000-0002-1234-5678
       affiliation: 1
   affiliations:
     - name: Your Institution
       index: 1
   ```

### Step 1: Create Public GitHub Repository (15 minutes)

```powershell
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit: SME-DT-ERP v0.1.0"

# Create repository on GitHub (manual step):
# 1. Go to https://github.com/new
# 2. Name: sme-dt-erp
# 3. Visibility: PUBLIC (required for JOSS)
# 4. Do NOT initialize with README (we have one)

# Push to GitHub
git remote add origin https://github.com/YOUR-USERNAME/sme-dt-erp.git
git branch -M main
git push -u origin main
```

### Step 2: Verify CI Pipeline (5 minutes)

After pushing, GitHub Actions should automatically run. Check:
- Tests pass (`pytest tests/`)
- Linting passes (if configured)
- No import errors

Fix any failures before proceeding.

### Step 3: Create Release v0.1.0 (5 minutes)

On GitHub:
1. Go to Releases → "Create a new release"
2. Tag: `v0.1.0`
3. Title: `SME-DT-ERP v0.1.0`
4. Description:
   ```
   Initial release of SME-DT-ERP Digital Twin Framework
   
   Features:
   - SimPy discrete-event simulation engine
   - ERP adapter interface (ports & adapters pattern)
   - Automated calibration from ERP logs
   - What-if scenario analysis
   - Sensitivity analysis for resource optimization
   - Docker containerization
   ```
5. Publish release

### Step 4: Archive on Zenodo (10 minutes)

1. Go to https://zenodo.org/ and sign in with GitHub
2. Settings → GitHub → Sync now
3. Find your repository and flip the switch to ON
4. Create new release on GitHub (or use existing v0.1.0)
5. Zenodo automatically archives and assigns DOI
6. Copy DOI (format: `10.5281/zenodo.XXXXXXX`)

### Step 5: Update Paper with DOI (2 minutes)

Edit `paper/paper.md` front matter:
```yaml
---
title: 'SME-DT-ERP: An Open-Source Digital Twin Framework...'
# ... existing fields ...
repository: https://github.com/YOUR-USERNAME/sme-dt-erp
archive_doi: 10.5281/zenodo.XXXXXXX  # ADD THIS
---
```

Commit and push:
```powershell
git add paper/paper.md
git commit -m "Add Zenodo DOI to paper"
git push
```

### Step 6: Submit to JOSS (10 minutes)

1. Go to https://joss.theoj.org/
2. Sign in with GitHub
3. Click "Submit a paper"
4. Enter repository URL: `https://github.com/YOUR-USERNAME/sme-dt-erp`
5. JOSS automatically:
   - Detects `paper/paper.md` and `paper/paper.bib`
   - Runs pre-review checks
   - Creates review issue on GitHub

### Step 7: Respond to Review (2-6 weeks)

JOSS uses **open peer review** on GitHub:
- Editor assigns 2 reviewers
- Reviewers comment on the review issue
- Address feedback by:
  1. Making changes to code/paper
  2. Pushing updates to GitHub
  3. Commenting on review issue when done
- Repeat until reviewers approve

### JOSS Review Criteria

Reviewers check for:

| Criterion | Verification | Our Status |
|-----------|-------------|------------|
| **Installation** | `pip install` works without errors | ✅ `setup.py` configured |
| **Functionality** | Code runs as documented | ✅ `python core.py` works |
| **Tests** | Automated tests exist and pass | ✅ 680 lines of pytest |
| **Documentation** | README explains usage | ✅ Comprehensive README |
| **Community** | CONTRIBUTING.md exists | ✅ Included |
| **License** | OSI-approved license | ✅ MIT License |
| **Substantial effort** | >1000 LOC with research value | ✅ ~1400 LOC |
| **Paper quality** | Clear, well-referenced | ✅ 25+ citations |

### Common Review Requests

Be prepared to address:
- **API documentation**: Add docstrings to public methods (already done)
- **Installation instructions**: Clear steps in README (already done)
- **Example usage**: Working code examples (already done)
- **State of the field**: How it differs from existing tools (in paper)
- **Automated tests**: Reasonable coverage (already done)

### Post-Acceptance (automatic)

Once accepted, JOSS:
1. Publishes paper with DOI
2. Adds badge to your README
3. Archives on Crossref

Add badge to README:
```markdown
[![JOSS](https://joss.theoj.org/papers/10.21105/joss.XXXXX/status.svg)](https://joss.theoj.org/papers/10.21105/joss.XXXXX)
```

### Timeline Estimate

| Stage | Duration |
|-------|----------|
| Preparation (author info, repo, release) | 1 hour |
| JOSS submission | 10 minutes |
| Editor assignment | 1-2 weeks |
| Peer review | 2-4 weeks |
| Revisions (if needed) | 1-2 weeks |
| **Total** | **4-8 weeks** |

### Support Resources

- **JOSS Author Guide**: https://joss.readthedocs.io/en/latest/submitting.html
- **JOSS Review Checklist**: https://joss.readthedocs.io/en/latest/review_checklist.html
- **Example Review**: https://github.com/openjournals/joss-reviews/issues/ (browse recent)
- **Zenodo Help**: https://help.zenodo.org/

## Adding New ERP Adapters

1. Inherit from `ERPAdapterPort` abstract base class
2. Implement all 6 abstract methods: `connect()`, `disconnect()`, `fetch_orders()`, `fetch_inventory()`, `update_order_status()`, `update_inventory()`
3. Use `subscribe_to_events(callback)` for real-time integration
4. Example: See `MockERPAdapter` implementation (lines 240-372 in core.py)

## Important Notes

- **Dependencies**: SimPy 4.1+ and NumPy 1.21+ are mandatory. Check availability with `SIMPY_AVAILABLE` flag
- **Time Units**: All simulation times are in **minutes** (not seconds)
- **Metrics Calculation**: Throughput is computed as `60 / avg_order_time` to get orders per hour
- **Calibration**: System tracks drift between DT and ERP inventory. Triggers recalibration when drift exceeds `sync_threshold` (default 5%)
- **No Async IO**: SimPy uses generator-based coroutines, not Python async/await

## Common Pitfalls & Solutions

### 1. SimPy vs. Async/Await Confusion
**Problem**: Using `async/await` syntax instead of `yield`
```python
# ❌ WRONG - async/await doesn't work with SimPy
async def order_process(self, order):
    await self.workers.request()

# ✅ CORRECT - use generator with yield
def order_process(self, order):
    with self.workers.request() as req:
        yield req
```

### 2. Time Unit Conversions
**Problem**: Mixing time units causes incorrect inter-arrival times
```python
# ❌ WRONG - treats per-hour rate as per-minute
arrival_rate = self.config.order_arrival_rate  # 10.0/hr
inter_arrival = np.random.exponential(1.0 / arrival_rate)  # Wrong!

# ✅ CORRECT - convert to per-minute first
arrival_rate = self.config.order_arrival_rate / 60.0  # 10.0/60 = 0.167/min
inter_arrival = np.random.exponential(1.0 / arrival_rate)
```

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
# Auto-released here
```

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
```

### 5. Forgetting to Record Events
**Problem**: State changes without event recording break calibration
```python
# ❌ WRONG - invisible to ERP sync
self.inventory[sku].quantity -= line.quantity

# ✅ CORRECT - always record inventory changes
self.inventory[sku].quantity -= line.quantity
self._record_event(EventType.INVENTORY_UPDATED, {
    'sku': sku,
    'change': -line.quantity,
    'sim_time': self.env.now
})
```

### 6. Not Seeding Random Number Generators
**Problem**: Non-reproducible simulations make debugging impossible
```python
# ❌ WRONG - different results every run
random.seed()  # Seeds with system time
np.random.seed()

# ✅ CORRECT - use config seed
random.seed(self.config.random_seed)
np.random.seed(self.config.random_seed)
```

### 7. Negative Time Samples
**Problem**: Normal distribution can produce negative durations
```python
# ❌ WRONG - can return negative time
pick_time = np.random.normal(mean, std)

# ✅ CORRECT - truncate to minimum positive value
pick_time = max(0.1, np.random.normal(mean, std))
```

### 8. Testing with Production Time Scales
**Problem**: 8-hour simulations make tests slow
```python
# ❌ WRONG - tests take too long
config = SimulationConfig(simulation_time=480.0)  # 8 hours

# ✅ CORRECT - use short test duration
config = SimulationConfig(simulation_time=60.0)  # 1 hour for tests
```

