# Firmware (Phase 5)

This folder contains minimal Arduino/PlatformIO scaffolding for Anchor and Tag firmware used in Phase 5.

Build examples:

```
pio run -e anchor
pio run -e tag
```

Enable SIM ranges in `platformio.ini` by uncommenting `-DSIM_RANGES` in the `anchor` env.

Configure MQTT host/port via build flags or edit `platformio.ini`.
# Firmware projects (Anchor / Tag)
