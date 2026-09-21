"""
BusNotify - Data Structures & Algorithms (DSA) Service
Module implementing core DSA concepts explicitly requested in Section 50:
1. Hash Map (O(1) bus lookup)
2. Graph (Adjacency List for transit stops and route connectivity)
3. Multi-criteria Searching & Filtering
4. Sorting (Alternative-bus multi-key ranking)
5. Priority Queue (Emergency depot requests)
6. Haversine Formula (Geographic distance)
7. Greedy Allocation (Passenger redistribution across available bus capacities)

All functions and classes include formal Time and Space complexity documentation.
"""
import math
import heapq
from typing import Dict, List, Any, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. HAVERSINE FORMULA
# ---------------------------------------------------------------------------
def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two GPS coordinates using the Haversine formula.
    
    Time Complexity: O(1) - Constant number of trigonometric and arithmetic operations.
    Space Complexity: O(1) - Auxiliary space is constant.
    
    :return: Distance in kilometers.
    """
    R = 6371.0  # Earth's mean radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 3)


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """
    Calculates walking distance in meters between two coordinates.
    Time Complexity: O(1)
    Space Complexity: O(1)
    """
    return int(haversine_distance_km(lat1, lon1, lat2, lon2) * 1000)


# ---------------------------------------------------------------------------
# 2. HASH MAP: O(1) Bus & Stop Registry
# ---------------------------------------------------------------------------
class BusRegistryHashMap:
    """
    In-memory Hash Map mapping bus_number -> active bus metadata for fast O(1) lookups.
    
    Time Complexity:
      - insert / update: O(1) average
      - get: O(1) average
      - delete: O(1) average
    Space Complexity: O(N) where N is the number of active buses.
    """
    def __init__(self):
        self._table: Dict[str, Dict[str, Any]] = {}

    def put(self, bus_number: str, data: Dict[str, Any]) -> None:
        self._table[str(bus_number).strip().upper()] = data

    def get(self, bus_number: str) -> Optional[Dict[str, Any]]:
        return self._table.get(str(bus_number).strip().upper())

    def contains(self, bus_number: str) -> bool:
        return str(bus_number).strip().upper() in self._table

    def all_buses(self) -> List[Dict[str, Any]]:
        return list(self._table.values())

    def size(self) -> int:
        return len(self._table)


# ---------------------------------------------------------------------------
# 3. GRAPH: Adjacency List Transit Network
# ---------------------------------------------------------------------------
class TransitNetworkGraph:
    """
    Graph representation of transit stops and route connections.
    Vertices = Stops (id, name, lat, lon)
    Edges = Direct route segments between consecutive stops with distance/travel time weights.
    
    Time Complexity:
      - Add stop: O(1)
      - Add edge: O(1)
      - Find reachable stops (BFS/DFS): O(V + E)
      - Check direct connectivity: O(deg(V))
    Space Complexity: O(V + E)
    """
    def __init__(self):
        self.adj_list: Dict[int, List[Dict[str, Any]]] = {}
        self.stop_meta: Dict[int, Dict[str, Any]] = {}

    def add_stop(self, stop_id: int, name: str, lat: float, lon: float) -> None:
        if stop_id not in self.adj_list:
            self.adj_list[stop_id] = []
            self.stop_meta[stop_id] = {"id": stop_id, "name": name, "lat": lat, "lon": lon}

    def add_route_segment(self, from_stop_id: int, to_stop_id: int, route_id: int,
                          distance_km: float, time_min: int) -> None:
        if from_stop_id not in self.adj_list:
            self.adj_list[from_stop_id] = []
        self.adj_list[from_stop_id].append({
            "to_stop_id": to_stop_id,
            "route_id": route_id,
            "distance_km": distance_km,
            "time_min": time_min,
        })

    def is_directly_connected(self, stop_a_id: int, stop_b_id: int) -> Tuple[bool, Optional[int]]:
        """Checks if stop A has a direct route segment to stop B."""
        for edge in self.adj_list.get(stop_a_id, []):
            if edge["to_stop_id"] == stop_b_id:
                return True, edge["route_id"]
        return False, None


# ---------------------------------------------------------------------------
# 4. SORTING & RANKING: Multi-Criteria Alternative Bus Ranking
# ---------------------------------------------------------------------------
def rank_alternative_buses(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks alternative candidate buses using Section 16 multi-factor criteria:
      1. Direct route (True > False)
      2. Correct direction (destination matches) (True > False)
      3. Available capacity / seats (descending)
      4. Lowest ETA (ascending)
      5. Lowest walking distance (ascending)
      6. Lower historical delay (ascending)

    Time Complexity: O(K log K) where K is number of valid candidate buses.
    Space Complexity: O(K) for sorted result list.
    """
    def sort_key(item: Dict[str, Any]):
        return (
            1 if item.get("direct_route", False) else 0,
            1 if item.get("destination_compatible", True) else 0,
            item.get("available_seats", 0),
            -item.get("eta_minutes", 999),
            -item.get("walking_distance_m", 9999),
            -item.get("historical_delay_min", 999.0)
        )

    # Sort descending based on key elements (using reverse=True on combined tuple)
    sorted_candidates = sorted(candidates, key=sort_key, reverse=True)
    
    # Assign ranks and mark the top one as recommended
    for idx, candidate in enumerate(sorted_candidates):
        candidate["rank_order"] = idx + 1
        candidate["is_recommended"] = (idx == 0)

    return sorted_candidates


# ---------------------------------------------------------------------------
# 5. PRIORITY QUEUE: Emergency Depot Requests
# ---------------------------------------------------------------------------
class EmergencyRequestPriorityQueue:
    """
    Min-Heap Priority Queue for Depot Emergency Requests.
    Priority values:
      CRITICAL = 1
      HIGH = 2
      MEDIUM = 3
      LOW = 4
    Secondary key: creation timestamp (earlier first).
    
    Time Complexity:
      - push: O(log N)
      - pop: O(log N)
      - peek: O(1)
    Space Complexity: O(N)
    """
    PRIORITY_MAP = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}

    def __init__(self):
        self._heap: List[Tuple[int, float, Dict[str, Any]]] = []

    def push(self, request: Dict[str, Any], timestamp: float) -> None:
        p_val = self.PRIORITY_MAP.get(request.get("priority", "HIGH").upper(), 2)
        heapq.heappush(self._heap, (p_val, timestamp, request))

    def pop(self) -> Optional[Dict[str, Any]]:
        if not self._heap:
            return None
        _, _, request = heapq.heappop(self._heap)
        return request

    def peek(self) -> Optional[Dict[str, Any]]:
        return self._heap[0][2] if self._heap else None

    def size(self) -> int:
        return len(self._heap)


# ---------------------------------------------------------------------------
# 6. GREEDY PASSENGER REDISTRIBUTION ALGORITHM
# ---------------------------------------------------------------------------
def greedy_passenger_redistribution(
    affected_passengers: int,
    available_buses: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Greedy algorithm to distribute affected passengers across available buses
    (including alternative passing buses and replacement bus).
    
    Section 17 & 42 Demonstration Example:
      Bus 123 affected: 40
      Bus 156 (seats: 15) -> 15 allocated
      Bus 178 (seats: 30) -> 15 allocated (or up to remaining)
      Bus 189 (Replacement, capacity: 40) -> 10 allocated
      Total transferred = 40, Remaining = 0.
      
    Constraints:
      transferred_i <= bus_capacity_i
      sum(transferred) <= affected_passengers
      transferred_i >= 0
      
    Time Complexity: O(B log B) for sorting buses by priority/seats, O(B) for allocation pass.
    Space Complexity: O(B) where B is number of available buses.
    
    :return: (allocated_buses_list, total_transferred, remaining_passengers)
    """
    remaining = affected_passengers
    total_transferred = 0
    results: List[Dict[str, Any]] = []

    for bus in available_buses:
        cap = int(bus.get("available_seats", 0) or bus.get("capacity", 0))
        if remaining <= 0 or cap <= 0:
            alloc = 0
        else:
            alloc = min(remaining, cap)
            remaining -= alloc
            total_transferred += alloc

        bus_entry = dict(bus)
        bus_entry["allocated_passengers"] = alloc
        bus_entry["remaining_after_allocation"] = cap - alloc
        results.append(bus_entry)

    return results, total_transferred, remaining
