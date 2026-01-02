# LightTracking – NOTFALLKARTE (1-Seite)

⚠️ **Diese Karte ist für den LIVE-Betrieb gedacht.**
Im Zweifel immer: **SAFE**.

---

## 🚨 SOFORTMASSNAHMEN (Priorität)

### ❗ Unkontrollierte Bewegung / falsches Follow
1. **SAFE auslösen**
   ```bash
   POST /api/v1/state → SAFE
   ```
2. Fixtures frieren ein
3. Ruhe bewahren

---

## 🔴 HÄUFIGE LIVE-PROBLEME

### Tracking springt / ist instabil
- Ursache:
  - Anchor kurz OFFLINE
  - Ranges instabil
- Maßnahme:
  - Warten (kurz)
  - Wenn anhaltend → **SAFE**

---

### Anchor fällt aus
- ≥ min Anchors:
  - Weiterbetrieb möglich
- < min Anchors:
  - **SAFE**
  - Kein Weiterbetrieb

---

### Tag verloren
- Automatisch Freeze
- Entscheidung:
  - warten (kurz)
  - oder **SAFE**

---

### DMX reagiert nicht
- Ursache:
  - RS485 Fehler
  - Fixture Problem
- Maßnahme:
  - **SAFE**
  - Manuelles Licht übernehmen

---

## 🟡 WAS MAN NICHT TUN DARF (LIVE)

- ❌ Anchor-Positionen ändern
- ❌ Calibration starten
- ❌ System neu starten
- ❌ Kabel umstecken

---

## 🟢 NACH SAFE

- Licht ist eingefroren oder in Safe-Scene
- Problem analysieren
- Erst nach Klärung wieder LIVE

---

## 🧠 GRUNDREGEL
> **Keine Bewegung ist besser als falsche Bewegung.**
