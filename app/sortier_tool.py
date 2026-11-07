import re
from pathlib import Path

import streamlit as st

from lego_scanner.preprocessing import sorting

GROUP_SIZE = 3

st.set_page_config(page_title="Lego-Sortierer", layout="wide")

with st.sidebar:
    st.header("Ordner")
    render_dir = Path(st.text_input("Renders (Ordner pro Teil)", "data/renders")).expanduser()
    unsorted_dir = Path(st.text_input("Unsortierte Fotos", "data/real/unsorted")).expanduser()
    sorted_dir = Path(st.text_input("Ziel für sortierte Fotos", "data/real/sorted")).expanduser()
    thumb_cols = st.slider("Vergleichsbilder pro Zeile", 4, 12, 6)

parts = sorting.list_parts(render_dir)
photos = sorting.list_unsorted(unsorted_dir)

if not parts:
    st.error(f"Keine Teile-Ordner in `{render_dir}` gefunden.")
    st.stop()


@st.cache_data
def references(render_dir: str, parts: tuple[str, ...]):
    return {p: sorting.reference_image(Path(render_dir), p) for p in parts}


@st.cache_data
def colors(render_dir: str):
    return sorting.list_colors(Path(render_dir)) + ["andere"]


@st.cache_data
def photo_ref(path: str):
    return sorting.photo_thumbnail(Path(path))


@st.cache_data(max_entries=20)
def preview(path: str):
    return sorting.load_photo(Path(path))


refs = references(str(render_dir), tuple(parts))
render_colors = colors(str(render_dir))
extra_colors = st.session_state.setdefault("extra_colors", [])
custom_colors = sorted(
    {c for c in sorting.used_colors(sorted_dir) + extra_colors if c not in render_colors}
)
color_options = render_colors[:-1] + custom_colors + ["andere"]
history: list[list[sorting.Move]] = st.session_state.setdefault("history", [])

with st.sidebar:
    st.header("Fortschritt")
    counts = sorting.count_sorted(sorted_dir)
    done = sum(counts.values())
    st.metric("Sortierte Fotos", done, help="inkl. _unklar")
    st.metric("Offene Fotos", len(photos))
    if done + len(photos):
        st.progress(done / (done + len(photos)))
    with st.expander("Fotos pro Teil"):
        st.dataframe({"Teil": list(counts), "Fotos": list(counts.values())}, hide_index=True)


def selected_group(group: list[Path]) -> tuple[list[Path], list[str]]:
    chosen = [p for p in group if st.session_state.get(widget_key("use", p))]
    views = [st.session_state.get(widget_key("view", p)) or "andere" for p in chosen]
    return chosen, views


def reset_photo_widgets():
    st.session_state["round"] = st.session_state.get("round", 0) + 1


def widget_key(kind: str, photo: Path) -> str:
    return f"{kind}_{st.session_state.get('round', 0)}_{photo.name}"


def do_assign(group: list[Path], part: str):
    chosen, views = selected_group(group)
    if not chosen:
        st.session_state["warn"] = "Mindestens ein Foto anhaken."
        return
    color = st.session_state.get("color") or ""
    history.append(sorting.assign_group(chosen, views, part, color, sorted_dir))
    st.session_state["color"] = None
    reset_photo_widgets()


def do_assign_new(group: list[Path]):
    part = (st.session_state.get("new_part") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", part) or part.startswith((".", "_")):
        st.session_state["warn"] = "Bitte eine gültige Teile-Nummer eintragen (nur Buchstaben, Ziffern, . _ -)."
        return
    before = len(history)
    do_assign(group, part)
    if len(history) > before:
        st.session_state["new_part"] = ""


def do_add_color():
    color = sorting.normalize_color(st.session_state.get("new_color") or "")
    if not re.fullmatch(r"[a-z0-9_]+", color):
        st.session_state["warn"] = "Bitte einen gültigen Farbnamen eintragen (Buchstaben, Ziffern, Leerzeichen)."
        return
    if color not in extra_colors:
        extra_colors.append(color)
    st.session_state["color"] = color
    st.session_state["new_color"] = ""


def do_undo():
    for move in reversed(history.pop()):
        sorting.undo(move, sorted_dir)
    reset_photo_widgets()


if not photos:
    st.success(f"Keine unsortierten Fotos in `{unsorted_dir}`. Fertig!")
    if history:
        st.button("↶ Letzten Stein rückgängig", on_click=do_undo)
    st.stop()

group = photos[:GROUP_SIZE]
views = sorting.default_views(len(group))

st.subheader("1. Fotos desselben Steins anhaken")
st.caption("Hohe Steine: oben, Seite, unten. Flache Steine: nur oben und unten, also das dritte Foto abhaken.")
for col, photo, view in zip(st.columns(GROUP_SIZE), group, views):
    with col:
        st.image(preview(str(photo)), caption=photo.name, width="stretch")
        st.checkbox("gehört zu diesem Stein", value=True, key=widget_key("use", photo))
        st.selectbox(
            "Ansicht",
            sorting.VIEWS,
            index=sorting.VIEWS.index(view),
            key=widget_key("view", photo),
            label_visibility="collapsed",
        )

if warn := st.session_state.pop("warn", None):
    st.warning(warn)

st.subheader("2. Farbe wählen (optional)")
st.radio("Farbe", color_options, index=None, key="color", horizontal=True, label_visibility="collapsed")

with st.expander("Farbe ist nicht dabei? Neue Farbe eintragen"):
    st.caption("Am besten den Namen wie bei Rebrickable, z. B. „Sand Green“. Wird zu sand_green.")
    f1, f2 = st.columns([3, 1])
    f1.text_input("Farbname", key="new_color", label_visibility="collapsed", placeholder="z. B. Sand Green")
    f2.button("Hinzufügen", on_click=do_add_color, width="stretch")

c1, c2, c3 = st.columns([1, 1, 3])
c1.button("Unklar", on_click=do_assign, args=(group, sorting.UNCLEAR), width="stretch")
c2.button("↶ Rückgängig", on_click=do_undo, disabled=not history, width="stretch")
if history:
    last = history[-1]
    c3.caption(f"Zuletzt: {len(last)} Fotos → {last[0].part} {last[0].color}")

st.subheader("3. Teil anklicken")
query = st.text_input("Teile-Nummer filtern", placeholder="z. B. 3001")
extra_parts = [p for p in counts if p not in parts and p != sorting.UNCLEAR]
shown = [p for p in parts + extra_parts if query.strip().lower() in p.lower()]

with st.expander("Teil ist nicht dabei? Neue Teile-Nummer eintragen"):
    st.caption(
        "Nummer wie bei Rebrickable, z. B. 3001 oder 3069b. "
        "Für dieses Teil gibt es keine Renders, es ist also erstmal nur in den echten Fotos."
    )
    n1, n2 = st.columns([3, 1])
    new_part = n1.text_input("Teile-Nummer", key="new_part", label_visibility="collapsed", placeholder="z. B. 3062b")
    n2.button("Zuordnen", on_click=do_assign_new, args=(group,), width="stretch")

for start in range(0, len(shown), thumb_cols):
    cols = st.columns(thumb_cols)
    for col, part in zip(cols, shown[start : start + thumb_cols]):
        with col:
            if refs.get(part) is not None:
                st.image(refs[part], width="stretch")
            elif (own := sorting.photo_for_preview(sorted_dir, part)) is not None:
                st.image(photo_ref(str(own)), width="stretch")
            st.button(part, key=f"part_{part}", on_click=do_assign, args=(group, part), width="stretch")
