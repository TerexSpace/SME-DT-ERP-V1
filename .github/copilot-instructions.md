# SME-DT-ERP Development Guide

## Project Overview

**Repository**: https://github.com/TerexSpace/SME-DT-ERP-V1  
**Author**: Almas Ospanov (a.ospanov@astanait.edu.kz)  
**Institution**: Astana IT University, School of Software Engineering  
**License**: MIT  
**Status**: Ready for JOSS submission

## Architecture

**SimPy discrete-event simulation** framework for warehouse digital twins with ERP integration using **Ports & Adapters** pattern.

### Core Files
- `core.py` (955 LOC): Simulation engine (`WarehouseDigitalTwin`), domain models, `ERPAdapterPort` interface, `MockERPAdapter`
- `run_simulation.py` (383 LOC): Batch scenario runner with what-if analysis and sensitivity sweeps
- `tests/test_core.py` (680 LOC): Pytest suite with fixtures (`default_config`, `mock_erp_adapter`, `digital_twin`, `sample_order`)
- `paper/paper.md`: JOSS paper (606 words, JOSS-compliant)

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
black sme_dt_erp/ tests/          # Auto-format
isort sme_dt_erp/ tests/          # Sort imports
flake8 sme_dt_erp/ tests/         # Linting
mypy sme_dt_erp/                  # Type checking

# Docker
docker build -t sme-dt-erp:latest .
docker run --rm -v ${PWD}/results:/app/results sme-dt-erp:latest python run_simulation.py

# JOSS paper compilation (requires Docker)
docker run --rm --volume ${PWD}/paper:/data --env JOURNAL=joss openjournals/inara
# OR push to GitHub → Actions tab → Download paper.pdf artifact
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

## JOSS Submission Workflow

### Prerequisites (5 minutes)

1. **Get ORCID identifier**: Register at https://orcid.org/
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
# Initialize git
git init
git add .
git commit -m "Initial commit: SME-DT-ERP v0.1.0"

# Create repository on GitHub: https://github.com/new
# Name: sme-dt-erp
# Visibility: PUBLIC (required for JOSS)

# Push to GitHub
git remote add origin https://github.com/YOUR-USERNAME/sme-dt-erp.git
git branch -M main
git push -u origin main
```

### Step 2: Verify CI Pipeline (5 minutes)

After pushing, GitHub Actions should run. Check tests pass.

### Step 3: Create Release v0.1.0 (5 minutes)

On GitHub: Releases → "Create a new release"
- Tag: `v0.1.0`
- Title: `SME-DT-ERP v0.1.0`
- Description: List key features

### Step 4: Archive on Zenodo (10 minutes)

1. Go to https://zenodo.org/ and sign in with GitHub
2. Settings → GitHub → Sync now
3. Find repository and enable
4. Zenodo assigns DOI (format: `10.5281/zenodo.XXXXXXX`)

### Step 5: Update Paper with DOI (2 minutes)

Edit `paper/paper.md`:
```yaml
archive_doi: 10.5281/zenodo.XXXXXXX  # ADD THIS
```

### Step 6: Submit to JOSS (10 minutes)

1. Go to https://joss.theoj.org/
2. Sign in with GitHub
3. "Submit a paper"
4. Enter repository URL

### Step 7: Respond to Review (2-6 weeks)

JOSS uses open peer review on GitHub. Address reviewer feedback.

### Timeline Estimate

| Stage | Duration |
|-------|----------|
| Preparation | 1 hour |
| Submission | 10 minutes |
| Editor assignment | 1-2 weeks |
| Peer review | 2-4 weeks |
| Revisions | 1-2 weeks |
| **Total** | **4-8 weeks** |

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
