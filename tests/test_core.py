#!/usr/bin/env python3
"""
Unit tests for SME-DT-ERP core module.

Run with:
    pytest tests/test_core.py -v
    pytest tests/test_core.py -v --cov=sme_dt_erp --cov-report=html
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import modules under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import (
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


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_config():
    """Create a default simulation configuration."""
    return SimulationConfig(
        simulation_time=60.0,  # Short simulation for testing
        random_seed=42,
        num_storage_locations=20,
        num_workers=3,
        num_forklifts=1,
        order_arrival_rate=5.0,
    )


@pytest.fixture
def mock_erp_adapter(default_config):
    """Create a mock ERP adapter."""
    adapter = MockERPAdapter(default_config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def digital_twin(default_config, mock_erp_adapter):
    """Create a digital twin instance."""
    return WarehouseDigitalTwin(default_config, mock_erp_adapter)


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        order_id="TEST-001",
        customer_id="CUST-001",
        lines=[
            OrderLine(sku="SKU-0001", quantity=2, location="A-01-01"),
            OrderLine(sku="SKU-0002", quantity=3, location="A-02-02"),
        ],
        priority=3
    )


@pytest.fixture
def sample_inventory_item():
    """Create a sample inventory item."""
    return InventoryItem(
        sku="SKU-TEST",
        name="Test Product",
        quantity=50,
        location="A-01-01",
        min_stock=10,
        max_stock=100,
        unit_cost=25.99
    )


# =============================================================================
# SIMULATION CONFIG TESTS
# =============================================================================

class TestSimulationConfig:
    """Tests for SimulationConfig class."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = SimulationConfig()
        
        assert config.simulation_time == 480.0
        assert config.time_unit == "minutes"
        assert config.random_seed == 42
        assert config.num_workers == 5
        assert config.num_forklifts == 2
        assert config.num_storage_locations == 100
    
    def test_custom_values(self):
        """Test configuration with custom values."""
        config = SimulationConfig(
            simulation_time=120.0,
            num_workers=10,
            random_seed=123
        )
        
        assert config.simulation_time == 120.0
        assert config.num_workers == 10
        assert config.random_seed == 123
    
    def test_to_dict(self):
        """Test configuration serialization to dictionary."""
        config = SimulationConfig(simulation_time=100.0)
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict['simulation_time'] == 100.0
        assert 'num_workers' in config_dict
        assert 'random_seed' in config_dict
    
    def test_from_dict(self):
        """Test configuration deserialization from dictionary."""
        data = {
            'simulation_time': 200.0,
            'num_workers': 8,
            'random_seed': 999
        }
        config = SimulationConfig.from_dict(data)
        
        assert config.simulation_time == 200.0
        assert config.num_workers == 8
        assert config.random_seed == 999
    
    def test_roundtrip_serialization(self):
        """Test that to_dict/from_dict preserve values."""
        original = SimulationConfig(
            simulation_time=300.0,
            num_workers=7,
            order_arrival_rate=15.0
        )
        
        config_dict = original.to_dict()
        restored = SimulationConfig.from_dict(config_dict)
        
        assert restored.simulation_time == original.simulation_time
        assert restored.num_workers == original.num_workers
        assert restored.order_arrival_rate == original.order_arrival_rate


# =============================================================================
# DATA MODEL TESTS
# =============================================================================

class TestInventoryItem:
    """Tests for InventoryItem class."""
    
    def test_creation(self, sample_inventory_item):
        """Test inventory item creation."""
        item = sample_inventory_item
        
        assert item.sku == "SKU-TEST"
        assert item.name == "Test Product"
        assert item.quantity == 50
        assert item.location == "A-01-01"
    
    def test_to_dict(self, sample_inventory_item):
        """Test inventory item serialization."""
        item_dict = sample_inventory_item.to_dict()
        
        assert item_dict['sku'] == "SKU-TEST"
        assert item_dict['quantity'] == 50
        assert 'last_updated' in item_dict


class TestOrder:
    """Tests for Order class."""
    
    def test_creation(self, sample_order):
        """Test order creation."""
        order = sample_order
        
        assert order.order_id == "TEST-001"
        assert order.customer_id == "CUST-001"
        assert len(order.lines) == 2
        assert order.status == OrderStatus.RECEIVED
    
    def test_total_items(self, sample_order):
        """Test total items calculation."""
        assert sample_order.total_items == 5  # 2 + 3
    
    def test_picked_items_initial(self, sample_order):
        """Test that picked items starts at zero."""
        assert sample_order.picked_items == 0
    
    def test_is_fully_picked_false(self, sample_order):
        """Test is_fully_picked when not all items picked."""
        assert sample_order.is_fully_picked is False
    
    def test_is_fully_picked_true(self, sample_order):
        """Test is_fully_picked when all items picked."""
        for line in sample_order.lines:
            line.picked_quantity = line.quantity
        
        assert sample_order.is_fully_picked is True
    
    def test_to_dict(self, sample_order):
        """Test order serialization."""
        order_dict = sample_order.to_dict()
        
        assert order_dict['order_id'] == "TEST-001"
        assert order_dict['total_items'] == 5
        assert order_dict['status'] == "received"


class TestOrderStatus:
    """Tests for OrderStatus enum."""
    
    def test_status_values(self):
        """Test that all expected status values exist."""
        assert OrderStatus.RECEIVED.value == "received"
        assert OrderStatus.PICKING.value == "picking"
        assert OrderStatus.PACKED.value == "packed"
        assert OrderStatus.COMPLETED.value == "completed"


class TestWarehouseEvent:
    """Tests for WarehouseEvent class."""
    
    def test_creation(self):
        """Test event creation."""
        event = WarehouseEvent(
            event_id="EV-001",
            event_type=EventType.ORDER_CREATED,
            timestamp=datetime.now(),
            data={'order_id': 'TEST-001'},
            source="simulation"
        )
        
        assert event.event_id == "EV-001"
        assert event.event_type == EventType.ORDER_CREATED
        assert event.processed is False
    
    def test_to_dict(self):
        """Test event serialization."""
        event = WarehouseEvent(
            event_id="EV-002",
            event_type=EventType.INVENTORY_UPDATED,
            timestamp=datetime.now(),
            data={'sku': 'SKU-001', 'change': -5}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict['event_id'] == "EV-002"
        assert event_dict['event_type'] == "inventory_updated"


# =============================================================================
# MOCK ERP ADAPTER TESTS
# =============================================================================

class TestMockERPAdapter:
    """Tests for MockERPAdapter class."""
    
    def test_connection(self, default_config):
        """Test adapter connection."""
        adapter = MockERPAdapter(default_config)
        
        assert adapter.connected is False
        result = adapter.connect()
        assert result is True
        assert adapter.connected is True
        
        adapter.disconnect()
        assert adapter.connected is False
    
    def test_inventory_initialization(self, mock_erp_adapter, default_config):
        """Test that inventory is initialized with correct number of items."""
        inventory = mock_erp_adapter.fetch_inventory()
        
        assert len(inventory) == default_config.num_storage_locations
    
    def test_fetch_orders_empty(self, mock_erp_adapter):
        """Test fetching orders when none exist."""
        orders = mock_erp_adapter.fetch_orders()
        
        assert orders == []
    
    def test_create_order(self, mock_erp_adapter):
        """Test order creation in mock ERP."""
        items = [("SKU-0001", 2), ("SKU-0002", 3)]
        order = mock_erp_adapter.create_order("CUST-001", items)
        
        assert order.order_id.startswith("ORD-")
        assert order.customer_id == "CUST-001"
        assert len(order.lines) == 2
    
    def test_update_order_status(self, mock_erp_adapter):
        """Test order status update."""
        # Create an order first
        order = mock_erp_adapter.create_order("CUST-001", [("SKU-0001", 1)])
        
        # Update status
        result = mock_erp_adapter.update_order_status(
            order.order_id, 
            OrderStatus.PICKING
        )
        
        assert result is True
        
        # Verify status changed
        orders = mock_erp_adapter.fetch_orders(OrderStatus.PICKING)
        assert len(orders) == 1
        assert orders[0].order_id == order.order_id
    
    def test_update_inventory(self, mock_erp_adapter):
        """Test inventory quantity update."""
        inventory = mock_erp_adapter.fetch_inventory()
        sku = list(inventory.keys())[0]
        original_qty = inventory[sku].quantity
        
        result = mock_erp_adapter.update_inventory(sku, -5)
        
        assert result is True
        
        updated_inventory = mock_erp_adapter.fetch_inventory()
        assert updated_inventory[sku].quantity == original_qty - 5
    
    def test_event_subscription(self, mock_erp_adapter):
        """Test event subscription and callback."""
        events_received = []
        
        def callback(event):
            events_received.append(event)
        
        mock_erp_adapter.subscribe_to_events(callback)
        
        # Trigger an event by creating an order
        mock_erp_adapter.create_order("CUST-001", [("SKU-0001", 1)])
        
        assert len(events_received) > 0
        assert events_received[0].event_type == EventType.ORDER_CREATED


# =============================================================================
# DIGITAL TWIN TESTS
# =============================================================================

class TestWarehouseDigitalTwin:
    """Tests for WarehouseDigitalTwin class."""
    
    def test_initialization(self, digital_twin, default_config):
        """Test digital twin initialization."""
        assert digital_twin.config == default_config
        assert len(digital_twin.inventory) > 0
        assert digital_twin.env is not None  # SimPy environment
    
    def test_inventory_sync(self, digital_twin):
        """Test that inventory is synced from ERP."""
        assert len(digital_twin.inventory) == digital_twin.config.num_storage_locations
    
    def test_run_simulation(self, digital_twin):
        """Test running a simulation."""
        results = digital_twin.run_simulation(duration=30.0)
        
        assert 'orders_completed' in results
        assert 'metrics' in results
        assert 'config' in results
        assert results['duration'] == 30.0
    
    def test_simulation_completes_orders(self, digital_twin):
        """Test that simulation processes orders."""
        results = digital_twin.run_simulation(duration=60.0)
        
        # With arrival rate of 5/hour, expect some orders in 60 minutes
        assert results['orders_completed'] >= 0
    
    def test_what_if_scenario(self, digital_twin):
        """Test what-if scenario analysis."""
        scenario_params = {'num_workers': 6}
        
        scenario_results = digital_twin.run_what_if_scenario(scenario_params)
        
        assert 'scenario_params' in scenario_results
        assert 'results' in scenario_results
        assert scenario_results['scenario_params'] == scenario_params
    
    def test_event_recording(self, digital_twin):
        """Test that events are recorded during simulation."""
        digital_twin.run_simulation(duration=30.0)
        
        assert len(digital_twin.event_buffer) > 0
    
    def test_sync_drift_calculation(self, digital_twin):
        """Test synchronization drift calculation."""
        drift = digital_twin.calculate_sync_drift()
        
        # Initially should be in sync
        assert 0.0 <= drift <= 1.0


class TestDigitalTwinCalibration:
    """Tests for digital twin calibration functionality."""
    
    def test_calibration_from_events(self, digital_twin):
        """Test calibration from ERP event logs."""
        # Create synthetic events
        events = []
        base_time = datetime.now()
        
        for i in range(10):
            order_id = f"CAL-{i:04d}"
            
            # Order created
            events.append(WarehouseEvent(
                event_id=f"EV-{len(events)}",
                event_type=EventType.ORDER_CREATED,
                timestamp=base_time,
                data={'order_id': order_id},
                source="erp"
            ))
            
            # Order picked (3 minutes later)
            events.append(WarehouseEvent(
                event_id=f"EV-{len(events)}",
                event_type=EventType.ORDER_STATUS_CHANGED,
                timestamp=base_time + timedelta(minutes=3),
                data={'order_id': order_id, 'new_status': OrderStatus.PICKED.value},
                source="erp"
            ))
            
            # Order packed (2 minutes after picking)
            events.append(WarehouseEvent(
                event_id=f"EV-{len(events)}",
                event_type=EventType.ORDER_STATUS_CHANGED,
                timestamp=base_time + timedelta(minutes=5),
                data={'order_id': order_id, 'new_status': OrderStatus.PACKED.value},
                source="erp"
            ))
            
            # Order completed
            events.append(WarehouseEvent(
                event_id=f"EV-{len(events)}",
                event_type=EventType.ORDER_STATUS_CHANGED,
                timestamp=base_time + timedelta(minutes=5.5),
                data={'order_id': order_id, 'new_status': OrderStatus.COMPLETED.value},
                source="erp"
            ))
            
            base_time += timedelta(minutes=10)
        
        # Run calibration
        calibrated = digital_twin.calibrate_from_erp_logs(events)
        
        assert 'pick_time_mean' in calibrated
        assert 'pack_time_mean' in calibrated
        assert calibrated['pick_time_mean'] > 0


# =============================================================================
# METRICS TESTS
# =============================================================================

class TestDigitalTwinMetrics:
    """Tests for DigitalTwinMetrics class."""
    
    def test_initialization(self):
        """Test metrics initialization."""
        metrics = DigitalTwinMetrics()
        
        assert metrics.orders_completed == 0
        assert metrics.total_items_picked == 0
        assert len(metrics.order_times) == 0
    
    def test_record_order_completion(self, sample_order):
        """Test recording order completion."""
        metrics = DigitalTwinMetrics()
        
        sample_order.pick_start_time = 0.0
        sample_order.pick_end_time = 10.0
        sample_order.pack_start_time = 10.0
        sample_order.pack_end_time = 20.0
        
        metrics.record_order_completion(sample_order, total_time=25.0)
        
        assert metrics.orders_completed == 1
        assert metrics.total_items_picked == 5
        assert len(metrics.order_times) == 1
    
    def test_get_summary(self, sample_order):
        """Test getting metrics summary."""
        metrics = DigitalTwinMetrics()
        
        sample_order.pick_start_time = 0.0
        sample_order.pick_end_time = 10.0
        sample_order.pack_start_time = 10.0
        sample_order.pack_end_time = 20.0
        
        metrics.record_order_completion(sample_order, total_time=25.0)
        
        summary = metrics.get_summary()
        
        assert summary['orders_completed'] == 1
        assert summary['avg_order_time'] == 25.0
        assert 'throughput_orders_per_hour' in summary


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for the complete system."""
    
    def test_full_workflow(self, default_config):
        """Test complete workflow from ERP to simulation."""
        # Setup
        adapter = MockERPAdapter(default_config)
        adapter.connect()
        
        # Create some initial orders
        adapter.create_order("CUST-001", [("SKU-0001", 2)])
        adapter.create_order("CUST-002", [("SKU-0002", 1)])
        
        # Create digital twin
        dt = WarehouseDigitalTwin(default_config, adapter)
        
        # Run simulation
        results = dt.run_simulation(duration=30.0)
        
        # Verify results
        assert results['orders_completed'] >= 0
        assert 'metrics' in results
        
        # Cleanup
        adapter.disconnect()
    
    def test_scenario_comparison(self, default_config):
        """Test comparing multiple scenarios."""
        adapter = MockERPAdapter(default_config)
        adapter.connect()
        
        dt = WarehouseDigitalTwin(default_config, adapter)
        
        # Run baseline
        baseline = dt.run_simulation(duration=30.0)
        
        # Run scenario
        scenario = dt.run_what_if_scenario({'num_workers': 6})
        
        # Both should complete without errors
        assert baseline['metrics']['orders_completed'] >= 0
        assert scenario['results']['metrics']['orders_completed'] >= 0
        
        adapter.disconnect()


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Performance tests for simulation engine."""
    
    def test_simulation_speed(self, default_config):
        """Test that simulation runs in reasonable time."""
        import time
        
        adapter = MockERPAdapter(default_config)
        adapter.connect()
        
        dt = WarehouseDigitalTwin(default_config, adapter)
        
        start = time.time()
        dt.run_simulation(duration=480.0)  # 8-hour simulation
        elapsed = time.time() - start
        
        # Simulation should complete in under 5 seconds
        assert elapsed < 5.0, f"Simulation took {elapsed:.2f}s, expected < 5s"
        
        adapter.disconnect()
    
    def test_memory_usage(self, default_config):
        """Test that simulation doesn't leak memory."""
        import gc
        
        adapter = MockERPAdapter(default_config)
        adapter.connect()
        
        # Run multiple simulations
        for _ in range(5):
            dt = WarehouseDigitalTwin(default_config, adapter)
            dt.run_simulation(duration=60.0)
        
        gc.collect()
        
        # If we get here without OOM, test passes
        adapter.disconnect()


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_inventory(self):
        """Test handling of empty inventory."""
        config = SimulationConfig(num_storage_locations=0)
        adapter = MockERPAdapter(config)
        adapter.connect()
        
        # Should not crash
        inventory = adapter.fetch_inventory()
        assert len(inventory) == 0
        
        adapter.disconnect()
    
    def test_zero_workers(self):
        """Test handling of zero workers."""
        config = SimulationConfig(
            num_workers=0,
            simulation_time=10.0
        )
        adapter = MockERPAdapter(config)
        adapter.connect()
        
        dt = WarehouseDigitalTwin(config, adapter)
        
        # Should not crash, but orders won't complete
        results = dt.run_simulation()
        
        adapter.disconnect()
    
    def test_very_high_arrival_rate(self):
        """Test handling of very high order arrival rate."""
        config = SimulationConfig(
            order_arrival_rate=100.0,  # Very high
            simulation_time=10.0
        )
        adapter = MockERPAdapter(config)
        adapter.connect()
        
        dt = WarehouseDigitalTwin(config, adapter)
        results = dt.run_simulation()
        
        # Should handle gracefully
        assert 'orders_completed' in results
        
        adapter.disconnect()
    
    def test_invalid_sku_update(self, mock_erp_adapter):
        """Test updating inventory for non-existent SKU."""
        result = mock_erp_adapter.update_inventory("INVALID-SKU", -5)
        
        assert result is False


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=.", "--cov-report=term-missing"])
