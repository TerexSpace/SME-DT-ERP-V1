"""
SME-DT-ERP: Digital Twin Framework for ERP-Integrated Warehouse Management in SMEs

This package provides tools for implementing warehouse digital twins integrated
with Enterprise Resource Planning (ERP) systems, specifically designed for
Small and Medium Enterprises (SMEs).

Main Components:
    - SimulationConfig: Configuration parameters for simulation
    - WarehouseDigitalTwin: Core simulation engine
    - ERPAdapterPort: Abstract interface for ERP integration
    - MockERPAdapter: Mock adapter for testing

Example:
    >>> from sme_dt_erp import SimulationConfig, MockERPAdapter, WarehouseDigitalTwin
    >>> config = SimulationConfig(simulation_time=480, num_workers=5)
    >>> adapter = MockERPAdapter(config)
    >>> adapter.connect()
    >>> dt = WarehouseDigitalTwin(config, adapter)
    >>> results = dt.run_simulation()

Author: [Author Name]
License: MIT
Version: 0.1.0
"""

__version__ = "0.1.0"
__author__ = "[Author Name]"
__license__ = "MIT"

from .core import (
    SimulationConfig,
    InventoryItem,
    OrderLine,
    Order,
    OrderStatus,
    EventType,
    WarehouseEvent,
    ERPAdapterPort,
    MockERPAdapter,
    WarehouseDigitalTwin,
    DigitalTwinMetrics,
)

__all__ = [
    "SimulationConfig",
    "InventoryItem",
    "OrderLine",
    "Order",
    "OrderStatus",
    "EventType",
    "WarehouseEvent",
    "ERPAdapterPort",
    "MockERPAdapter",
    "WarehouseDigitalTwin",
    "DigitalTwinMetrics",
]
