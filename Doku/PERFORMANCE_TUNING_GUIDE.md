# LightTracking – Performance Tuning Guide

Dieses Dokument hilft, **Tracking-Stabilität und DMX-Flüssigkeit**
für unterschiedliche Bühnengrößen und Hardwarebedingungen zu optimieren.

---

## 1) Wichtige Parameter

### rates.global
| Parameter | Bedeutung | Typisch |
|---------|----------|--------|
| tracking_hz | Tracking Tick | 10–30 |
| dmx_hz | DMX Update Rate | 25–40 |
| ui_hz | UI Refresh | 5–10 |
| stale_timeout_ms | Zeit bis STALE | 300–600 |
| lost_timeout_ms | Zeit bis LOST | 1000–2000 |

---

## 2) Tracking Stabilität

### tracking_hz
- Zu hoch:
  - CPU-Last
  - Jitter
- Zu niedrig:
  - spürbare Latenz

**Empfehlung**
- Kleine Bühne: 20 Hz
- Große Bühne: 15 Hz

---

### Anchor-Anzahl
- Minimum: 4
- Optimal: 5–6 (Redundanz)
- Mehr als 6:
  - kaum Verbesserung
  - mehr MQTT Traffic

---

### Residual Threshold
- resid_max_m:
  - Startwert: 0.3–0.5 m
- Zu klein:
  - häufig STALE
- Zu groß:
  - ungenaue Position

---

## 3) DMX Glättung

### dmx_hz
- 30 Hz → sehr flüssig
- 25 Hz → ausreichend

### Slew Limiter
- pan_slew_deg_s: 90–180
- tilt_slew_deg_s: 60–120

Langsame Werte:
- ruhiger, aber träge
Schnelle Werte:
- reaktionsfreudig, evtl. ruckelig

---

## 4) Netzwerk

### Ethernet vs WLAN
- Ethernet:
  - geringste Latenz
  - stabil
- WLAN:
  - funktioniert, aber störanfälliger

### MQTT QoS
- Ranges: QoS 0 (niedrige Latenz)
- Commands: QoS 1

---

## 5) Raspberry Pi Ressourcen

### CPU
- Pi 5 ausreichend für:
  - 1 Tag
  - 5–6 Anchors
  - 2–4 Fixtures

Bei Engpässen:
- tracking_hz senken
- Logging reduzieren

### Logging
- position_log.hz ≤ 5
- event_log immer an

---

## 6) Raum & Geometrie

- Anchors möglichst nicht coplanar
- Höhenunterschiede nutzen
- Freie Sichtlinie zum Tag bevorzugen

---

## 7) Vorgehen beim Tuning

1. Statisch testen (Tag ruhig)
2. Langsame Bewegung
3. Schnelle Bewegung
4. Tracking_hz feinjustieren
5. Slew Limiter anpassen

---

## 8) Zielzustand
- Ruhige Bewegung
- Keine Sprünge
- STALE selten
- LOST praktisch nie im Normalbetrieb
