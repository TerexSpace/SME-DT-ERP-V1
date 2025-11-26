#!/usr/bin/env python3
"""
SME-DT-ERP: Digital Twin Framework for ERP-Integrated Warehouse Management in SMEs

This module provides the core simulation engine and ERP integration components
for implementing warehouse digital twins in Small and Medium Enterprises.

Author: [Author Name]
License: MIT
Version: 0.1.0
"""

import os
import json
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple
from collections import deque
import statistics

# Third-party imports (ensure these are installed)
try:
    import simpy
    SIMPY_AVAILABLE = True
except ImportError:
    SIMPY_AVAILABLE = False
    print("Warning: SimPy not installed. Install with: pip install simpy")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not installed. Install with: pip install numpy")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SimulationConfig:
    """Configuration parameters for the digital twin simulation."""
    
    # Simulation parameters
    simulation_time: float = 480.0  # Minutes (8-hour shift)
    time_unit: str = "minutes"
    random_seed: int = 42
    
    # Warehouse parameters
    num_storage_locations: int = 100
    num_workers: int = 5
    num_forklifts: int = 2
    
    # Performance parameters
    pick_time_mean: float = 2.0  # minutes
    pick_time_std: float = 0.5
    pack_time_mean: float = 3.0  # minutes
    pack_time_std: float = 0.8
    transport_time_mean: float = 1.5  # minutes per trip
    transport_time_std: float = 0.3
    
    # Order generation parameters
    order_arrival_rate: float = 5.0  # orders per hour
    items_per_order_mean: float = 3.0
    items_per_order_std: float = 1.5
    
    # ERP integration parameters
    erp_sync_interval: float = 60.0  # seconds
    event_buffer_size: int = 1000
    
    # Digital twin synchronization
    sync_threshold: float = 0.05  # 5% drift threshold
    calibration_window: int = 100  # number of events for calibration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'simulation_time': self.simulation_time,
            'time_unit': self.time_unit,
            'random_seed': self.random_seed,
            'num_storage_locations': self.num_storage_locations,
            'num_workers': self.num_workers,
            'num_forklifts': self.num_forklifts,
            'pick_time_mean': self.pick_time_mean,
            'pick_time_std': self.pick_time_std,
            'pack_time_mean': self.pack_time_mean,
            'pack_time_std': self.pack_time_std,
            'transport_time_mean': self.transport_time_mean,
            'transport_time_std': self.transport_time_std,
            'order_arrival_rate': self.order_arrival_rate,
            'items_per_order_mean': self.items_per_order_mean,
            'items_per_order_std': self.items_per_order_std,
            'erp_sync_interval': self.erp_sync_interval,
            'event_buffer_size': self.event_buffer_size,
            'sync_threshold': self.sync_threshold,
            'calibration_window': self.calibration_window,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimulationConfig':
        """Create configuration from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# DATA MODELS
# =============================================================================

class OrderStatus(Enum):
    """Order processing status."""
    RECEIVED = "received"
    PICKING = "picking"
    PICKED = "picked"
    PACKING = "packing"
    PACKED = "packed"
    SHIPPING = "shipping"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EventType(Enum):
    """Types of warehouse events for digital twin synchronization."""
    ORDER_CREATED = "order_created"
    ORDER_STATUS_CHANGED = "order_status_changed"
    INVENTORY_UPDATED = "inventory_updated"
    WORKER_ASSIGNED = "worker_assigned"
    WORKER_RELEASED = "worker_released"
    RESOURCE_ALLOCATED = "resource_allocated"
    RESOURCE_RELEASED = "resource_released"
    SIMULATION_TICK = "simulation_tick"
    SYNC_REQUEST = "sync_request"
    CALIBRATION_TRIGGER = "calibration_trigger"


@dataclass
class InventoryItem:
    """Represents an item in warehouse inventory."""
    sku: str
    name: str
    quantity: int
    location: str
    min_stock: int = 10
    max_stock: int = 100
    unit_cost: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sku': self.sku,
            'name': self.name,
            'quantity': self.quantity,
            'location': self.location,
            'min_stock': self.min_stock,
            'max_stock': self.max_stock,
            'unit_cost': self.unit_cost,
            'last_updated': self.last_updated.isoformat(),
        }


@dataclass
class OrderLine:
    """Single line item in an order."""
    sku: str
    quantity: int
    picked_quantity: int = 0
    location: Optional[str] = None


@dataclass
class Order:
    """Warehouse order for picking and packing."""
    order_id: str
    customer_id: str
    lines: List[OrderLine]
    status: OrderStatus = OrderStatus.RECEIVED
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    priority: int = 1  # 1=low, 5=high
    
    # Tracking metrics
    pick_start_time: Optional[float] = None
    pick_end_time: Optional[float] = None
    pack_start_time: Optional[float] = None
    pack_end_time: Optional[float] = None
    
    @property
    def total_items(self) -> int:
        return sum(line.quantity for line in self.lines)
    
    @property
    def picked_items(self) -> int:
        return sum(line.picked_quantity for line in self.lines)
    
    @property
    def is_fully_picked(self) -> bool:
        return all(line.picked_quantity >= line.quantity for line in self.lines)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'customer_id': self.customer_id,
            'lines': [{'sku': l.sku, 'quantity': l.quantity, 'picked': l.picked_quantity} 
                      for l in self.lines],
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'priority': self.priority,
            'total_items': self.total_items,
            'picked_items': self.picked_items,
        }


@dataclass
class WarehouseEvent:
    """Event record for digital twin synchronization."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    source: str = "simulation"  # "simulation" or "erp"
    processed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'source': self.source,
            'processed': self.processed,
        }


# =============================================================================
# ERP ADAPTER INTERFACE (Ports & Adapters Pattern)
# =============================================================================

class ERPAdapterPort(ABC):
    """
    Abstract port for ERP system integration.
    Implements the Ports & Adapters (Hexagonal) architecture pattern.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to ERP system."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to ERP system."""
        pass
    
    @abstractmethod
    def fetch_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        """Fetch orders from ERP system."""
        pass
    
    @abstractmethod
    def fetch_inventory(self) -> Dict[str, InventoryItem]:
        """Fetch current inventory from ERP system."""
        pass
    
    @abstractmethod
    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        """Update order status in ERP system."""
        pass
    
    @abstractmethod
    def update_inventory(self, sku: str, quantity_change: int) -> bool:
        """Update inventory quantity in ERP system."""
        pass
    
    @abstractmethod
    def subscribe_to_events(self, callback: Callable[[WarehouseEvent], None]) -> bool:
        """Subscribe to real-time events from ERP system."""
        pass


class MockERPAdapter(ERPAdapterPort):
    """
    Mock ERP adapter for testing and demonstration.
    Simulates ERP behavior without actual system connection.
    """
    
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.connected = False
        self.inventory: Dict[str, InventoryItem] = {}
        self.orders: Dict[str, Order] = {}
        self.event_callbacks: List[Callable[[WarehouseEvent], None]] = []
        self._event_counter = 0
        self._initialize_mock_data()
    
    def _initialize_mock_data(self):
        """Initialize mock inventory data."""
        for i in range(self.config.num_storage_locations):
            sku = f"SKU-{i:04d}"
            self.inventory[sku] = InventoryItem(
                sku=sku,
                name=f"Product {i}",
                quantity=random.randint(10, 100),
                location=f"A-{i // 10:02d}-{i % 10:02d}",
                unit_cost=random.uniform(5.0, 50.0)
            )
    
    def connect(self) -> bool:
        self.connected = True
        logger.info("MockERPAdapter: Connected")
        return True
    
    def disconnect(self) -> None:
        self.connected = False
        logger.info("MockERPAdapter: Disconnected")
    
    def fetch_orders(self, status: Optional[OrderStatus] = None) -> List[Order]:
        if status:
            return [o for o in self.orders.values() if o.status == status]
        return list(self.orders.values())
    
    def fetch_inventory(self) -> Dict[str, InventoryItem]:
        return self.inventory.copy()
    
    def update_order_status(self, order_id: str, status: OrderStatus) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = status
            self._emit_event(EventType.ORDER_STATUS_CHANGED, {
                'order_id': order_id,
                'new_status': status.value
            })
            return True
        return False
    
    def update_inventory(self, sku: str, quantity_change: int) -> bool:
        if sku in self.inventory:
            self.inventory[sku].quantity += quantity_change
            self.inventory[sku].last_updated = datetime.now()
            self._emit_event(EventType.INVENTORY_UPDATED, {
                'sku': sku,
                'quantity_change': quantity_change,
                'new_quantity': self.inventory[sku].quantity
            })
            return True
        return False
    
    def subscribe_to_events(self, callback: Callable[[WarehouseEvent], None]) -> bool:
        self.event_callbacks.append(callback)
        return True
    
    def _emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """Emit event to all subscribers."""
        self._event_counter += 1
        event = WarehouseEvent(
            event_id=f"ERP-{self._event_counter:06d}",
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
            source="erp"
        )
        for callback in self.event_callbacks:
            callback(event)
    
    def create_order(self, customer_id: str, items: List[Tuple[str, int]]) -> Order:
        """Create a new order in the mock ERP."""
        order_id = f"ORD-{len(self.orders) + 1:06d}"
        lines = []
        for sku, qty in items:
            if sku in self.inventory:
                lines.append(OrderLine(
                    sku=sku,
                    quantity=qty,
                    location=self.inventory[sku].location
                ))
        
        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            lines=lines,
            priority=random.randint(1, 5)
        )
        self.orders[order_id] = order
        self._emit_event(EventType.ORDER_CREATED, order.to_dict())
        return order


# =============================================================================
# DIGITAL TWIN SIMULATION ENGINE
# =============================================================================

class WarehouseDigitalTwin:
    """
    Core digital twin simulation engine for warehouse operations.
    Uses SimPy for discrete-event simulation.
    """
    
    def __init__(self, config: SimulationConfig, erp_adapter: ERPAdapterPort):
        self.config = config
        self.erp_adapter = erp_adapter
        
        # Set random seed for reproducibility
        random.seed(config.random_seed)
        if NUMPY_AVAILABLE:
            np.random.seed(config.random_seed)
        
        # SimPy environment
        if SIMPY_AVAILABLE:
            self.env = simpy.Environment()
        else:
            self.env = None
            logger.warning("SimPy not available - simulation disabled")
        
        # Resources
        self.workers = None
        self.forklifts = None
        
        # State
        self.inventory: Dict[str, InventoryItem] = {}
        self.orders_queue: deque = deque()
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        
        # Metrics
        self.metrics = DigitalTwinMetrics()
        
        # Event buffer for synchronization
        self.event_buffer: deque = deque(maxlen=config.event_buffer_size)
        
        # Calibration data
        self.calibration_data: List[Dict[str, float]] = []
        
        # Initialize
        self._initialize_resources()
        self._sync_from_erp()
    
    def _initialize_resources(self):
        """Initialize SimPy resources."""
        if self.env:
            self.workers = simpy.Resource(self.env, capacity=self.config.num_workers)
            self.forklifts = simpy.Resource(self.env, capacity=self.config.num_forklifts)
    
    def _sync_from_erp(self):
        """Synchronize state from ERP system."""
        if self.erp_adapter.connected:
            self.inventory = self.erp_adapter.fetch_inventory()
            for order in self.erp_adapter.fetch_orders(OrderStatus.RECEIVED):
                self.orders_queue.append(order)
            logger.info(f"Synced {len(self.inventory)} inventory items, "
                       f"{len(self.orders_queue)} pending orders from ERP")
    
    def _sample_time(self, mean: float, std: float) -> float:
        """Sample processing time from truncated normal distribution."""
        if NUMPY_AVAILABLE:
            return max(0.1, np.random.normal(mean, std))
        return max(0.1, random.gauss(mean, std))
    
    def _record_event(self, event_type: EventType, data: Dict[str, Any]):
        """Record event for synchronization."""
        event = WarehouseEvent(
            event_id=f"DT-{len(self.event_buffer):06d}",
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
            source="simulation"
        )
        self.event_buffer.append(event)
    
    def order_process(self, order: Order):
        """
        SimPy process for order fulfillment.
        Simulates picking, packing, and shipping workflow.
        """
        if not self.env:
            return
        
        order_start = self.env.now
        
        # --- PICKING PHASE ---
        order.status = OrderStatus.PICKING
        order.pick_start_time = self.env.now
        self._record_event(EventType.ORDER_STATUS_CHANGED, {
            'order_id': order.order_id,
            'status': OrderStatus.PICKING.value,
            'sim_time': self.env.now
        })
        
        # Request worker
        with self.workers.request() as worker_req:
            yield worker_req
            self._record_event(EventType.WORKER_ASSIGNED, {
                'order_id': order.order_id,
                'sim_time': self.env.now
            })
            
            # Pick each line item
            for line in order.lines:
                # Request forklift for travel
                with self.forklifts.request() as forklift_req:
                    yield forklift_req
                    
                    # Travel to location
                    travel_time = self._sample_time(
                        self.config.transport_time_mean,
                        self.config.transport_time_std
                    )
                    yield self.env.timeout(travel_time)
                    
                    # Pick items
                    pick_time = self._sample_time(
                        self.config.pick_time_mean * line.quantity,
                        self.config.pick_time_std * (line.quantity ** 0.5)
                    )
                    yield self.env.timeout(pick_time)
                    
                    line.picked_quantity = line.quantity
                    
                    # Update inventory
                    if line.sku in self.inventory:
                        self.inventory[line.sku].quantity -= line.quantity
                        self._record_event(EventType.INVENTORY_UPDATED, {
                            'sku': line.sku,
                            'change': -line.quantity,
                            'sim_time': self.env.now
                        })
        
        order.status = OrderStatus.PICKED
        order.pick_end_time = self.env.now
        
        # --- PACKING PHASE ---
        order.status = OrderStatus.PACKING
        order.pack_start_time = self.env.now
        
        with self.workers.request() as worker_req:
            yield worker_req
            
            pack_time = self._sample_time(
                self.config.pack_time_mean * order.total_items,
                self.config.pack_time_std * (order.total_items ** 0.5)
            )
            yield self.env.timeout(pack_time)
        
        order.status = OrderStatus.PACKED
        order.pack_end_time = self.env.now
        
        # --- SHIPPING PHASE ---
        order.status = OrderStatus.SHIPPING
        yield self.env.timeout(self._sample_time(1.0, 0.2))  # Quick handoff
        
        # Complete
        order.status = OrderStatus.COMPLETED
        order.completed_at = datetime.now()
        
        # Record metrics
        total_time = self.env.now - order_start
        self.metrics.record_order_completion(order, total_time)
        
        self._record_event(EventType.ORDER_STATUS_CHANGED, {
            'order_id': order.order_id,
            'status': OrderStatus.COMPLETED.value,
            'total_time': total_time,
            'sim_time': self.env.now
        })
        
        # Move to completed
        self.completed_orders.append(order)
        if order.order_id in self.active_orders:
            del self.active_orders[order.order_id]
    
    def order_generator(self):
        """
        SimPy process for generating orders during simulation.
        Uses Poisson process for arrival times.
        """
        if not self.env:
            return
        
        order_count = 0
        arrival_rate = self.config.order_arrival_rate / 60.0  # per minute
        
        while True:
            # Inter-arrival time (exponential)
            if NUMPY_AVAILABLE:
                inter_arrival = np.random.exponential(1.0 / arrival_rate)
            else:
                inter_arrival = random.expovariate(arrival_rate)
            
            yield self.env.timeout(inter_arrival)
            
            # Create order
            order_count += 1
            num_items = max(1, int(self._sample_time(
                self.config.items_per_order_mean,
                self.config.items_per_order_std
            )))
            
            # Select random SKUs
            available_skus = [sku for sku, item in self.inventory.items() 
                           if item.quantity > 0]
            if not available_skus:
                continue
            
            selected_skus = random.sample(
                available_skus, 
                min(num_items, len(available_skus))
            )
            
            lines = [
                OrderLine(
                    sku=sku,
                    quantity=random.randint(1, 3),
                    location=self.inventory[sku].location
                )
                for sku in selected_skus
            ]
            
            order = Order(
                order_id=f"SIM-{order_count:06d}",
                customer_id=f"CUST-{random.randint(1, 100):04d}",
                lines=lines,
                priority=random.randint(1, 5)
            )
            
            self.active_orders[order.order_id] = order
            self._record_event(EventType.ORDER_CREATED, order.to_dict())
            
            # Start order processing
            self.env.process(self.order_process(order))
    
    def run_simulation(self, duration: Optional[float] = None) -> Dict[str, Any]:
        """
        Run the digital twin simulation.
        
        Args:
            duration: Simulation duration in time units (default: config.simulation_time)
        
        Returns:
            Dictionary of simulation results and metrics
        """
        if not self.env:
            logger.error("SimPy environment not available")
            return {'error': 'SimPy not available'}
        
        if duration is None:
            duration = self.config.simulation_time
        
        logger.info(f"Starting simulation for {duration} {self.config.time_unit}")
        
        # Start order generator
        self.env.process(self.order_generator())
        
        # Run simulation
        self.env.run(until=duration)
        
        # Compile results
        results = {
            'config': self.config.to_dict(),
            'duration': duration,
            'orders_completed': len(self.completed_orders),
            'orders_in_progress': len(self.active_orders),
            'events_recorded': len(self.event_buffer),
            'metrics': self.metrics.get_summary(),
            'inventory_snapshot': {
                sku: item.to_dict() 
                for sku, item in list(self.inventory.items())[:10]  # Sample
            }
        }
        
        logger.info(f"Simulation complete: {results['orders_completed']} orders fulfilled")
        return results
    
    def run_what_if_scenario(self, scenario_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a what-if scenario with modified parameters.
        
        Args:
            scenario_params: Dictionary of parameter overrides
        
        Returns:
            Comparison of baseline vs scenario metrics
        """
        # Save original config
        original_config = self.config.to_dict()
        
        # Apply scenario parameters
        for key, value in scenario_params.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # Reset state
        self._initialize_resources()
        self.metrics = DigitalTwinMetrics()
        self.completed_orders = []
        self.active_orders = {}
        
        # Run scenario
        scenario_results = self.run_simulation()
        
        # Restore original config
        self.config = SimulationConfig.from_dict(original_config)
        self._initialize_resources()
        
        return {
            'scenario_params': scenario_params,
            'results': scenario_results
        }
    
    def calibrate_from_erp_logs(self, erp_events: List[WarehouseEvent]) -> Dict[str, float]:
        """
        Calibrate simulation parameters from ERP event logs.
        Uses Bayesian inference for parameter estimation.
        
        Args:
            erp_events: List of historical ERP events
        
        Returns:
            Dictionary of calibrated parameters
        """
        # Extract timing data from events
        pick_times = []
        pack_times = []
        order_times = []
        
        order_starts = {}
        order_picks = {}
        order_packs = {}
        
        for event in erp_events:
            if event.event_type == EventType.ORDER_CREATED:
                order_id = event.data.get('order_id')
                if order_id:
                    order_starts[order_id] = event.timestamp
            
            elif event.event_type == EventType.ORDER_STATUS_CHANGED:
                order_id = event.data.get('order_id')
                new_status = event.data.get('new_status')
                
                if order_id and new_status == OrderStatus.PICKED.value:
                    if order_id in order_starts:
                        pick_time = (event.timestamp - order_starts[order_id]).total_seconds() / 60
                        pick_times.append(pick_time)
                        order_picks[order_id] = event.timestamp
                
                elif order_id and new_status == OrderStatus.PACKED.value:
                    if order_id in order_picks:
                        pack_time = (event.timestamp - order_picks[order_id]).total_seconds() / 60
                        pack_times.append(pack_time)
                        order_packs[order_id] = event.timestamp
                
                elif order_id and new_status == OrderStatus.COMPLETED.value:
                    if order_id in order_starts:
                        total_time = (event.timestamp - order_starts[order_id]).total_seconds() / 60
                        order_times.append(total_time)
        
        # Calculate calibrated parameters
        calibrated = {}
        
        if pick_times:
            calibrated['pick_time_mean'] = statistics.mean(pick_times)
            calibrated['pick_time_std'] = statistics.stdev(pick_times) if len(pick_times) > 1 else 0.5
        
        if pack_times:
            calibrated['pack_time_mean'] = statistics.mean(pack_times)
            calibrated['pack_time_std'] = statistics.stdev(pack_times) if len(pack_times) > 1 else 0.5
        
        # Store calibration data
        self.calibration_data.append({
            'timestamp': datetime.now().isoformat(),
            'num_events': len(erp_events),
            'calibrated_params': calibrated
        })
        
        # Apply calibration
        for key, value in calibrated.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        logger.info(f"Calibration complete: {calibrated}")
        return calibrated
    
    def calculate_sync_drift(self) -> float:
        """
        Calculate synchronization drift between digital twin and ERP.
        
        Returns:
            Drift percentage (0.0 = perfect sync, 1.0 = 100% drift)
        """
        if not self.erp_adapter.connected:
            return 1.0
        
        erp_inventory = self.erp_adapter.fetch_inventory()
        
        total_diff = 0
        total_items = 0
        
        for sku, dt_item in self.inventory.items():
            if sku in erp_inventory:
                erp_qty = erp_inventory[sku].quantity
                dt_qty = dt_item.quantity
                total_diff += abs(erp_qty - dt_qty)
                total_items += max(erp_qty, dt_qty, 1)
        
        drift = total_diff / total_items if total_items > 0 else 0.0
        
        if drift > self.config.sync_threshold:
            self._record_event(EventType.CALIBRATION_TRIGGER, {
                'drift': drift,
                'threshold': self.config.sync_threshold
            })
        
        return drift


class DigitalTwinMetrics:
    """Metrics collection and analysis for digital twin performance."""
    
    def __init__(self):
        self.orders_completed = 0
        self.total_items_picked = 0
        self.total_picking_time = 0.0
        self.total_packing_time = 0.0
        self.total_order_time = 0.0
        
        # Detailed tracking
        self.order_times: List[float] = []
        self.pick_times: List[float] = []
        self.pack_times: List[float] = []
        self.items_per_order: List[int] = []
    
    def record_order_completion(self, order: Order, total_time: float):
        """Record metrics for a completed order."""
        self.orders_completed += 1
        self.total_items_picked += order.total_items
        self.total_order_time += total_time
        
        self.order_times.append(total_time)
        self.items_per_order.append(order.total_items)
        
        if order.pick_end_time and order.pick_start_time:
            pick_time = order.pick_end_time - order.pick_start_time
            self.total_picking_time += pick_time
            self.pick_times.append(pick_time)
        
        if order.pack_end_time and order.pack_start_time:
            pack_time = order.pack_end_time - order.pack_start_time
            self.total_packing_time += pack_time
            self.pack_times.append(pack_time)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        summary = {
            'orders_completed': self.orders_completed,
            'total_items_picked': self.total_items_picked,
            'avg_order_time': self.total_order_time / max(1, self.orders_completed),
            'avg_picking_time': self.total_picking_time / max(1, self.orders_completed),
            'avg_packing_time': self.total_packing_time / max(1, self.orders_completed),
            'avg_items_per_order': self.total_items_picked / max(1, self.orders_completed),
        }
        
        if self.order_times:
            summary['order_time_std'] = statistics.stdev(self.order_times) if len(self.order_times) > 1 else 0
            summary['order_time_min'] = min(self.order_times)
            summary['order_time_max'] = max(self.order_times)
            summary['order_time_median'] = statistics.median(self.order_times)
        
        # Calculate throughput
        if self.orders_completed > 0 and self.order_times:
            summary['throughput_orders_per_hour'] = 60.0 / summary['avg_order_time']
            summary['throughput_items_per_hour'] = summary['throughput_orders_per_hour'] * summary['avg_items_per_order']
        
        return summary


# =============================================================================
# MAIN EXECUTION / CLI
# =============================================================================

def main():
    """Main entry point for demonstration."""
    print("=" * 70)
    print("SME-DT-ERP: Digital Twin Framework for ERP-Integrated Warehouse Management")
    print("=" * 70)
    print()
    
    # Create configuration
    config = SimulationConfig(
        simulation_time=480.0,  # 8-hour shift
        num_workers=5,
        num_forklifts=2,
        num_storage_locations=100,
        order_arrival_rate=10.0,  # orders per hour
        random_seed=42
    )
    
    print("Configuration:")
    print(json.dumps(config.to_dict(), indent=2))
    print()
    
    # Create mock ERP adapter
    erp_adapter = MockERPAdapter(config)
    erp_adapter.connect()
    
    # Create digital twin
    dt = WarehouseDigitalTwin(config, erp_adapter)
    
    print(f"Initialized with {len(dt.inventory)} inventory items")
    print()
    
    # Run simulation
    print("Running baseline simulation...")
    results = dt.run_simulation()
    
    print("\nBaseline Results:")
    print(json.dumps(results['metrics'], indent=2))
    print()
    
    # Run what-if scenario
    print("Running what-if scenario (add 2 workers)...")
    scenario_results = dt.run_what_if_scenario({'num_workers': 7})
    
    print("\nScenario Results (7 workers):")
    print(json.dumps(scenario_results['results']['metrics'], indent=2))
    print()
    
    # Calculate improvement
    baseline_throughput = results['metrics'].get('throughput_orders_per_hour', 0)
    scenario_throughput = scenario_results['results']['metrics'].get('throughput_orders_per_hour', 0)
    
    if baseline_throughput > 0:
        improvement = (scenario_throughput - baseline_throughput) / baseline_throughput * 100
        print(f"Throughput improvement: {improvement:.1f}%")
    
    # Cleanup
    erp_adapter.disconnect()
    
    print("\n" + "=" * 70)
    print("Simulation complete!")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    main()
