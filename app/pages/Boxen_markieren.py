import csv
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from PIL import ImageDraw

from lego_scanner.preprocessing import boxes as bx
from lego_scanner.preprocessing import sorting

PER_PAGE = 12
EDIT_SIZE = 850
COLORS = {"auto": (255, 140, 0), "ok": (0, 170, 60)}

st.set_page_config(page_title="Boxen markieren", layout="wide")

with st.sidebar:
    st.header("Ordner")
    sorted_dir = Path(st.text_input("Sortierte Fotos", "data/real/sorted")).expanduser()
    per_row = st.slider("Bilder pro Zeile", 3, 8, 6)

labels = sorted_dir / sorting.LABELS_FILE
if not labels.is_file():
    st.error(f"Keine `{sorting.LABELS_FILE}` in `{sorted_dir}` gefunden.")
    st.stop()
with labels.open(newline="") as f:
    files = [
        r["file"]
        for r in csv.DictReader(f)
        if r["part"] != sorting.UNCLEAR and (sorted_dir / r["file"]).is_file()
    ]


@st.cache_data(max_entries=300)
def photo(path: str, size: int):
    return sorting.load_photo(Path(path), max_size=size)


boxes = bx.load_boxes(sorted_dir)
missing = [f for f in files if f not in boxes]
if missing:
    bar = st.progress(0.0, text="Boxen werden vorgeschlagen …")
    for i, file in enumerate(missing, 1):
        boxes[file] = bx.suggest_box(sorted_dir / file) or bx.Box(0.3, 0.3, 0.7, 0.7)
        bar.progress(i / len(missing), text=f"Boxen werden vorgeschlagen … {i}/{len(missing)}")
    bx.save_boxes(sorted_dir, boxes)
    bar.empty()


def confirm(page: list[str]):
    current = bx.load_boxes(sorted_dir)
    for file in page:
        current[file].status = "ok"
    bx.save_boxes(sorted_dir, current)


def start_edit(file: str):
    st.session_state["edit"] = file


def save_edit(file: str, box: bx.Box):
    current = bx.load_boxes(sorted_dir)
    current[file] = box
    bx.save_boxes(sorted_dir, current)
    st.session_state["edit"] = None


def cancel_edit():
    st.session_state["edit"] = None


def thumbnail(file: str, box: bx.Box):
    img = photo(str(sorted_dir / file), 800).copy()
    x0, y0, x1, y1 = box.pixels(*img.size)
    ImageDraw.Draw(img).rectangle((x0, y0, x1, y1), outline=COLORS[box.status], width=3)
    half = max(x1 - x0, y1 - y0) * 0.9 + 30
    half = min(half, min(img.size) / 2)
    cx = min(max((x0 + x1) / 2, half), img.width - half)
    cy = min(max((y0 + y1) / 2, half), img.height - half)
    return img.crop((round(cx - half), round(cy - half), round(cx + half), round(cy + half)))


done = sum(boxes[f].status == "ok" for f in files)
with st.sidebar:
    st.header("Fortschritt")
    st.metric("Geprüfte Boxen", f"{done} / {len(files)}")
    st.progress(done / len(files) if files else 1.0)
    st.caption("Orange = Vorschlag, noch nicht geprüft. Grün = geprüft.")

st.title("Boxen markieren")

edit = st.session_state.get("edit")
if edit in boxes:
    box = boxes[edit]
    st.subheader(f"Box korrigieren: {edit}")
    st.caption("Mit der Maus ein Rechteck um den ganzen Stein ziehen (ohne Schatten), dann „Speichern“.")
    full = st.toggle("Ganzes Foto zeigen", key=f"full_{edit}", help="Falls der Stein im Ausschnitt nicht zu sehen ist")

    img = photo(str(sorted_dir / edit), 1600)
    w, h = img.size
    if full:
        region = (0, 0, w, h)
    else:
        x0, y0, x1, y1 = box.pixels(w, h)
        half = min(max(x1 - x0, y1 - y0) * 1.5 + 0.05 * w, min(w, h) / 2)
        cx = min(max((x0 + x1) / 2, half), w - half)
        cy = min(max((y0 + y1) / 2, half), h - half)
        region = (round(cx - half), round(cy - half), round(cx + half), round(cy + half))
    view = img.crop(region)
    view.thumbnail((EDIT_SIZE, EDIT_SIZE))
    scale = view.width / (region[2] - region[0])

    def to_view(px: float, py: float) -> tuple[float, float]:
        return (px - region[0]) * scale, (py - region[1]) * scale

    bx0, by0 = to_view(box.x_min * w, box.y_min * h)
    bx1, by1 = to_view(box.x_max * w, box.y_max * h)
    fig = go.Figure(go.Image(z=np.asarray(view), hoverinfo="skip"))
    fig.add_shape(type="rect", x0=bx0, y0=by0, x1=bx1, y1=by1, line=dict(color="orange", width=2, dash="dash"))
    fig.update_layout(
        dragmode="select",
        width=view.width,
        height=view.height,
        margin=dict(l=0, r=0, t=0, b=0),
        newselection=dict(line=dict(color="lime", width=2)),
    )
    fig.update_xaxes(visible=False, range=[0, view.width])
    fig.update_yaxes(visible=False, range=[view.height, 0])
    event = st.plotly_chart(
        fig,
        key=f"plot_{edit}_{full}",
        on_select="rerun",
        selection_mode="box",
        width="content",
        config={"displayModeBar": False},
    )

    new_box = None
    selected = event.selection.box if event else []
    if selected:
        xs, ys = sorted(selected[-1]["x"]), sorted(selected[-1]["y"])

        def to_rel(vx: float, vy: float) -> tuple[float, float]:
            px, py = region[0] + vx / scale, region[1] + vy / scale
            return min(max(px / w, 0.0), 1.0), min(max(py / h, 0.0), 1.0)

        (nx0, ny0), (nx1, ny1) = to_rel(xs[0], ys[0]), to_rel(xs[1], ys[1])
        if nx1 - nx0 > 0.003 and ny1 - ny0 > 0.003:
            new_box = bx.Box(nx0, ny0, nx1, ny1, "ok")

    c1, c2, c3 = st.columns([1, 1, 3])
    if new_box:
        c1.button("Speichern", type="primary", on_click=save_edit, args=(edit, new_box), width="stretch")
        c3.caption("Grünes Rechteck wird gespeichert.")
    else:
        keep = bx.Box(box.x_min, box.y_min, box.x_max, box.y_max, "ok")
        c1.button("Alte Box passt doch", on_click=save_edit, args=(edit, keep), width="stretch")
        c3.caption("Noch kein neues Rechteck gezogen.")
    c2.button("Abbrechen", on_click=cancel_edit, width="stretch")
    st.divider()

mode = st.radio("Anzeigen", ["Ungeprüfte", "Alle"], horizontal=True, label_visibility="collapsed")
pool = [f for f in files if mode == "Alle" or boxes[f].status != "ok"]

if not pool:
    st.success("Alle Boxen sind geprüft. Fertig!")
    st.stop()

if mode == "Alle":
    pages = (len(pool) + PER_PAGE - 1) // PER_PAGE
    page_no = st.number_input("Seite", 1, pages, 1)
    page = pool[(page_no - 1) * PER_PAGE : page_no * PER_PAGE]
else:
    page = pool[:PER_PAGE]
    st.caption(f"Noch {len(pool)} ungeprüft. Box falsch? „Korrigieren“ anklicken. Sonst unten alle bestätigen.")

for start in range(0, len(page), per_row):
    for col, file in zip(st.columns(per_row), page[start : start + per_row]):
        with col:
            st.image(thumbnail(file, boxes[file]), caption=file, width="stretch")
            st.button("Korrigieren", key=f"edit_{file}", on_click=start_edit, args=(file,), width="stretch")

unchecked = [f for f in page if boxes[f].status != "ok"]
if unchecked:
    st.button(
        f"Alle {len(unchecked)} Boxen auf dieser Seite passen ✓",
        type="primary",
        on_click=confirm,
        args=(unchecked,),
    )
