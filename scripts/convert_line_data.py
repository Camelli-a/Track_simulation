"""将老师提供的 线路数据.xls 转换为前端可用的 JSON 布局文件。"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
XLS_PATH = ROOT / "线路数据(1).xls"
OUT_PATH = ROOT / "frontend" / "public" / "data" / "line-layout.json"


def read_sheet(name: str) -> pd.DataFrame:
    df = pd.read_excel(XLS_PATH, sheet_name=name, header=None)
    header = df.iloc[3].tolist()
    data = df.iloc[4:].copy()
    data.columns = [str(h) if pd.notna(h) else f"col{i}" for i, h in enumerate(header)]
    return data


def parse_km(value) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper().replace("K", "")
    match = re.match(r"(\d+)\+(\d+(?:\.\d+)?)", text)
    if match:
        return round(float(match.group(1)) * 1000 + float(match.group(2)), 1)
    try:
        return round(float(text) / 100, 1)
    except ValueError:
        return None


def build_seg_topology() -> tuple[dict, list]:
    """从 Seg 表构建拓扑（含正/侧向连接），用于图布局。"""
    seg_df = read_sheet("Seg表")
    invalid = 65535
    segs: dict[int, dict] = {}

    for _, row in seg_df.iterrows():
        if pd.isna(row.get("索引编号")):
            continue
        sid = int(row["索引编号"])
        segs[sid] = {
            "seg_id": sid,
            "length_m": round(float(row["长度（cm)"]) / 100, 1),
            "start_type": int(row["起点端点类型"]),
            "start_id": int(row["起点端点编号"]),
            "end_type": int(row["终点端点类型"]),
            "end_id": int(row["终点端点编号"]),
            "end_fwd": int(row["终点正向相邻点SegID"]),
            "end_lat": int(row["终点侧向相邻点SegID"]),
        }

    return segs, _layout_graph(segs, invalid)


def _layout_graph(segs: dict, invalid: int) -> dict:
    """BFS 拓扑布局：正线水平展开，侧线向上下分支。"""
    from collections import deque

    scale = 0.035  # px / m
    branch_dy = 85
    base_y = 280

    edges = []
    nodes: dict[str, dict] = {}
    visited: set[int] = set()
    queue = deque([(1, 0.0, base_y, 0, "main")])

    while queue:
        seg_id, x, y, level, branch = queue.popleft()
        if seg_id in visited or seg_id not in segs:
            continue
        visited.add(seg_id)

        seg = segs[seg_id]
        length_px = max(12.0, seg["length_m"] * scale)
        x2 = x + length_px

        edges.append(
            {
                "seg_id": seg_id,
                "x1": round(x, 1),
                "y1": round(y, 1),
                "x2": round(x2, 1),
                "y2": round(y, 1),
                "length_m": seg["length_m"],
                "branch": branch,
            }
        )

        sk = f"{seg['start_type']}-{seg['start_id']}"
        ek = f"{seg['end_type']}-{seg['end_id']}"
        nodes[sk] = {"id": sk, "x": round(x, 1), "y": round(y, 1), "kind": "junction"}
        nodes[ek] = {"id": ek, "x": round(x2, 1), "y": round(y, 1), "kind": "junction"}

        if seg["end_fwd"] != invalid and seg["end_fwd"] not in visited:
            queue.append((seg["end_fwd"], x2, y, level, "main"))
        if seg["end_lat"] != invalid and seg["end_lat"] not in visited:
            dy = y - branch_dy if level % 2 == 0 else y + branch_dy
            queue.append((seg["end_lat"], x2, dy, level + 1, "branch"))

    max_x = max((e["x2"] for e in edges), default=800)
    max_y = max((e["y1"] for e in edges), default=base_y)
    min_y = min((e["y1"] for e in edges), default=base_y)

    return {
        "edges": edges,
        "nodes": list(nodes.values()),
        "width": round(max_x + 120, 1),
        "height": round(max_y - min_y + 160, 1),
        "placed_seg_count": len(edges),
        "total_seg_count": len(segs),
    }


def build_seg_linear_map(segs_topo: dict) -> dict:
    """保留线性里程映射（用于趋势图、MA 等）。"""
    cum_cm = 0.0
    linear = {}
    for sid in sorted(segs_topo.keys()):
        length_cm = segs_topo[sid]["length_m"] * 100
        linear[sid] = {
            "seg_id": sid,
            "length_m": segs_topo[sid]["length_m"],
            "start_m": round(cum_cm / 100, 1),
        }
        cum_cm += length_cm
    return linear


def seg_offset_to_m(segs: dict, seg_id, offset_cm) -> float:
    seg_id = int(seg_id)
    offset_m = float(offset_cm) / 100
    base = segs.get(seg_id, {}).get("start_m", 0.0)
    return round(base + offset_m, 1)


def build_stations(platforms: list[dict], st_df: pd.DataFrame) -> list[dict]:
    stations = []
    for _, row in st_df.iterrows():
        if pd.isna(row.get("车站ID")):
            continue
        sid = int(row["车站ID"])
        name = str(row["车站名称"])
        platform_ids = []
        for col in row.index:
            if "站台编号" in str(col):
                val = row[col]
                if pd.notna(val) and int(val) != 65535:
                    platform_ids.append(int(val))
        matched = [p for p in platforms if p["platform_id"] in platform_ids]
        if not matched:
            continue
        stations.append(
            {
                "station_id": f"ST-{sid:02d}",
                "name": name,
                "position": min(p["position_m"] for p in matched),
                "seg_id": matched[0].get("seg_id"),
            }
        )
    return sorted(stations, key=lambda s: s["position"])


def main() -> None:
    segs_topo, graph = build_seg_topology()
    segs = build_seg_linear_map(segs_topo)

    plat_df = read_sheet("站台表")
    platforms = []
    for _, row in plat_df.iterrows():
        if pd.isna(row.get("站台ID")):
            continue
        pos = parse_km(row["站台中心公里标"])
        if pos is None:
            continue
        platforms.append(
            {
                "platform_id": int(row["站台ID"]),
                "position_m": pos,
                "seg_id": int(row["关联seg编号"]) if pd.notna(row.get("关联seg编号")) else None,
            }
        )

    st_df = read_sheet("车站表")
    stations = build_stations(platforms, st_df)

    logic_df = read_sheet("逻辑区段表")
    blocks = []
    for _, row in logic_df.iterrows():
        if pd.isna(row.get("索引编号")):
            continue
        start = seg_offset_to_m(segs, row["起点所处Seg编号"], row["起点所处Seg偏移量"])
        end = seg_offset_to_m(segs, row["终点所处Seg编号"], row["终点所处Seg偏移量"])
        if end < start:
            start, end = end, start
        blocks.append(
            {
                "segment_id": str(row["名称"]),
                "track_seg_id": int(row["起点所处Seg编号"]),
                "start": start,
                "end": end,
                "length_m": round(end - start, 1),
            }
        )

    sig_df = read_sheet("信号机表")
    signals = []
    for _, row in sig_df.iterrows():
        if pd.isna(row.get("索引编号")):
            continue
        signals.append(
            {
                "signal_id": str(row["名称"]),
                "position": seg_offset_to_m(segs, row["所处Seg编号"], row["所处Seg偏移量（cm）"]),
                "signal_type": int(row["类型"]) if pd.notna(row.get("类型")) else 0,
            }
        )

    turn_df = read_sheet("道岔表")
    turnouts = []
    for _, row in turn_df.iterrows():
        if pd.isna(row.get("索引编号")):
            continue
        merge_seg = int(row["汇合SegID"]) if pd.notna(row.get("汇合SegID")) else None
        pos = segs.get(merge_seg, {}).get("start_m", 0.0) if merge_seg else 0.0
        turnouts.append(
            {
                "turnout_id": str(row["名称"]),
                "position": pos,
                "merge_seg_id": merge_seg,
                "normal_seg": int(row["定位SegID"]) if pd.notna(row.get("定位SegID")) else None,
                "reverse_seg": int(row["反位SegID"]) if pd.notna(row.get("反位SegID")) else None,
            }
        )

    # 道岔节点坐标：落在对应 merge_seg 的 edge 终点
    edge_by_seg = {e["seg_id"]: e for e in graph["edges"]}
    for t in turnouts:
        e = edge_by_seg.get(t.get("merge_seg_id"))
        if e:
            t["graph_x"] = e["x2"]
            t["graph_y"] = e["y2"]

    for st in stations:
        e = edge_by_seg.get(st.get("seg_id"))
        if e:
            st["graph_x"] = round((e["x1"] + e["x2"]) / 2, 1)
            st["graph_y"] = e["y1"] - 28

    slope_df = read_sheet("坡度表")
    profile = []
    for _, row in slope_df.iterrows():
        if pd.isna(row.get("索引编号")):
            continue
        profile.append(
            {
                "position": seg_offset_to_m(
                    segs, row["坡度起点所处seg编号"], row["坡度起点所处seg偏移量"]
                ),
                "slope": float(row["坡度值"]) if pd.notna(row.get("坡度值")) else 0.0,
            }
        )
    profile.sort(key=lambda p: p["position"])

    total_length = max(
        [b["end"] for b in blocks]
        + [s["position"] for s in stations]
        + [p["position_m"] for p in platforms]
        + [0.0]
    )

    payload = {
        "source": "线路数据(1).xls",
        "total_length_m": round(total_length, 1),
        "seg_count": len(segs),
        "graph": graph,
        "stations": stations,
        "platforms": platforms,
        "blocks": blocks,
        "signals": signals,
        "turnouts": turnouts,
        "slope_profile": profile,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(
        f"total={payload['total_length_m']}m stations={len(stations)} "
        f"blocks={len(blocks)} graph_edges={graph['placed_seg_count']}/{graph['total_seg_count']}"
    )


if __name__ == "__main__":
    main()
