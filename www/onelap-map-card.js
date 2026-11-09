/**
 * Onelap Map Card
 * ----------------
 * A custom Lovelace card that shows an Onelap vehicle's live position on a
 * Leaflet map, together with a breadcrumb trail built from Home Assistant's
 * recorded location history.
 *
 * Usage (after registering this file as a dashboard resource):
 *
 *   type: custom:onelap-map-card
 *   entity: device_tracker.apache        # your Onelap tracker entity
 *   title: My Car                        # optional
 *   hours_to_show: 12                    # optional, default 6
 *   default_zoom: 15                     # optional, default 15
 *   aspect_ratio: "16:9"                 # optional card height ratio
 *   follow: true                         # optional, recenter on updates
 *
 * No build step required — vanilla web component, Leaflet loaded from CDN.
 */

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

let _leafletPromise = null;

function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (_leafletPromise) return _leafletPromise;

  _leafletPromise = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = LEAFLET_CSS;
      document.head.appendChild(link);
    }
    const script = document.createElement("script");
    script.src = LEAFLET_JS;
    script.onload = () => resolve(window.L);
    script.onerror = () => reject(new Error("Failed to load Leaflet"));
    document.head.appendChild(script);
  });
  return _leafletPromise;
}

class OnelapMapCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._map = null;
    this._marker = null;
    this._trail = null;
    this._lastEntity = null;
    this._lastHistoryFetch = 0;
    this._history = [];
    this._ready = false;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("You must set an 'entity' (your Onelap device_tracker).");
    }
    this._config = {
      hours_to_show: 6,
      default_zoom: 15,
      follow: true,
      aspect_ratio: "16:9",
      ...config,
    };
    this._render();
  }

  getCardSize() {
    return 6;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._ready) {
      this._update();
    }
  }

  _render() {
    const [w, h] = String(this._config.aspect_ratio || "16:9")
      .split(":")
      .map(Number);
    const ratio = w && h ? (h / w) * 100 : 56.25;

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 12px 16px 8px; font-weight: 500; font-size: 1.1rem;
        }
        .meta { font-size: 0.8rem; color: var(--secondary-text-color); font-weight: 400; }
        .map-wrap { position: relative; width: 100%; padding-top: ${ratio}%; }
        #map {
          position: absolute; inset: 0; width: 100%; height: 100%;
          background: var(--card-background-color);
        }
        .badge {
          position: absolute; z-index: 500; bottom: 10px; left: 10px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #000);
          border-radius: 10px; padding: 6px 10px; font-size: 0.8rem;
          box-shadow: 0 1px 4px rgba(0,0,0,0.3); line-height: 1.35;
        }
        .badge b { font-weight: 600; }
        .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; }
        .vehicle-marker {
          font-size: 30px; line-height: 30px; text-align: center;
          filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5));
          transition: transform 0.4s ease;
        }
        .error { padding: 16px; color: var(--error-color, #c00); }
      </style>
      <ha-card>
        <div class="header">
          <span class="title"></span>
          <span class="meta"></span>
        </div>
        <div class="map-wrap">
          <div id="map"></div>
          <div class="badge" hidden></div>
        </div>
      </ha-card>
    `;

    this._titleEl = this.shadowRoot.querySelector(".title");
    this._metaEl = this.shadowRoot.querySelector(".meta");
    this._badgeEl = this.shadowRoot.querySelector(".badge");
    this._mapEl = this.shadowRoot.getElementById("map");
    this._titleEl.textContent =
      this._config.title || this._config.entity;

    loadLeaflet()
      .then((L) => this._initMap(L))
      .catch((err) => {
        this._mapEl.parentElement.innerHTML =
          `<div class="error">${err.message}</div>`;
      });
  }

  _initMap(L) {
    this._L = L;
    this._map = L.map(this._mapEl, {
      zoomControl: true,
      attributionControl: true,
    }).setView([20.5937, 78.9629], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(this._map);

    this._trail = L.polyline([], {
      color: "#03a9f4",
      weight: 4,
      opacity: 0.8,
    }).addTo(this._map);

    this._ready = true;
    // Leaflet needs a size recalc once it's actually visible.
    setTimeout(() => this._map && this._map.invalidateSize(), 200);
    this._update(true);
  }

  async _update(force = false) {
    if (!this._hass || !this._ready) return;
    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];
    if (!stateObj) {
      this._metaEl.textContent = "entity not found";
      return;
    }

    const a = stateObj.attributes;
    const lat = a.latitude;
    const lon = a.longitude;

    // Refresh history at most once a minute (or on first paint).
    const now = Date.now();
    if (force || now - this._lastHistoryFetch > 60000) {
      this._lastHistoryFetch = now;
      await this._fetchHistory(entityId);
    }

    if (typeof lat !== "number" || typeof lon !== "number") {
      this._metaEl.textContent = "no GPS fix yet";
      return;
    }

    const L = this._L;
    const heading = typeof a.course === "number" ? a.course : 0;

    if (!this._marker) {
      const icon = L.divIcon({
        className: "",
        html: `<div class="vehicle-marker" style="transform: rotate(${heading}deg)">➤</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
      });
      this._marker = L.marker([lat, lon], { icon }).addTo(this._map);
      this._map.setView([lat, lon], this._config.default_zoom);
    } else {
      this._marker.setLatLng([lat, lon]);
      const el = this._marker.getElement();
      if (el) {
        const inner = el.querySelector(".vehicle-marker");
        if (inner) inner.style.transform = `rotate(${heading}deg)`;
      }
      if (this._config.follow) {
        this._map.panTo([lat, lon], { animate: true });
      }
    }

    // Draw the trail (history + current point).
    const line = [...this._history];
    line.push([lat, lon]);
    this._trail.setLatLngs(line);

    this._updateBadge(stateObj);
  }

  _updateBadge(stateObj) {
    const a = stateObj.attributes;
    const online = (a.status || "").toLowerCase() === "online";
    const speed = typeof a.speed_kmph === "number" ? a.speed_kmph : null;
    const ign = a.ignition;
    const parts = [];
    parts.push(
      `<span class="dot" style="background:${online ? "#43a047" : "#9e9e9e"}"></span>` +
        `<b>${a.vehicle_number || stateObj.attributes.friendly_name || "Vehicle"}</b>`
    );
    if (speed !== null) parts.push(`${speed} km/h`);
    if (ign !== undefined) parts.push(`ignition ${ign ? "on" : "off"}`);
    this._badgeEl.innerHTML = parts.join("<br>");
    this._badgeEl.hidden = false;

    const when = a.gps_time || a.last_update;
    this._metaEl.textContent = when
      ? `updated ${this._timeAgo(when)}`
      : (stateObj.state || "");
  }

  _timeAgo(iso) {
    const t = new Date(iso).getTime();
    if (isNaN(t)) return iso;
    const s = Math.round((Date.now() - t) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    if (s < 86400) return `${Math.round(s / 3600)}h ago`;
    return `${Math.round(s / 86400)}d ago`;
  }

  async _fetchHistory(entityId) {
    try {
      const end = new Date();
      const start = new Date(
        end.getTime() - this._config.hours_to_show * 3600 * 1000
      );
      const path =
        `history/period/${start.toISOString()}` +
        `?filter_entity_id=${entityId}` +
        `&minimal_response&no_attributes=false&end_time=${encodeURIComponent(
          end.toISOString()
        )}`;
      const result = await this._hass.callApi("GET", path);
      const series = Array.isArray(result) && result.length ? result[0] : [];
      const pts = [];
      for (const s of series) {
        const at = s.attributes || {};
        if (typeof at.latitude === "number" && typeof at.longitude === "number") {
          pts.push([at.latitude, at.longitude]);
        }
      }
      this._history = pts;
    } catch (err) {
      // History is a nice-to-have; keep the live marker working regardless.
      this._history = [];
    }
  }

  static getConfigElement() {
    return document.createElement("onelap-map-card-editor");
  }

  static getStubConfig(hass) {
    const tracker = Object.keys(hass.states).find((e) =>
      e.startsWith("device_tracker.")
    );
    return { entity: tracker || "device_tracker.onelap_vehicle", hours_to_show: 6 };
  }
}

customElements.define("onelap-map-card", OnelapMapCard);

// Register the card in the UI picker.
window.customCards = window.customCards || [];
window.customCards.push({
  type: "onelap-map-card",
  name: "Onelap Map Card",
  preview: false,
  description: "Live map + location history trail for an Onelap vehicle tracker.",
});

console.info(
  "%c ONELAP-MAP-CARD %c v1.0.0 ",
  "color:white;background:#03a9f4;font-weight:700;",
  "color:#03a9f4;background:white;"
);
