#!/usr/bin/env python3
"""
SME-DT-ERP: Comprehensive Simulation Runner

This script runs multiple simulation scenarios and generates results
suitable for inclusion in the JOSS paper.

Usage:
    python run_simulation.py

Output:
    - Console output with summary statistics
    - JSON file with detailed results
    - CSV file with metrics for plotting

Author: [Author Name]
License: MIT
"""

import json
import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import (
    SimulationConfig,
    MockERPAdapter,
    WarehouseDigitalTwin,
    OrderStatus,
    EventType,
    WarehouseEvent,
)


def run_baseline_simulation(config: SimulationConfig) -> Dict[str, Any]:
    """Run baseline simulation with default configuration."""
    print("\n" + "=" * 70)
    print("BASELINE SIMULATION")
    print("=" * 70)
    
    erp_adapter = MockERPAdapter(config)
    erp_adapter.connect()
    
    dt = WarehouseDigitalTwin(config, erp_adapter)
    results = dt.run_simulation()
    
    erp_adapter.disconnect()
    
    return results


def run_what_if_scenarios(base_config: SimulationConfig) -> List[Dict[str, Any]]:
    """Run multiple what-if scenarios."""
    print("\n" + "=" * 70)
    print("WHAT-IF SCENARIO ANALYSIS")
    print("=" * 70)
    
    scenarios = [
        {'name': 'Add 2 Workers', 'params': {'num_workers': 7}},
        {'name': 'Add 1 Forklift', 'params': {'num_forklifts': 3}},
        {'name': 'Double Workers', 'params': {'num_workers': 10}},
        {'name': 'High Demand (+50%)', 'params': {'order_arrival_rate': 15.0}},
        {'name': 'High Demand + More Staff', 'params': {'order_arrival_rate': 15.0, 'num_workers': 8}},
        {'name': 'Faster Picking (-20% time)', 'params': {'pick_time_mean': 1.6}},
        {'name': 'More Locations', 'params': {'num_storage_locations': 150}},
    ]
    
    results = []
    
    for scenario in scenarios:
        print(f"\n--- Scenario: {scenario['name']} ---")
        print(f"Parameters: {scenario['params']}")
        
        # Create fresh adapter and twin for each scenario
        erp_adapter = MockERPAdapter(base_config)
        erp_adapter.connect()
        
        dt = WarehouseDigitalTwin(base_config, erp_adapter)
        scenario_result = dt.run_what_if_scenario(scenario['params'])
        
        scenario_result['scenario_name'] = scenario['name']
        results.append(scenario_result)
        
        metrics = scenario_result['results']['metrics']
        print(f"  Orders completed: {metrics.get('orders_completed', 0)}")
        print(f"  Throughput: {metrics.get('throughput_orders_per_hour', 0):.1f} orders/hour")
        print(f"  Avg order time: {metrics.get('avg_order_time', 0):.2f} minutes")
        
        erp_adapter.disconnect()
    
    return results


def run_calibration_test(config: SimulationConfig) -> Dict[str, Any]:
    """Test calibration from simulated ERP event logs."""
    print("\n" + "=" * 70)
    print("CALIBRATION TEST")
    print("=" * 70)
    
    # Generate synthetic ERP events
    erp_events = []
    base_time = datetime.now()
    
    # Simulate 50 orders with realistic timing
    import random
    random.seed(config.random_seed)
    
    for i in range(50):
        order_id = f"TEST-{i:04d}"
        
        # Order created
        created_time = base_time
        erp_events.append(WarehouseEvent(
            event_id=f"EV-{len(erp_events):04d}",
            event_type=EventType.ORDER_CREATED,
            timestamp=created_time,
            data={'order_id': order_id, 'items': random.randint(1, 5)},
            source="erp"
        ))
        
        # Picked (2-5 minutes later)
        pick_duration = random.gauss(3.0, 0.8)
        picked_time = base_time + __import__('datetime').timedelta(minutes=pick_duration)
        erp_events.append(WarehouseEvent(
            event_id=f"EV-{len(erp_events):04d}",
            event_type=EventType.ORDER_STATUS_CHANGED,
            timestamp=picked_time,
            data={'order_id': order_id, 'new_status': OrderStatus.PICKED.value},
            source="erp"
        ))
        
        # Packed (2-4 minutes after picking)
        pack_duration = random.gauss(2.5, 0.6)
        packed_time = picked_time + __import__('datetime').timedelta(minutes=pack_duration)
        erp_events.append(WarehouseEvent(
            event_id=f"EV-{len(erp_events):04d}",
            event_type=EventType.ORDER_STATUS_CHANGED,
            timestamp=packed_time,
            data={'order_id': order_id, 'new_status': OrderStatus.PACKED.value},
            source="erp"
        ))
        
        # Completed
        erp_events.append(WarehouseEvent(
            event_id=f"EV-{len(erp_events):04d}",
            event_type=EventType.ORDER_STATUS_CHANGED,
            timestamp=packed_time + __import__('datetime').timedelta(minutes=0.5),
            data={'order_id': order_id, 'new_status': OrderStatus.COMPLETED.value},
            source="erp"
        ))
        
        # Update base time for next order
        base_time = packed_time + __import__('datetime').timedelta(minutes=random.expovariate(0.2))
    
    # Run calibration
    erp_adapter = MockERPAdapter(config)
    erp_adapter.connect()
    
    dt = WarehouseDigitalTwin(config, erp_adapter)
    calibrated_params = dt.calibrate_from_erp_logs(erp_events)
    
    erp_adapter.disconnect()
    
    print(f"\nCalibrated parameters from {len(erp_events)} events:")
    for key, value in calibrated_params.items():
        print(f"  {key}: {value:.3f}")
    
    return {
        'num_events': len(erp_events),
        'calibrated_params': calibrated_params
    }


def run_sensitivity_analysis(base_config: SimulationConfig) -> List[Dict[str, Any]]:
    """Run sensitivity analysis on key parameters."""
    print("\n" + "=" * 70)
    print("SENSITIVITY ANALYSIS")
    print("=" * 70)
    
    results = []
    
    # Sensitivity on number of workers (3-10)
    print("\n--- Worker Sensitivity ---")
    for num_workers in range(3, 11):
        erp_adapter = MockERPAdapter(base_config)
        erp_adapter.connect()
        
        dt = WarehouseDigitalTwin(base_config, erp_adapter)
        scenario_result = dt.run_what_if_scenario({'num_workers': num_workers})
        
        throughput = scenario_result['results']['metrics'].get('throughput_orders_per_hour', 0)
        avg_time = scenario_result['results']['metrics'].get('avg_order_time', 0)
        
        results.append({
            'parameter': 'num_workers',
            'value': num_workers,
            'throughput': throughput,
            'avg_order_time': avg_time
        })
        
        print(f"  Workers={num_workers}: Throughput={throughput:.1f}/hr, AvgTime={avg_time:.2f}min")
        
        erp_adapter.disconnect()
    
    # Sensitivity on arrival rate (5-20)
    print("\n--- Demand Sensitivity ---")
    for arrival_rate in [5, 8, 10, 12, 15, 18, 20]:
        erp_adapter = MockERPAdapter(base_config)
        erp_adapter.connect()
        
        dt = WarehouseDigitalTwin(base_config, erp_adapter)
        scenario_result = dt.run_what_if_scenario({'order_arrival_rate': arrival_rate})
        
        throughput = scenario_result['results']['metrics'].get('throughput_orders_per_hour', 0)
        avg_time = scenario_result['results']['metrics'].get('avg_order_time', 0)
        completed = scenario_result['results']['metrics'].get('orders_completed', 0)
        
        results.append({
            'parameter': 'order_arrival_rate',
            'value': arrival_rate,
            'throughput': throughput,
            'avg_order_time': avg_time,
            'orders_completed': completed
        })
        
        print(f"  ArrivalRate={arrival_rate}: Completed={completed}, AvgTime={avg_time:.2f}min")
        
        erp_adapter.disconnect()
    
    return results


def save_results(
    baseline: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    calibration: Dict[str, Any],
    sensitivity: List[Dict[str, Any]],
    output_dir: str = "results"
):
    """Save all results to files."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save comprehensive JSON
    all_results = {
        'timestamp': timestamp,
        'baseline': baseline,
        'scenarios': scenarios,
        'calibration': calibration,
        'sensitivity': sensitivity
    }
    
    json_path = os.path.join(output_dir, f"simulation_results_{timestamp}.json")
    with open(json_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved JSON results to: {json_path}")
    
    # Save sensitivity analysis as CSV
    csv_path = os.path.join(output_dir, f"sensitivity_analysis_{timestamp}.csv")
    with open(csv_path, 'w', newline='') as f:
        if sensitivity:
            writer = csv.DictWriter(f, fieldnames=sensitivity[0].keys())
            writer.writeheader()
            writer.writerows(sensitivity)
    print(f"Saved CSV results to: {csv_path}")
    
    # Save scenario comparison as CSV
    scenario_csv_path = os.path.join(output_dir, f"scenario_comparison_{timestamp}.csv")
    scenario_rows = []
    for s in scenarios:
        row = {
            'scenario': s['scenario_name'],
            **s['scenario_params'],
            **{k: v for k, v in s['results']['metrics'].items() if isinstance(v, (int, float))}
        }
        scenario_rows.append(row)
    
    if scenario_rows:
        with open(scenario_csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=scenario_rows[0].keys())
            writer.writeheader()
            writer.writerows(scenario_rows)
        print(f"Saved scenario comparison to: {scenario_csv_path}")


def print_summary(
    baseline: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    calibration: Dict[str, Any]
):
    """Print summary for paper inclusion."""
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY FOR PAPER")
    print("=" * 70)
    
    print("\n### Baseline Performance ###")
    metrics = baseline['metrics']
    print(f"- Orders completed: {metrics.get('orders_completed', 0)}")
    print(f"- Throughput: {metrics.get('throughput_orders_per_hour', 0):.2f} orders/hour")
    print(f"- Items throughput: {metrics.get('throughput_items_per_hour', 0):.2f} items/hour")
    print(f"- Average order time: {metrics.get('avg_order_time', 0):.2f} minutes")
    print(f"- Average picking time: {metrics.get('avg_picking_time', 0):.2f} minutes")
    print(f"- Average packing time: {metrics.get('avg_packing_time', 0):.2f} minutes")
    
    print("\n### What-If Scenario Improvements ###")
    baseline_throughput = metrics.get('throughput_orders_per_hour', 1)
    
    for scenario in scenarios:
        s_metrics = scenario['results']['metrics']
        s_throughput = s_metrics.get('throughput_orders_per_hour', 0)
        improvement = (s_throughput - baseline_throughput) / baseline_throughput * 100 if baseline_throughput > 0 else 0
        
        print(f"- {scenario['scenario_name']}: {improvement:+.1f}% throughput change")
    
    print("\n### Calibration Results ###")
    print(f"- Events processed: {calibration['num_events']}")
    for param, value in calibration['calibrated_params'].items():
        print(f"- Calibrated {param}: {value:.3f}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("SME-DT-ERP: Comprehensive Simulation Analysis")
    print("Digital Twin Framework for ERP-Integrated Warehouse Management")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    
    # Base configuration
    config = SimulationConfig(
        simulation_time=480.0,  # 8-hour shift
        time_unit="minutes",
        random_seed=42,
        num_storage_locations=100,
        num_workers=5,
        num_forklifts=2,
        pick_time_mean=2.0,
        pick_time_std=0.5,
        pack_time_mean=3.0,
        pack_time_std=0.8,
        transport_time_mean=1.5,
        transport_time_std=0.3,
        order_arrival_rate=10.0,  # orders per hour
        items_per_order_mean=3.0,
        items_per_order_std=1.5,
    )
    
    print("\n### Configuration ###")
    print(json.dumps(config.to_dict(), indent=2))
    
    # Run all analyses
    baseline = run_baseline_simulation(config)
    scenarios = run_what_if_scenarios(config)
    calibration = run_calibration_test(config)
    sensitivity = run_sensitivity_analysis(config)
    
    # Save results
    save_results(baseline, scenarios, calibration, sensitivity)
    
    # Print summary
    print_summary(baseline, scenarios, calibration)
    
    print("\n" + "=" * 70)
    print(f"Completed: {datetime.now().isoformat()}")
    print("=" * 70)
    
    return {
        'baseline': baseline,
        'scenarios': scenarios,
        'calibration': calibration,
        'sensitivity': sensitivity
    }


if __name__ == "__main__":
    results = main()
