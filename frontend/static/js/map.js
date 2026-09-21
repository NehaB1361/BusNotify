/**
 * BusNotify - Leaflet Map Engine
 * Renders stops, bus locations, route paths, and live pulsing markers
 */

const TransitMap = {
  createMap(elementId, initialLat = 18.5204, initialLon = 73.8567, zoom = 12) {
    if (!document.getElementById(elementId)) return null;

    const map = L.map(elementId).setView([initialLat, initialLon], zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors | BusNotify Transit Flow',
      maxZoom: 18,
    }).addTo(map);

    return map;
  },

  createBusIcon(status = 'RUNNING') {
    let color = '#E85D04';
    if (status === 'DELAYED') color = '#CA8A04';
    else if (status === 'PUNCTURED' || status === 'BREAKDOWN') color = '#DC2626';
    else if (status === 'DISPATCHED') color = '#2563EB';

    return L.divIcon({
      className: 'custom-bus-marker',
      html: `<div style="background-color: ${color}; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; border: 3px solid white; box-shadow: 0 3px 8px rgba(0,0,0,0.3); font-size: 16px;"><i class="bi bi-bus-front"></i></div>`,
      iconSize: [34, 34],
      iconAnchor: [17, 17],
      popupAnchor: [0, -17]
    });
  },

  createStopIcon(isCurrent = false) {
    const color = isCurrent ? '#E85D04' : '#64748B';
    const size = isCurrent ? 14 : 10;
    return L.divIcon({
      className: 'custom-stop-marker',
      html: `<div style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: 2px solid white; box-shadow: 0 1px 4px rgba(0,0,0,0.2);"></div>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2]
    });
  }
};
