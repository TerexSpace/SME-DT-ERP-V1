# SME-DT-ERP: Digital Twin Framework for ERP-Integrated Warehouse Management

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![JOSS](https://img.shields.io/badge/JOSS-submitted-green.svg)](https://joss.theoj.org/)

An open-source Python framework enabling Small and Medium Enterprises (SMEs) to implement warehouse digital twins integrated with ERP systems.

## Features

- **Discrete-Event Simulation**: SimPy-based warehouse operations modeling
- **ERP Integration**: Plug-and-play adapters for Odoo, ERPNext, SAP Business One
- **Real-Time Synchronization**: Event-driven architecture with <100ms latency
- **What-If Analysis**: Scenario simulation without disrupting physical operations
- **Automated Calibration**: Parameter estimation from ERP transaction logs
- **SME-Optimized**: Deployable for <$500/month cloud costs

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/TerexSpace/SME-DT-ERP-V1.git
cd SME-DT-ERP-V1

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run demonstration
python -m sme_dt_erp.core
```

### Docker Deployment

```bash
# Build image
docker build -t sme-dt-erp .

# Run container
docker run -p 8000:8000 sme-dt-erp
```

## Usage Example

```python
from sme_dt_erp.core import (
    SimulationConfig,
    MockERPAdapter,
    WarehouseDigitalTwin
)

# Configure simulation
config = SimulationConfig(
    simulation_time=480.0,  # 8-hour shift (minutes)
    num_workers=5,
    num_forklifts=2,
    num_storage_locations=100,
    order_arrival_rate=10.0  # orders per hour
)

# Initialize ERP adapter
erp_adapter = MockERPAdapter(config)
erp_adapter.connect()

# Create digital twin
dt = WarehouseDigitalTwin(config, erp_adapter)

# Run simulation
results = dt.run_simulation()
print(f"Orders completed: {results['orders_completed']}")
print(f"Throughput: {results['metrics']['throughput_orders_per_hour']:.1f} orders/hour")

# Run what-if scenario
scenario = dt.run_what_if_scenario({'num_workers': 7})
print(f"With 7 workers: {scenario['results']['metrics']['throughput_orders_per_hour']:.1f} orders/hour")

# Cleanup
erp_adapter.disconnect()
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SME-DT-ERP Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │   ERP Layer   │  │  IoT Layer    │  │   UI Layer    │       │
│  │ (Odoo/SAP B1) │  │ (MQTT/OPC-UA) │  │ (React/Dash)  │       │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘       │
│          │                  │                  │                │
│  ┌───────▼──────────────────▼──────────────────▼───────┐       │
│  │            Event Bus (Kafka/RabbitMQ)                │       │
│  └───────────────────────────┬─────────────────────────┘       │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────┐       │
│  │              Core Services (Python)                  │       │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │       │
│  │  │ ERP Adapter │ │  DT Engine  │ │  Analytics  │    │       │
│  │  │  (ports)    │ │  (SimPy)    │ │  (PyTorch)  │    │       │
│  │  └─────────────┘ └─────────────┘ └─────────────┘    │       │
│  └─────────────────────────────────────────────────────┘       │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────┐       │
│  │           Data Layer (PostgreSQL/TimescaleDB)        │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `simulation_time` | 480.0 | Simulation duration (minutes) |
| `num_workers` | 5 | Number of warehouse workers |
| `num_forklifts` | 2 | Number of forklifts |
| `num_storage_locations` | 100 | Warehouse storage locations |
| `order_arrival_rate` | 5.0 | Orders per hour |
| `pick_time_mean` | 2.0 | Average pick time (minutes) |
| `pack_time_mean` | 3.0 | Average pack time (minutes) |
| `random_seed` | 42 | Random seed for reproducibility |

## Documentation

- [User Guide](docs/user_guide.md)
- [API Reference](docs/api_reference.md)
- [ERP Adapter Development](docs/erp_adapters.md)
- [Deployment Guide](docs/deployment.md)

## Requirements

- Python 3.9+
- SimPy 4.1+
- NumPy 1.21+
- (Optional) Docker for containerized deployment

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Citation

If you use SME-DT-ERP in your research, please cite:

```bibtex
@software{sme_dt_erp,
  author = {[Author Name]},
  title = {{SME-DT-ERP}: Digital Twin Framework for ERP-Integrated Warehouse Management},
  year = {2025},
  url = {https://github.com/[username]/sme-dt-erp}
}
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- SimPy team for the discrete-event simulation framework
- OpenTwins project for architectural inspiration
- SME research community for requirements validation
# SME-DT-ERP-V1
