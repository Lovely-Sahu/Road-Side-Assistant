/*
 * RSA live tracking map (Leaflet). Shows ONLY real data:
 *  - the driver's reported location (if the driver shared it)
 *  - the assigned provider's latest shared location (with its age; marked stale)
 *  - a straight-line distance, and a road route/ETA only when a routing
 *    service (OSRM-compatible, RSA_ROUTING_URL) is configured and answers.
 * Nothing is animated or invented: if there is no new location, nothing moves.
 */
(function () {
  'use strict';

  function TrackMap(element, config) {
    this.el = element;
    this.config = config || {};
    this.map = null;
    this.driverMarker = null;
    this.providerMarker = null;
    this.line = null;
    this.route = null;
    this.lastRouteKey = null;
    this.lastRouteAt = 0;
    this.fitted = false;
    this.available = typeof window.L !== 'undefined';
    if (!this.available) {
      element.innerHTML = '<div class="map-fallback"><div><b>Map could not be loaded.</b><br><span class="small">Location details are still shown below.</span></div></div>';
      return;
    }
    this.map = L.map(element, { zoomControl: true, attributionControl: true });
    L.tileLayer(this.config.tile_url, { maxZoom: 19, attribution: this.config.attribution }).addTo(this.map);
    this.map.setView([20.5937, 78.9629], 5); // India overview until real data arrives
  }

  function pin(color, label) {
    return L.divIcon({
      className: '',
      html: '<div style="width:30px;height:30px;border-radius:50%;background:' + color + ';border:3px solid #fff;box-shadow:0 0 0 6px ' + color + '33;display:grid;place-items:center;color:#fff;font:700 13px sans-serif">' + label + '</div>',
      iconSize: [30, 30], iconAnchor: [15, 15]
    });
  }

  TrackMap.prototype.update = function (driver, provider, labels) {
    if (!this.available) return;
    labels = labels || {};
    const points = [];
    if (driver) {
      const ll = [driver.latitude, driver.longitude];
      if (!this.driverMarker) this.driverMarker = L.marker(ll, { icon: pin('#1b8cff', 'D'), title: 'Driver' }).addTo(this.map).bindPopup(labels.driver || 'Reported breakdown location');
      else this.driverMarker.setLatLng(ll);
      points.push(ll);
    }
    if (provider) {
      const ll = [provider.latitude, provider.longitude];
      const color = (provider.stale || provider.base) ? '#8a9bb0' : '#16b889';
      if (!this.providerMarker) this.providerMarker = L.marker(ll, { icon: pin(color, 'P'), title: 'Provider' }).addTo(this.map);
      else { this.providerMarker.setLatLng(ll); this.providerMarker.setIcon(pin(color, 'P')); }
      this.providerMarker.bindPopup(labels.provider || 'Provider (last shared location)');
      points.push(ll);
    } else if (this.providerMarker) {
      this.map.removeLayer(this.providerMarker); this.providerMarker = null;
    }
    if (this.line) { this.map.removeLayer(this.line); this.line = null; }
    if (points.length === 2 && !this.route) {
      this.line = L.polyline(points, { color: '#5ad9ff', weight: 3, dashArray: '6 8', opacity: .8 }).addTo(this.map);
    }
    if (points.length && !this.fitted) {
      if (points.length === 1) this.map.setView(points[0], 14);
      else this.map.fitBounds(points, { padding: [40, 40] });
      this.fitted = true;
    }
  };

  /** Ask the configured OSRM-compatible router for a road route. Resolves to {km, minutes} or null. */
  TrackMap.prototype.routeBetween = async function (from, to) {
    if (!this.available || !this.config.routing_url || !from || !to) return null;
    const key = [from.latitude, from.longitude, to.latitude, to.longitude].map(n => Number(n).toFixed(4)).join(',');
    const now = Date.now();
    if (key === this.lastRouteKey && now - this.lastRouteAt < 60000) return this.lastRouteResult || null;
    this.lastRouteKey = key; this.lastRouteAt = now;
    try {
      const url = this.config.routing_url + '/route/v1/driving/' + from.longitude + ',' + from.latitude + ';' + to.longitude + ',' + to.latitude + '?overview=full&geometries=geojson';
      const res = await fetch(url, { credentials: 'omit' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!data.routes || !data.routes.length) throw new Error('no route');
      const r = data.routes[0];
      if (this.route) this.map.removeLayer(this.route);
      this.route = L.geoJSON(r.geometry, { style: { color: '#2daeff', weight: 5, opacity: .85 } }).addTo(this.map);
      if (this.line) { this.map.removeLayer(this.line); this.line = null; }
      this.lastRouteResult = { km: r.distance / 1000, minutes: r.duration / 60 };
      return this.lastRouteResult;
    } catch (e) {
      this.lastRouteResult = null;
      return null;
    }
  };

  window.RSATrackMap = TrackMap;
})();
