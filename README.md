# Onelap Vehicle Tracker — Home Assistant integration

Track your [Onelap](https://onelap.in) GPS vehicle tracker inside Home
Assistant: live position on the map, full location **history**, speed,
direction, ignition and more — plus a ready-to-use **map card** that draws the
vehicle and its recent trail.

It uses Onelap's **public share endpoints**, so all you need is a share link —
no username, password or API key.

![type: device_tracker + sensors + map card](https://github.com/surajbhari/onelap_ha_plugin)

---

## What you get

For every vehicle on the share link:

| Entity | Example | Notes |
|---|---|---|
| `device_tracker.<vehicle>` | on the HA map | latitude/longitude, recorded to history |
| `sensor.<vehicle>_speed` | `45 km/h` | |
| `sensor.<vehicle>_direction` | `217°` | heading / course |
| `sensor.<vehicle>_status` | `online` | |
| `sensor.<vehicle>_satellites` | `15` | GPS satellites in use |
| `sensor.<vehicle>_total_distance` | `4427 km` | odometer |
| `sensor.<vehicle>_last_gps_fix` | timestamp | |
| `sensor.<vehicle>_battery` | `4` | device battery level (bars, diagnostic) |
| `sensor.<vehicle>_gsm_signal` | `4` | cellular signal (bars, diagnostic) |
| `binary_sensor.<vehicle>_ignition` | `on`/`off` | |

The `device_tracker` entity is a standard HA GPS tracker, so its location is
**stored in the recorder** and you can replay the trail with the built-in **Map**
card (`hours_to_show`), the History panel, or the bundled Onelap Map Card below.

---

## 1. Get your share link

1. Open the **Onelap** app (or web dashboard).
2. Share the device you want to track.
3. Copy the link — it looks like:
   `https://r.onelap.in/#/shared?tid=XXXXXX`

You can paste either the **whole link** or just the **tracking id** (`XXXXXX`).

> The link stays valid as long as sharing is enabled in the app. If you revoke
> sharing, the integration stops receiving data.

---

## 2. Install the integration

### Option A — HACS (recommended)

1. HACS → **Integrations** → ⋮ → **Custom repositories**.
2. Add `https://github.com/surajbhari/onelap_ha_plugin` as an **Integration**.
3. Install **Onelap Vehicle Tracker**, then restart Home Assistant.

### Option B — Manual

Copy `custom_components/onelap/` into your Home Assistant
`config/custom_components/` folder and restart.

```
config/
└── custom_components/
    └── onelap/
        ├── __init__.py
        ├── api.py
        ├── ...
```

---

## 3. Add it

**Settings → Devices & Services → Add Integration → Onelap Vehicle Tracker**,
then paste your share link or tracking id.

To change how often it polls Onelap, open the integration's **Configure** button
(default: every 30 s, minimum 10 s).

---

## 4. Show it on a map

### Built-in Map card (zero extra setup)

Add a **Map** card and pick your `device_tracker` entity. Set
`hours_to_show` to draw the historical trail:

```yaml
type: map
entities:
  - device_tracker.apache
hours_to_show: 12
```

### Bundled Onelap Map Card (live marker + trail + speed badge)

This repo ships a custom Lovelace card at
[`www/onelap-map-card.js`](www/onelap-map-card.js).

1. Copy it to `config/www/onelap-map-card.js`.
   (With HACS you can instead add it as a **Lovelace/Dashboard** resource repo.)
2. Register it as a dashboard resource:
   **Settings → Dashboards → ⋮ → Resources → Add**
   - URL: `/local/onelap-map-card.js`
   - Type: **JavaScript Module**
3. Add the card to any dashboard:

```yaml
type: custom:onelap-map-card
entity: device_tracker.apache
title: My Car
hours_to_show: 12
default_zoom: 15
follow: true
```

| Option | Default | Description |
|---|---|---|
| `entity` | — | Your Onelap `device_tracker` (required) |
| `title` | entity id | Card title |
| `hours_to_show` | `6` | How much history to draw as a trail |
| `default_zoom` | `15` | Initial map zoom |
| `follow` | `true` | Recenter the map when the vehicle moves |
| `aspect_ratio` | `16:9` | Card height |

---

## Notes & limitations

- **Speed** is reported by Onelap in knots and converted to km/h by the
  integration (`× 1.852`).
- `0, 0` coordinates are treated as "no fix yet" and ignored.
- This is an unofficial integration built against Onelap's public share API;
  it is not affiliated with or endorsed by Onelap Telematics.
- Location history depends on the Home Assistant **recorder** (enabled by
  default). History retention follows your recorder's `purge_keep_days`.

---

## Troubleshooting

- **"did not return any devices"** — double-check the share link and that
  sharing is still on in the Onelap app.
- **No position** — a brand-new device may not have reported a fix yet; the
  tracker shows as unavailable until the first GPS fix arrives.
- Enable debug logs:

```yaml
logger:
  logs:
    custom_components.onelap: debug
```
