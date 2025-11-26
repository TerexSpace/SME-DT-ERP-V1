# Changelog

All notable changes to SME-DT-ERP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Additional ERP adapters (Odoo, ERPNext) planned
- REST API for external integration
- Web-based dashboard

## [0.1.0] - 2025-11-25

### Added
- Initial release of SME-DT-ERP framework
- Core simulation engine using SimPy for discrete-event simulation
- `SimulationConfig` dataclass for configurable parameters
- `WarehouseDigitalTwin` class for simulation orchestration
- `ERPAdapterPort` abstract base class for ERP integration
- `MockERPAdapter` for testing and development
- Order processing simulation (picking, packing, shipping)
- Resource modeling (workers, forklifts, storage locations)
- Event-driven architecture with `WarehouseEvent` and `EventType`
- What-if scenario analysis via `run_what_if_scenario()`
- Automatic calibration from ERP event logs via `calibrate_from_erp_logs()`
- Synchronization drift detection via `calculate_sync_drift()`
- `DigitalTwinMetrics` for performance tracking
- Comprehensive test suite with pytest
- Docker containerization support
- GitHub Actions CI workflow
- MIT License
- Full documentation (README, CONTRIBUTING, JOSS paper)

### Security
- Input validation on configuration parameters
- Safe handling of ERP credentials (adapter-level)

## [0.0.1] - 2025-11-01

### Added
- Project initialization
- Basic project structure
- Requirements definition

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2025-11-25 | Initial public release |
| 0.0.1 | 2025-11-01 | Project initialization |
