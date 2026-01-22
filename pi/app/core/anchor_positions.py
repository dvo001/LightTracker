from typing import Dict, Tuple


def ensure_anchor_offsets_table(db) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS anchor_position_offsets ("
        "mac TEXT PRIMARY KEY,"
        "dx_cm REAL,"
        "dy_cm REAL,"
        "dz_cm REAL,"
        "updated_at_ms INTEGER,"
        "tag_mac TEXT"
        ")"
    )
    db.commit()


def load_anchor_offsets(db) -> Dict[str, Tuple[float, float, float]]:
    ensure_anchor_offsets_table(db)
    rows = db.execute("SELECT mac, dx_cm, dy_cm, dz_cm FROM anchor_position_offsets").fetchall()
    offsets = {}
    for r in rows:
        dx = r["dx_cm"] if r["dx_cm"] is not None else 0.0
        dy = r["dy_cm"] if r["dy_cm"] is not None else 0.0
        dz = r["dz_cm"] if r["dz_cm"] is not None else 0.0
        offsets[r["mac"]] = (dx, dy, dz)
    return offsets


def load_anchor_positions(db, with_offsets: bool = False) -> Dict[str, Tuple[float, float, float]]:
    rows = db.execute("SELECT mac, x_cm, y_cm, z_cm FROM anchor_positions").fetchall()
    base = {r["mac"]: (r["x_cm"], r["y_cm"], r["z_cm"]) for r in rows}
    if not with_offsets:
        return base
    offsets = load_anchor_offsets(db)
    merged = {}
    for mac, pos in base.items():
        dx, dy, dz = offsets.get(mac, (0.0, 0.0, 0.0))
        merged[mac] = (pos[0] + dx, pos[1] + dy, pos[2] + dz)
    return merged
