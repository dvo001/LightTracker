# LightTracking – Failure Modes and Effects Analysis (FMEA)

Dieses Dokument beschreibt **typische Fehlerzustände**, ihre Ursachen, Auswirkungen
und die vorgesehenen **Gegenmaßnahmen / Fallbacks**.

---

## 1) Netzwerk & MQTT

### Fehler: MQTT Broker nicht erreichbar
**Ursachen**
- Broker nicht gestartet
- Netzwerkproblem
- Falsche IP/Port

**Auswirkung**
- Keine Status-/Range-Daten
- Tracking nicht möglich

**Erkennung**
- mqtt_ok = false
- reconnect counter steigt
- event_log WARN/ERROR

**Maßnahmen**
- System bleibt in SETUP
- LIVE wird geblockt
- Automatischer Reconnect mit Backoff

---

### Fehler: MQTT Paketverlust / Jitter
**Ursachen**
- WLAN-Interferenzen
- Überlastetes Netz

**Auswirkung**
- STALE Phasen
- Tracking-Jitter

**Erkennung**
- häufige STALE States
- erhöhte resid_m

**Maßnahmen**
- Freeze bei STALE
- tracking_hz reduzieren
- Ethernet bevorzugen

---

## 2) Anchors / Tags

### Fehler: Anchor OFFLINE
**Ursachen**
- Strom weg
- Firmware Crash
- WLAN verloren

**Auswirkung**
- Weniger Ranges
- Tracking evtl. degradiert

**Erkennung**
- DeviceRegistry setzt status OFFLINE
- anchors_online < erwartet

**Maßnahmen**
- Weiterbetrieb, solange >= min Anchors
- Unter min: LIVE → SAFE

---

### Fehler: Tag OFFLINE
**Auswirkung**
- Kein Tracking

**Maßnahmen**
- Freeze
- Operator entscheidet SAFE

---

## 3) Tracking / Trilateration

### Fehler: Unlösbare Geometrie
**Ursachen**
- Collineare Anchors
- Falsche Positionen
- NLOS Effekte

**Auswirkung**
- Solver liefert None
- STALE/LOST

**Erkennung**
- resid_m > threshold
- outliers Liste gefüllt

**Maßnahmen**
- Solver bricht ab
- State STALE/LOST
- Keine DMX Bewegung

---

### Fehler: Ausreißer-Ranges
**Ursachen**
- NLOS
- Reflektionen

**Maßnahmen**
- Residual-Gating
- Outlier Removal (drop worst)
- Kalibrierung prüfen

---

## 4) Kalibrierung

### Fehler: Calibration FAILED
**Ursachen**
- Zu wenige Samples
- Instabile Ranges
- Falsche Anchor-Positionen

**Auswirkung**
- LIVE gesperrt

**Maßnahmen**
- Ursachen beheben
- Calibration neu starten

---

### Fehler: Anchor-Position nach Calibration geändert
**Auswirkung**
- Calibration invalid

**Maßnahmen**
- invalidate_calibrations()
- erneute Calibration erforderlich

---

## 5) DMX / Output

### Fehler: UART/RS485 Sendefehler
**Ursachen**
- Falsches Device
- Verkabelungsfehler
- Transceiver defekt

**Auswirkung**
- Keine oder falsche Lichtbewegung

**Erkennung**
- Exception im Driver
- event_log ERROR

**Maßnahmen**
- DMX Engine meldet Fehler
- System → SAFE
- Freeze

---

### Fehler: Unkontrollierte Bewegung (Worst Case)
**Prävention**
- DMX nur bei LIVE + TRACKING
- Freeze bei STALE/LOST
- Slew Limiter aktiv

---

## 6) Operator Errors

### Fehler: LIVE ohne Readiness
**Prävention**
- Guards blockieren LIVE

### Fehler: Anchor-Position im LIVE geändert
**Prävention**
- UI sperrt Änderungen
- Backend invalidiert Calibration

---

## 7) Zusammenfassung
LightTracking ist **fail-safe by design**:
- Fehler führen zu Freeze oder SAFE
- Keine Bewegung ohne valide Position
- Operator behält Kontrolle
