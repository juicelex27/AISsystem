import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape


_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_REL_OFFICEDOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_REL_PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"


def _col_name(col_idx: int) -> str:
    # 1 -> A, 26 -> Z, 27 -> AA
    s = ""
    n = col_idx
    while n > 0:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _col_index(col_letters: str) -> int:
    n = 0
    for ch in col_letters:
        if "A" <= ch <= "Z":
            n = n * 26 + (ord(ch) - 64)
        elif "a" <= ch <= "z":
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return n


_INVALID_SHEET_CHARS = re.compile(r"[\[\]\:\*\?\/\\]")


def make_sheet_name(subject_code: str, subject_name: str, subject_id: int, existing: set[str] | None = None) -> str:
    """
    Excel worksheet names are limited to 31 chars and disallow: []:*?/\\
    We embed the subject id so imports can reliably map sheets back to subjects.
    """
    label = (subject_code or "").strip() or (subject_name or "").strip() or "Subject"
    # Put ID first so it survives the 31-char truncation.
    base = f"ID {subject_id} - {label}"
    base = _INVALID_SHEET_CHARS.sub(" ", base).strip()
    if not base:
        base = f"ID {subject_id} - Subject"
    name = base[:31].rstrip()

    if existing is None:
        return name

    # Ensure uniqueness (after truncation) by appending " (2)", " (3)", etc.
    if name not in existing:
        return name
    i = 2
    while True:
        suffix = f" ({i})"
        candidate = (base[: max(0, 31 - len(suffix))].rstrip() + suffix).rstrip()
        if candidate not in existing:
            return candidate
        i += 1


def extract_subject_id_from_sheet_name(sheet_name: str) -> int | None:
    m = re.search(r"\bID\s*(\d+)\b", sheet_name or "", flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def write_xlsx(sheets: list[tuple[str, list[list]]]) -> bytes:
    """
    Minimal XLSX writer (no external deps).
    Each sheet is (sheet_name, rows) where rows is a list of lists.
    Strings are written as inlineStr; numbers as numeric cells.
    """
    # Normalize/unique sheet names
    used: set[str] = set()
    normalized: list[tuple[str, list[list]]] = []
    for name, rows in sheets:
        base = _INVALID_SHEET_CHARS.sub(" ", (name or "").strip()).strip() or "Sheet"
        safe = base[:31].rstrip() or "Sheet"
        if safe in used:
            i = 2
            while True:
                suffix = f" ({i})"
                candidate = (base[: max(0, 31 - len(suffix))].rstrip() + suffix).rstrip() or f"Sheet{i}"
                if candidate not in used:
                    safe = candidate
                    break
                i += 1
        used.add(safe)
        normalized.append((safe, rows))

    def sheet_xml(rows: list[list]) -> bytes:
        out = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"]
        out.append(f"<worksheet xmlns=\"{_NS_MAIN}\">")
        out.append("<sheetData>")
        for r_idx, row in enumerate(rows, start=1):
            if row is None:
                continue
            out.append(f"<row r=\"{r_idx}\">")
            for c_idx, val in enumerate(row, start=1):
                if val is None or val == "":
                    continue
                ref = f"{_col_name(c_idx)}{r_idx}"
                if isinstance(val, bool):
                    # Keep as string (avoid Excel booleans / type issues)
                    sval = "TRUE" if val else "FALSE"
                    sval = _xml_escape(sval)
                    out.append(f"<c r=\"{ref}\" t=\"inlineStr\"><is><t>{sval}</t></is></c>")
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    out.append(f"<c r=\"{ref}\"><v>{val}</v></c>")
                else:
                    sval = str(val)
                    attrs = ""
                    if sval[:1].isspace() or sval[-1:].isspace():
                        attrs = " xml:space=\"preserve\""
                    sval = _xml_escape(sval)
                    out.append(f"<c r=\"{ref}\" t=\"inlineStr\"><is><t{attrs}>{sval}</t></is></c>")
            out.append("</row>")
        out.append("</sheetData>")
        out.append("</worksheet>")
        return "".join(out).encode("utf-8")

    workbook = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"]
    workbook.append(
        f"<workbook xmlns=\"{_NS_MAIN}\" xmlns:r=\"{_NS_REL_OFFICEDOC}\"><sheets>"
    )
    for i, (name, _) in enumerate(normalized, start=1):
        workbook.append(f"<sheet name=\"{_xml_escape(name)}\" sheetId=\"{i}\" r:id=\"rId{i}\"/>")
    workbook.append("</sheets></workbook>")
    workbook_xml = "".join(workbook).encode("utf-8")

    wb_rels = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"]
    wb_rels.append(f"<Relationships xmlns=\"{_NS_REL_PACKAGE}\">")
    for i in range(1, len(normalized) + 1):
        wb_rels.append(
            "<Relationship "
            f"Id=\"rId{i}\" "
            "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" "
            f"Target=\"worksheets/sheet{i}.xml\"/>"
        )
    wb_rels.append(
        "<Relationship "
        "Id=\"rIdStyles\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" "
        "Target=\"styles.xml\"/>"
    )
    wb_rels.append("</Relationships>")
    wb_rels_xml = "".join(wb_rels).encode("utf-8")

    rels = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        f"<Relationships xmlns=\"{_NS_REL_PACKAGE}\">"
        "<Relationship "
        "Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
        "Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    ).encode("utf-8")

    content_types = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"]
    content_types.append("<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">")
    content_types.append("<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>")
    content_types.append("<Default Extension=\"xml\" ContentType=\"application/xml\"/>")
    content_types.append("<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>")
    content_types.append("<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>")
    for i in range(1, len(normalized) + 1):
        content_types.append(
            f"<Override PartName=\"/xl/worksheets/sheet{i}.xml\" "
            "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        )
    content_types.append("</Types>")
    content_types_xml = "".join(content_types).encode("utf-8")

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        f"<styleSheet xmlns=\"{_NS_MAIN}\">"
        "<fonts count=\"1\"><font><sz val=\"11\"/><color theme=\"1\"/><name val=\"Calibri\"/><family val=\"2\"/></font></fonts>"
        "<fills count=\"2\"><fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill></fills>"
        "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
        "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>"
        "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
        "</styleSheet>"
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
        z.writestr("xl/styles.xml", styles_xml)
        for i, (_, rows) in enumerate(normalized, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(rows))
    return buf.getvalue()


def read_xlsx(data: bytes) -> dict[str, list[list]]:
    """
    Minimal XLSX reader (no external deps).
    Returns: {sheet_name: rows_as_lists}
    """
    if not data:
        return {}
    zf = zipfile.ZipFile(io.BytesIO(data), "r")

    def _read_xml(path: str) -> ET.Element:
        return ET.fromstring(zf.read(path))

    shared_strings: list[str] = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = _read_xml("xl/sharedStrings.xml")
        for si in root.findall(f"{{{_NS_MAIN}}}si"):
            # shared strings can be rich text; collect all <t>
            ts = si.findall(f".//{{{_NS_MAIN}}}t")
            shared_strings.append("".join(t.text or "" for t in ts))

    wb = _read_xml("xl/workbook.xml")
    rels = _read_xml("xl/_rels/workbook.xml.rels")
    rel_map: dict[str, str] = {}
    for r in rels.findall(f"{{{_NS_REL_PACKAGE}}}Relationship"):
        rid = r.attrib.get("Id")
        tgt = r.attrib.get("Target")
        if rid and tgt:
            rel_map[rid] = "xl/" + tgt.lstrip("/")

    sheets: list[tuple[str, str]] = []
    for sheet in wb.findall(f".//{{{_NS_MAIN}}}sheet"):
        name = sheet.attrib.get("name") or "Sheet"
        rid = sheet.attrib.get(f"{{{_NS_REL_OFFICEDOC}}}id")
        if not rid or rid not in rel_map:
            continue
        sheets.append((name, rel_map[rid]))

    def _cell_value(c: ET.Element) -> str | float | int | None:
        t = c.attrib.get("t")
        if t == "inlineStr":
            t_el = c.find(f".//{{{_NS_MAIN}}}t")
            return t_el.text if t_el is not None else ""
        v_el = c.find(f"{{{_NS_MAIN}}}v")
        if v_el is None or v_el.text is None:
            return ""
        raw = v_el.text
        if t == "s":
            try:
                return shared_strings[int(raw)]
            except Exception:
                return ""
        # numeric / general
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except Exception:
            return raw

    out: dict[str, list[list]] = {}
    for sheet_name, sheet_path in sheets:
        root = _read_xml(sheet_path)
        rows_by_r: list[tuple[int, dict[int, object]]] = []
        for row in root.findall(f".//{{{_NS_MAIN}}}sheetData/{{{_NS_MAIN}}}row"):
            try:
                r_idx = int(row.attrib.get("r") or "0")
            except Exception:
                r_idx = 0
            if r_idx <= 0:
                continue
            cells: dict[int, object] = {}
            for c in row.findall(f"{{{_NS_MAIN}}}c"):
                ref = c.attrib.get("r") or ""
                m = re.match(r"([A-Za-z]+)(\d+)", ref)
                if not m:
                    continue
                col_idx = _col_index(m.group(1))
                if col_idx <= 0:
                    continue
                cells[col_idx] = _cell_value(c)
            if cells:
                rows_by_r.append((r_idx, cells))
        rows_by_r.sort(key=lambda x: x[0])
        if not rows_by_r:
            out[sheet_name] = []
            continue
        max_col = max((max(cells.keys()) for _, cells in rows_by_r), default=0)
        table: list[list] = []
        for _, cells in rows_by_r:
            row_list = ["" for _ in range(max_col)]
            for c_idx, val in cells.items():
                if 1 <= c_idx <= max_col:
                    row_list[c_idx - 1] = val
            table.append(row_list)
        out[sheet_name] = table
    return out
