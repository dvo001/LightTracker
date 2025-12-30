# LightTracking – INSTALL QUICKSTART (1-Seiter)

Diese Kurzanleitung bringt ein **bereits vorbereitetes System** schnell in Betrieb.

---

## 1) Raspberry Pi starten
- Raspberry Pi 5 einschalten
- Netzwerk verbunden (Ethernet bevorzugt)

## 2) Service prüfen
```bash
sudo systemctl status lighttracking
```
Falls nicht aktiv:
```bash
sudo systemctl start lighttracking
```

## 3) API prüfen
```bash
curl http://localhost:8000/api/v1/state
```
Erwartung:
```json
{ "system_state": "SETUP", "readiness": { ... } }
```

## 4) MQTT prüfen
```bash
mosquitto_sub -t 'dev/+/status' -v
```
Anchors/Tags einschalten → Statusmeldungen sichtbar.

## 5) Setup (Kurzform)
1. Anchor-Positionen setzen (`/api/v1/anchors`)
2. Fixtures konfigurieren
3. Kalibrieren (`/api/v1/calibration/start`)
4. LIVE_CHECKLIST.md durchgehen
5. `POST /api/v1/state -> LIVE`

## 6) Notfall
```bash
curl -X POST http://localhost:8000/api/v1/state -d '{"target_state":"SAFE"}'
```

---

👉 Details siehe:
- PI_INSTALLATION_GUIDE.md
- LIVE_CHECKLIST.md
