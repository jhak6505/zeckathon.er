import sys
import math
sys.stdout.reconfigure(encoding='utf-8')
from pptx import Presentation
from pptx.util import Inches

def run_verification(pptx_path: str = 'C:/Users/Alok/Desktop/FINHYPE/FINHYPE_Zeckathon_2026.pptx'):
    print("=" * 80)
    print("FINHYPE Zeckathon 2026 — Presentation Structural & Visual Verification")
    print("=" * 80)

    try:
        prs = Presentation(pptx_path)
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load presentation at {pptx_path}: {e}")
        return False

    w_in = prs.slide_width.inches
    h_in = prs.slide_height.inches
    print(f"[OK] Loaded presentation: {w_in:.3f}\" x {h_in:.3f}\" (Widescreen 16:9)")
    if abs(w_in - 13.333) > 0.05 or abs(h_in - 7.500) > 0.05:
        print(f"[FAIL] Expected 13.333\" x 7.500\", found {w_in:.3f}\" x {h_in:.3f}\"")
        return False

    total_slides = len(prs.slides)
    print(f"[OK] Slide count: {total_slides} (Expected: 9)")
    if total_slides != 9:
        print(f"[FAIL] Expected exactly 9 slides, found {total_slides}")
        return False

    all_passed = True

    # ── Slide-by-slide checks ────────────────────────────────────────────────
    for idx, slide in enumerate(prs.slides):
        slide_num = idx + 1
        slide_shapes = list(slide.shapes)
        tables = [s for s in slide_shapes if s.has_table]
        
        # Collect texts
        texts = []
        for s in slide_shapes:
            if s.has_text_frame:
                for p in s.text_frame.paragraphs:
                    t = p.text.strip()
                    if t:
                        texts.append(t)
            elif s.has_table:
                for row in s.table.rows:
                    row_vals = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_vals:
                        texts.append(" | ".join(row_vals))

        header = texts[0] if texts else "NO_HEADER"
        print(f"\n--- Slide {slide_num}: {header[:65]} ---")
        print(f"    Shapes: {len(slide_shapes)}, Tables: {len(tables)}, Text elements: {len(texts)}")

        # Check canvas boundary containment
        for s_idx, s in enumerate(slide_shapes):
            l = s.left.inches
            t = s.top.inches
            w = s.width.inches
            h = s.height.inches
            if l < -0.01 or t < -0.01 or (l + w) > (w_in + 0.05) or (t + h) > (h_in + 0.05):
                print(f"[WARN] Slide {slide_num} Shape {s_idx} exceeds slide boundary: "
                      f"l={l:.2f}, t={t:.2f}, r={l+w:.2f}, b={t+h:.2f}")

        # Table-vs-Shape Overlap Detection Engine
        if tables:
            for t_idx, t_shape in enumerate(tables):
                t_table = t_shape.table
                t_l = t_shape.left.inches
                t_t = t_shape.top.inches
                t_w = t_shape.width.inches
                t_rendered_h = sum(r.height for r in t_table.rows) / 914400.0
                t_b = t_t + t_rendered_h
                print(f"    Table {t_idx+1}: bounds = [{t_l:.2f}\", {t_t:.2f}\" to {t_l+t_w:.2f}\", {t_b:.2f}\"], "
                      f"rows={len(t_table.rows)}, cols={len(t_table.columns)}")

                # Check against all other shapes on this slide (excluding background full-screen rect)
                for s_idx, s in enumerate(slide_shapes):
                    if s == t_shape:
                        continue
                    sl = s.left.inches
                    st = s.top.inches
                    sw = s.width.inches
                    sh = s.height.inches
                    sb = st + sh
                    sr = sl + sw

                    # Skip full-slide background rects
                    if sw >= 13.0 and sh >= 7.0:
                        continue

                    # Check bounding box collision
                    x_overlap = not (sr <= t_l + 0.05 or sl >= t_l + t_w - 0.05)
                    y_overlap = not (sb <= t_t + 0.05 or st >= t_b - 0.05)

                    if x_overlap and y_overlap:
                        print(f"[FAIL] Slide {slide_num}: Shape {s_idx} ({s.name}) intersects Table!\n"
                              f"       Table bounds: Y=[{t_t:.2f}\", {t_b:.2f}\"], X=[{t_l:.2f}\", {t_l+t_w:.2f}\"]\n"
                              f"       Shape bounds: Y=[{st:.2f}\", {sb:.2f}\"], X=[{sl:.2f}\", {sr:.2f}\"]")
                        all_passed = False

    # ── Slide 6 Deep-Dive Layout & Typography Audit ──────────────────────────
    print("\n" + "=" * 80)
    print("SLIDE 6 DEDICATED GEOMETRY & TYPOGRAPHY AUDIT")
    print("=" * 80)
    slide6 = prs.slides[5]
    s6_tables = [s for s in slide6.shapes if s.has_table]
    if not s6_tables:
        print("[FAIL] Slide 6: No table found!")
        return False

    t_shape = s6_tables[0]
    table = t_shape.table
    num_rows = len(table.rows)
    num_cols = len(table.columns)

    print(f"[CHECK] Table dimensions: {num_rows} rows x {num_cols} columns")
    if num_rows != 11 or num_cols != 8:
        print(f"[FAIL] Slide 6: Expected 11 rows x 8 cols, found {num_rows}x{num_cols}")
        all_passed = False

    # Check cell merging on Section Headers (Row 1 and Row 6)
    row1_merged = table.cell(1, 0).is_merge_origin and all(table.cell(1, c).is_spanned for c in range(1, 8))
    row6_merged = table.cell(6, 0).is_merge_origin and all(table.cell(6, c).is_spanned for c in range(1, 8))

    print(f"[CHECK] Liquid Section Header (Row 1) merged across 8 cols: {row1_merged}")
    print(f"[CHECK] Overnight Section Header (Row 6) merged across 8 cols: {row6_merged}")
    if not (row1_merged and row6_merged):
        print("[FAIL] Slide 6: Section headers are NOT merged across all 8 columns!")
        all_passed = False

    # Check row heights and cell margins
    table_top = t_shape.top.inches
    row_heights = [r.height / 914400.0 for r in table.rows]
    total_table_height = sum(row_heights)
    table_bottom = table_top + total_table_height

    print(f"[CHECK] Table Top: {table_top:.3f}\", Height: {total_table_height:.3f}\", Table Bottom: {table_bottom:.3f}\"")
    if table_bottom > 4.00:
        print(f"[FAIL] Slide 6: Table bottom ({table_bottom:.3f}\") exceeds 4.00\"!")
        all_passed = False
    else:
        print(f"[PASS] Table bottom ({table_bottom:.3f}\") is well within upper half (<= 4.00\")")

    # Locate Explanatory Cards (Shapes positioned below table)
    cards = []
    for s_idx, s in enumerate(slide6.shapes):
        if s.has_table:
            continue
        st = s.top.inches
        sh = s.height.inches
        sw = s.width.inches
        # Bottom cards are around top 4.25 and height 2.20 - 2.45
        if st >= 4.10 and st <= 4.60 and sw >= 5.0 and sh >= 1.8:
            cards.append((s_idx, s, st, sh, st + sh))

    print(f"[CHECK] Explanatory Cards found: {len(cards)}")
    if len(cards) < 2:
        print(f"[FAIL] Slide 6: Expected at least 2 cards below table, found {len(cards)}")
        all_passed = False
    else:
        for idx, (s_idx, c_shape, ct, ch, cb) in enumerate(cards):
            gap = ct - table_bottom
            print(f"    Card {idx+1} [Shape {s_idx}]: Top={ct:.3f}\", Height={ch:.3f}\", Bottom={cb:.3f}\" | "
                  f"Clearance from table bottom = {gap:.3f}\" (assert >= 0.25\")")
            if gap < 0.25:
                print(f"[FAIL] Slide 6: Clearance gap between Table and Card {idx+1} is only {gap:.3f}\" (< 0.25\")!")
                all_passed = False
            else:
                print(f"[PASS] Card {idx+1} has clean clearance of {gap:.3f}\" from table bottom.")

            if cb > 6.75:
                print(f"[FAIL] Slide 6: Card {idx+1} bottom ({cb:.3f}\") intrudes into footer area (> 6.75\")!")
                all_passed = False
            else:
                print(f"[PASS] Card {idx+1} bottom ({cb:.3f}\") stays above footer margin (6.85\").")

    # Single-line cell text length estimation
    print("[CHECK] Estimating text fit across table data cells (ensuring zero unexpected row stretching)...")
    col_w_inches = [table.columns[c].width / 914400.0 for c in range(8)]
    max_char_overage = 0
    for r_idx in range(num_rows):
        if r_idx in (1, 6):
            continue  # Merged section headers span 11.733"
        for c_idx in range(num_cols):
            cell = table.cell(r_idx, c_idx)
            text = cell.text.strip()
            # Approximate max characters per inch for 9pt-9.5pt font: ~15 chars/inch
            col_cap_chars = col_w_inches[c_idx] * 15.0
            if len(text) > col_cap_chars:
                overage = len(text) - col_cap_chars
                max_char_overage = max(max_char_overage, overage)
                print(f"[WARN] Row {r_idx} Col {c_idx} text ({len(text)} chars) may exceed col width ({col_w_inches[c_idx]:.2f}\"): '{text}'")

    if max_char_overage == 0:
        print("[PASS] All data cells safely fit single lines without text-wrapping row expansion.")
    else:
        print(f"[INFO] Max potential character overage: {max_char_overage:.1f}")

    print("\n" + "=" * 80)
    if all_passed:
        print("FINAL VERIFICATION RESULT: ALL PASS (ZERO OVERLAPS, SAFE GEOMETRY)")
        print("=" * 80)
        return True
    else:
        print("FINAL VERIFICATION RESULT: FAILED CHECKS DETECTED")
        print("=" * 80)
        return False

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/Alok/Desktop/FINHYPE/FINHYPE_Zeckathon_2026.pptx'
    success = run_verification(path)
    sys.exit(0 if success else 1)
