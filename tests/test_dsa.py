"""
Tests for Data Structures & Algorithms (Section 50)
Verifies:
1. Haversine Distance
2. In-memory Hash Map (O(1))
3. Graph Connectivity (Adjacency List)
4. Multi-Criteria Ranking & Sorting
5. Priority Queue (Min-Heap)
6. Greedy Passenger Allocation (40 affected passengers demo)
"""
from app.services.dsa_service import (
    haversine_distance_km,
    haversine_distance_meters,
    BusRegistryHashMap,
    TransitNetworkGraph,
    rank_alternative_buses,
    EmergencyRequestPriorityQueue,
    greedy_passenger_redistribution,
)


def test_haversine_distance():
    # Pune Station (18.5284, 73.8744) to Magarpatta (18.5134, 73.9242)
    dist_km = haversine_distance_km(18.5284, 73.8744, 18.5134, 73.9242)
    assert 5.0 <= dist_km <= 7.0
    dist_m = haversine_distance_meters(18.5284, 73.8744, 18.5134, 73.9242)
    assert dist_m > 5000


def test_hash_map_operations():
    hmap = BusRegistryHashMap()
    hmap.put("123", {"status": "RUNNING", "capacity": 40})
    hmap.put("156", {"status": "RUNNING", "capacity": 40})

    assert hmap.contains("123") is True
    assert hmap.contains("999") is False
    assert hmap.get("123")["status"] == "RUNNING"
    assert hmap.size() == 2


def test_graph_transit_network():
    graph = TransitNetworkGraph()
    graph.add_stop(1, "Pune Station", 18.5284, 73.8744)
    graph.add_stop(2, "Magarpatta", 18.5134, 73.9242)
    graph.add_stop(3, "Hadapsar", 18.5089, 73.9260)

    graph.add_route_segment(1, 2, route_id=101, distance_km=6.0, time_min=20)
    graph.add_route_segment(2, 3, route_id=101, distance_km=3.0, time_min=10)

    connected, r_id = graph.is_directly_connected(1, 2)
    assert connected is True
    assert r_id == 101

    not_direct, _ = graph.is_directly_connected(1, 3)
    assert not_direct is False


def test_alternative_bus_ranking():
    candidates = [
        {"bus_number": "178", "direct_route": False, "destination_compatible": True, "available_seats": 30, "eta_minutes": 18, "walking_distance_m": 100, "historical_delay_min": 11.0},
        {"bus_number": "156", "direct_route": True, "destination_compatible": True, "available_seats": 15, "eta_minutes": 12, "walking_distance_m": 0, "historical_delay_min": 8.0},
    ]

    ranked = rank_alternative_buses(candidates)
    assert ranked[0]["bus_number"] == "156"  # Direct route takes priority
    assert ranked[0]["is_recommended"] is True
    assert ranked[1]["is_recommended"] is False


def test_emergency_priority_queue():
    pq = EmergencyRequestPriorityQueue()
    pq.push({"code": "DR002", "priority": "LOW"}, timestamp=100.0)
    pq.push({"code": "DR001", "priority": "CRITICAL"}, timestamp=105.0)
    pq.push({"code": "DR003", "priority": "HIGH"}, timestamp=90.0)

    first = pq.pop()
    assert first["code"] == "DR001"  # CRITICAL highest
    second = pq.pop()
    assert second["code"] == "DR003"  # HIGH next
    third = pq.pop()
    assert third["code"] == "DR002"  # LOW last


def test_greedy_passenger_redistribution_scenario():
    """
    Demonstrates Section 17 & 42:
      Affected: 40
      Bus 156 (Seats 15) -> 15
      Bus 178 (Seats 30) -> 15 (or available up to remaining)
      Bus 189 (Replacement, 40) -> 10
      Total transferred: 40, Remaining: 0
    """
    affected = 40
    buses = [
        {"bus_number": "156", "available_seats": 15},
        {"bus_number": "178", "available_seats": 15},  # 15 seats taken
        {"bus_number": "189", "available_seats": 40},  # replacement
    ]

    allocated, total_transferred, remaining = greedy_passenger_redistribution(affected, buses)
    assert total_transferred == 40
    assert remaining == 0
    assert allocated[0]["allocated_passengers"] == 15
    assert allocated[1]["allocated_passengers"] == 15
    assert allocated[2]["allocated_passengers"] == 10
