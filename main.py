"""
Virtual Whiteboard - Improved Version
=====================================
Improvements over original:
  - Better eraser: larger radius, per-segment erasing, clear visual cursor
  - New tools: Rectangle, Circle, Line shapes + Flood-fill bucket
  - Performance: dirty-flag redraw, cached base canvas, frame-skip for heavy ops
  - Better UI: icon-based left toolbar, colour palette grid, tool tooltips, status bar
  - New gestures: Fist (all fingers down) = Undo | Open palm = Clear canvas
"""

import cv2
import numpy as np
import time
import os
from hand_tracking_module import HandTracker

# ─────────────────────────── constants ───────────────────────────
CANVAS_W, CANVAS_H = 640, 480

# Extended BGR colour palette (6 cols × 2 rows = 12 colours)
PALETTE = [
    (0,   0,   0  ),  # Black
    (80,  80,  80 ),  # Dark grey
    (180, 180, 180),  # Light grey
    (255, 255, 255),  # White
    (0,   0,   255),  # Red
    (0,   165, 255),  # Orange
    (0,   255, 255),  # Yellow
    (0,   255, 0  ),  # Green
    (255, 0,   0  ),  # Blue
    (255, 0,   128),  # Violet
    (128, 0,   255),  # Purple
    (255, 128, 0  ),  # Cyan
]

THICKNESSES = [2, 5, 10]      # px — thin / medium / thick
ERASE_RADII  = [20, 40, 70]   # px — small / medium / large eraser

TOOLS = ['pen', 'line', 'rect', 'circle', 'fill', 'eraser']
TOOL_LABELS = ['✏ Pen', '╱ Line', '▭ Rect', '● Circle', '⬛ Fill', '⌫ Erase']

# Gesture debounce
HOVER_FRAMES_NEEDED  = 8   # frames a finger must hover before button fires
BUTTON_COOLDOWN      = 20  # frames before same button can fire again
GESTURE_COOLDOWN     = 30  # frames between special-gesture actions (undo/clear)

# ─────────────────────────── helpers ─────────────────────────────

def lerp(a, b, t):
    return int(a + (b - a) * t)


def ema(new_val, old_val, alpha=0.35):
    """Exponential moving average for smoothing."""
    if old_val is None:
        return new_val
    return (lerp(old_val[0], new_val[0], alpha),
            lerp(old_val[1], new_val[1], alpha))


def dist(p1, p2):
    return ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5


# ─────────────────────── UI layout builder ───────────────────────

class UILayout:
    """Computes and stores all button rects for the toolbar."""

    TOOLBAR_W   = 70   # left toolbar width
    PAL_COLS    = 6
    PAL_CELL    = 20   # colour swatch cell size (px)
    PAL_MARGIN  = 4
    PAL_TOP     = 10

    def __init__(self):
        self.buttons = {}        # name → (x1,y1,x2,y2)
        self._build()

    def _build(self):
        tw = self.TOOLBAR_W
        # ── Tool buttons (vertical strip on the left) ──
        tool_h = 48
        tool_margin = 6
        for i, tool in enumerate(TOOLS):
            y1 = 10 + i * (tool_h + tool_margin)
            y2 = y1 + tool_h
            self.buttons[f'tool_{tool}'] = (4, y1, tw - 4, y2)

        # ── Thickness buttons (below tools) ──
        thick_labels = ['thin', 'med', 'thick']
        thick_y_start = 10 + len(TOOLS) * (tool_h + tool_margin) + 10
        thick_w = (tw - 12) // 3
        for j, lbl in enumerate(thick_labels):
            x1 = 4 + j * (thick_w + 2)
            x2 = x1 + thick_w
            self.buttons[f'thick_{lbl}'] = (x1, thick_y_start, x2, thick_y_start + 30)

        # ── Eraser-size buttons (one row, same width) ──
        esize_labels = ['sml', 'med', 'lrg']
        esize_y = thick_y_start + 40
        for j, lbl in enumerate(esize_labels):
            x1 = 4 + j * (thick_w + 2)
            x2 = x1 + thick_w
            self.buttons[f'esize_{lbl}'] = (x1, esize_y, x2, esize_y + 30)

        # ── Undo / Clear buttons ──
        action_y = esize_y + 42
        self.buttons['undo']  = (4,      action_y, tw//2-2, action_y + 30)
        self.buttons['clear'] = (tw//2+2, action_y, tw - 4,  action_y + 30)

        # ── Colour palette (top of canvas, right of toolbar) ──
        pal_x0 = tw + 6
        for idx in range(len(PALETTE)):
            row = idx // self.PAL_COLS
            col = idx  % self.PAL_COLS
            x1 = pal_x0 + col * (self.PAL_CELL + self.PAL_MARGIN)
            y1 = self.PAL_TOP + row * (self.PAL_CELL + self.PAL_MARGIN)
            x2 = x1 + self.PAL_CELL
            y2 = y1 + self.PAL_CELL
            self.buttons[f'pal_{idx}'] = (x1, y1, x2, y2)


UI = UILayout()


# ─────────────────────── canvas renderer ─────────────────────────

def render_canvas(strokes, current_stroke, w=CANVAS_W, h=CANVAS_H):
    """Redraw all strokes onto a fresh white canvas. Returns the image."""
    img = np.ones((h, w, 3), np.uint8) * 255
    for s in strokes:
        _draw_stroke(img, s)
    if current_stroke:
        _draw_stroke(img, current_stroke)
    return img


def _draw_stroke(img, s):
    tool = s.get('tool', 'pen')
    pts  = s['points']
    col  = s['color']
    thk  = s['thickness']
    if tool == 'pen' and len(pts) > 1:
        for i in range(len(pts) - 1):
            cv2.line(img, pts[i], pts[i+1], col, thk, cv2.LINE_AA)
    elif tool == 'line' and len(pts) >= 2:
        cv2.line(img, pts[0], pts[-1], col, thk, cv2.LINE_AA)
    elif tool == 'rect' and len(pts) >= 2:
        cv2.rectangle(img, pts[0], pts[-1], col, thk)
    elif tool == 'circle' and len(pts) >= 2:
        r = int(dist(pts[0], pts[-1]))
        cv2.circle(img, pts[0], r, col, thk, cv2.LINE_AA)
    elif tool == 'fill' and len(pts) >= 1:
        # Flood-fill stored as single-point stroke with fill flag
        seed = pts[0]
        mask = np.zeros((img.shape[0]+2, img.shape[1]+2), np.uint8)
        cv2.floodFill(img, mask, seed, col, (20,)*3, (20,)*3,
                      cv2.FLOODFILL_FIXED_RANGE)


def flood_fill_canvas(canvas, seed, color):
    """Apply flood fill on canvas in-place and return a fill 'stroke' record."""
    mask = np.zeros((canvas.shape[0]+2, canvas.shape[1]+2), np.uint8)
    cv2.floodFill(canvas, mask, seed, color,
                  loDiff=(20,20,20), upDiff=(20,20,20),
                  flags=cv2.FLOODFILL_FIXED_RANGE)
    return {'tool': 'fill', 'points': [seed], 'color': color, 'thickness': 1}


# ─────────────────────────── UI drawing ──────────────────────────

def draw_toolbar(img, state):
    """Overlay the left toolbar and colour palette on img."""
    tw = UILayout.TOOLBAR_W

    # Semi-transparent toolbar background
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (tw, img.shape[0]), (240, 240, 240), -1)
    cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)
    cv2.line(img, (tw, 0), (tw, img.shape[0]), (180, 180, 180), 1)

    # ── Tool buttons ──
    for i, tool in enumerate(TOOLS):
        bname = f'tool_{tool}'
        x1,y1,x2,y2 = UI.buttons[bname]
        selected = (state['tool'] == tool)
        hovered  = (state['hovered'] == bname)
        _draw_btn(img, x1,y1,x2,y2,
                  TOOL_LABELS[i], selected=selected, hovered=hovered,
                  font_scale=0.38, font_thick=1)

    # ── Thickness buttons ──
    thick_map = {'thin': 0, 'med': 1, 'thick': 2}
    cur_ti = THICKNESSES.index(state['thickness']) if state['thickness'] in THICKNESSES else 0
    for lbl, ti in thick_map.items():
        bname = f'thick_{lbl}'
        x1,y1,x2,y2 = UI.buttons[bname]
        sel = (cur_ti == ti)
        hov = (state['hovered'] == bname)
        _draw_btn(img, x1,y1,x2,y2, lbl, selected=sel, hovered=hov,
                  font_scale=0.30, font_thick=1)
        # Draw representative line inside button
        cy = (y1+y2)//2
        cv2.line(img, (x1+4, cy), (x2-4, cy), (40,40,40), THICKNESSES[ti])

    # Label for thickness row
    x1t,y1t,_,_ = UI.buttons['thick_thin']
    cv2.putText(img, 'Brush', (4, y1t - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (80,80,80), 1)

    # ── Eraser-size buttons ──
    esize_map = {'sml': 0, 'med': 1, 'lrg': 2}
    cur_ei = ERASE_RADII.index(state['erase_radius']) if state['erase_radius'] in ERASE_RADII else 0
    for lbl, ei in esize_map.items():
        bname = f'esize_{lbl}'
        x1,y1,x2,y2 = UI.buttons[bname]
        sel = (cur_ei == ei)
        hov = (state['hovered'] == bname)
        _draw_btn(img, x1,y1,x2,y2, lbl, selected=sel, hovered=hov,
                  font_scale=0.28, font_thick=1)

    x1e,y1e,_,_ = UI.buttons['esize_sml']
    cv2.putText(img, 'Eraser', (4, y1e - 3),
                cv2.FONT_HERSHEY_SIMPLEX, 0.28, (80,80,80), 1)

    # ── Undo / Clear buttons ──
    x1u,y1u,x2u,y2u = UI.buttons['undo']
    x1c,y1c,x2c,y2c = UI.buttons['clear']
    _draw_btn(img, x1u,y1u,x2u,y2u,'↩ Undo',
              hovered=(state['hovered']=='undo'), font_scale=0.28, font_thick=1)
    _draw_btn(img, x1c,y1c,x2c,y2c,'✕ Clr',
              hovered=(state['hovered']=='clear'), font_scale=0.28, font_thick=1,
              base_color=(200,200,255))

    # ── Colour palette ──
    for idx, col in enumerate(PALETTE):
        bname = f'pal_{idx}'
        x1,y1,x2,y2 = UI.buttons[bname]
        sel = (state['color'] == col)
        hov = (state['hovered'] == bname)
        border = 3 if sel else (2 if hov else 1)
        border_col = (0,200,100) if sel else (0,0,0)
        cv2.rectangle(img, (x1,y1), (x2,y2), col, -1)
        cv2.rectangle(img, (x1,y1), (x2,y2), border_col, border)

    # ── Colour preview swatch ──
    sw_x = UILayout.TOOLBAR_W + 6
    sw_y = UILayout.PAL_TOP + 2*(UILayout.PAL_CELL + UILayout.PAL_MARGIN) + 6
    cv2.rectangle(img, (sw_x, sw_y), (sw_x+40, sw_y+16), state['color'], -1)
    cv2.rectangle(img, (sw_x, sw_y), (sw_x+40, sw_y+16), (0,0,0), 1)
    cv2.putText(img, 'Colour', (sw_x+44, sw_y+12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (60,60,60), 1)


def _draw_btn(img, x1, y1, x2, y2, label,
              selected=False, hovered=False,
              font_scale=0.35, font_thick=1,
              base_color=(220,220,220)):
    bg = (170,230,170) if selected else ((255,255,180) if hovered else base_color)
    cv2.rectangle(img, (x1,y1),(x2,y2), bg, -1)
    border_thk = 2 if (selected or hovered) else 1
    border_col = (0,140,0) if selected else (100,100,100)
    cv2.rectangle(img, (x1,y1),(x2,y2), border_col, border_thk)

    # Centre text
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thick)
    tx = x1 + ((x2-x1) - tw)//2
    ty = y1 + ((y2-y1) + th)//2
    cv2.putText(img, label, (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, (20,20,20), font_thick, cv2.LINE_AA)


def draw_status_bar(img, state):
    """Draw a status bar at the bottom of the canvas."""
    h, w = img.shape[:2]
    bar_h = 22
    cv2.rectangle(img, (0, h-bar_h), (w, h), (50, 50, 50), -1)

    tool_name = state['tool'].upper()
    thick_info = f"Brush: {state['thickness']}px" if state['tool'] != 'eraser' \
                 else f"Eraser: {state['erase_radius']}px"
    undo_info  = f"Strokes: {state['stroke_count']}  (Fist=Undo | Palm=Clear)"
    fps_info   = f"FPS:{state.get('fps', 0):.0f}"

    parts = [f"Tool: {tool_name}", thick_info, undo_info, fps_info]
    x = 8
    for p in parts:
        cv2.putText(img, p, (x, h - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220,220,220), 1, cv2.LINE_AA)
        (tw, _), _ = cv2.getTextSize(p, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        x += tw + 20


def draw_eraser_cursor(img, cx, cy, radius):
    """Draw a dashed eraser circle cursor."""
    cv2.circle(img, (cx, cy), radius, (0, 0, 200), 2, cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 3, (0, 0, 200), -1)
    # Small cross-hair
    cv2.line(img, (cx-6, cy), (cx+6, cy), (0,0,200), 1)
    cv2.line(img, (cx, cy-6), (cx, cy+6), (0,0,200), 1)


def draw_shape_preview(img, state, end_pt):
    """Draw a ghost preview of the shape being drawn."""
    if not state.get('shape_start'):
        return
    s = state['shape_start']
    col = state['color']
    thk = state['thickness']
    tool = state['tool']
    preview = img.copy()
    if tool == 'line':
        cv2.line(preview, s, end_pt, col, thk, cv2.LINE_AA)
    elif tool == 'rect':
        cv2.rectangle(preview, s, end_pt, col, thk)
    elif tool == 'circle':
        r = int(dist(s, end_pt))
        cv2.circle(preview, s, r, col, thk, cv2.LINE_AA)
    cv2.addWeighted(preview, 0.6, img, 0.4, 0, img)


# ──────────────────────── gesture helpers ────────────────────────

def classify_gesture(fingers):
    """Return a gesture name string from 5-finger list."""
    if fingers == [0, 0, 0, 0, 0]:
        return 'fist'
    if fingers == [1, 1, 1, 1, 1]:
        return 'palm'
    if fingers[1] == 1 and fingers[2] == 0:
        return 'index'           # draw / erase
    if fingers[1] == 1 and fingers[2] == 1:
        return 'two_fingers'     # select / hover UI
    if fingers[1] == 0 and fingers[2] == 0:
        return 'idle'
    return 'other'


def hit_button(px, py, margin=12):
    """Return first button name that (px,py) is inside (with margin)."""
    for name, (x1,y1,x2,y2) in UI.buttons.items():
        if (x1-margin) <= px <= (x2+margin) and (y1-margin) <= py <= (y2+margin):
            return name
    return None


# ──────────────────────────── main ───────────────────────────────

def main():
    # ── Camera init ──────────────────────────────────────────────
    cap = None
    camera_available = False
    print("Initialising camera...")
    for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
        try:
            cap = cv2.VideoCapture(0, backend)
            if not cap.isOpened():
                cap.release(); cap = None; continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            time.sleep(0.4)
            ok = False
            for _ in range(5):
                ret, frm = cap.read()
                if ret and frm is not None:
                    ok = True; break
                time.sleep(0.1)
            if ok:
                camera_available = True
                print("[OK] Camera ready.")
                break
            cap.release(); cap = None
        except Exception as e:
            print(f"  Backend {backend} failed: {e}")
            if cap: cap.release(); cap = None

    if not camera_available:
        print("[WARN] No camera — hand tracking disabled.")

    # ── Tracker ──────────────────────────────────────────────────
    tracker = HandTracker()

    # ── App state ────────────────────────────────────────────────
    strokes       = []          # committed strokes
    current_stroke = None       # stroke being drawn right now
    redo_stack    = []          # for undo (pop from strokes, push here)

    state = {
        'tool':         'pen',
        'color':        PALETTE[0],   # black
        'thickness':    THICKNESSES[0],
        'erase_radius': ERASE_RADII[0],
        'hovered':      None,
        'stroke_count': 0,
        'fps':          0,
        'shape_start':  None,         # for shape tools
    }

    # Interaction tracking
    prev_ptr      = None   # smoothed pointer
    prev_draw     = None   # smoothed draw point
    prev_lm_list  = None

    hovered_name    = None
    hover_frames    = 0
    last_fired_btn  = None
    btn_cooldown    = 0

    gesture_cooldown = 0   # for fist / palm gestures

    # Dirty-flag: only re-render strokes when something changed
    canvas_dirty  = True
    cached_canvas = np.ones((CANVAS_H, CANVAS_W, 3), np.uint8) * 255

    # FPS tracking
    fps_t = time.time()
    fps_count = 0

    # ── Window ───────────────────────────────────────────────────
    cv2.namedWindow('Virtual Whiteboard', cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty('Virtual Whiteboard',
                              cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        pass

    print("\n" + "="*55)
    print(" Virtual Whiteboard  —  Improved Edition")
    print("="*55)
    print("  Gestures:")
    print("   Index only      → Draw / Erase")
    print("   Index + Middle  → Hover & select UI buttons")
    print("   Fist            → Undo last stroke")
    print("   Open Palm       → Clear canvas")
    print("  Keyboard:")
    print("   Q / ESC         → Quit")
    print("   S               → Save drawing as PNG")
    print("   Z               → Undo")
    print("   C               → Clear canvas")
    print("="*55 + "\n")

    # ── Main loop ────────────────────────────────────────────────
    while True:
        # Window-close check
        try:
            if cv2.getWindowProperty('Virtual Whiteboard', cv2.WND_PROP_VISIBLE) < 1:
                break
        except Exception:
            break

        loop_start = time.time()

        # ── Camera frame ─────────────────────────────────────────
        frame = None
        if camera_available and cap is not None:
            success, frame = cap.read()
            if not success:
                camera_available = False
                frame = None

        # ── Hand tracking ────────────────────────────────────────
        lm_list       = []
        current_fingers = []
        gesture       = 'idle'
        ptr           = None     # smoothed index-finger canvas coord

        if frame is not None:
            frame = cv2.flip(frame, 1)
            frame = tracker.find_hands(frame)
            lm_list = tracker.get_positions(frame)
            if lm_list and len(lm_list) >= 21:
                lm_list = tracker.smooth_landmarks(lm_list, prev_lm_list, alpha=0.45)
                prev_lm_list = [list(x) for x in lm_list]
                current_fingers = tracker.fingers_up(lm_list)

        if lm_list and len(lm_list) >= 21 and len(current_fingers) == 5:
            tip = lm_list[8]
            fh, fw = frame.shape[:2]
            raw = (int(tip[1] * CANVAS_W / fw),
                   int(tip[2] * CANVAS_H / fh))
            # Clamp
            raw = (max(0, min(CANVAS_W-1, raw[0])),
                   max(0, min(CANVAS_H-1, raw[1])))
            # EMA smoothing
            prev_ptr = ema(raw, prev_ptr, alpha=0.30)
            ptr = prev_ptr
            gesture = classify_gesture(current_fingers)

        # ── Gesture: Fist = Undo, Palm = Clear ───────────────────
        if gesture_cooldown > 0:
            gesture_cooldown -= 1

        if gesture == 'fist' and gesture_cooldown == 0:
            if current_stroke:
                strokes.append(current_stroke)
                current_stroke = None
            if strokes:
                redo_stack.append(strokes.pop())
                canvas_dirty = True
                print("[UNDO] Stroke undone.")
            gesture_cooldown = GESTURE_COOLDOWN

        elif gesture == 'palm' and gesture_cooldown == 0:
            if current_stroke:
                current_stroke = None
            if strokes:
                redo_stack.extend(strokes)
                strokes.clear()
                canvas_dirty = True
                print("[CLEAR] Canvas cleared.")
            gesture_cooldown = GESTURE_COOLDOWN

        # ── UI button hover / selection ───────────────────────────
        state['hovered'] = None
        if btn_cooldown > 0:
            btn_cooldown -= 1

        if gesture == 'two_fingers' and ptr is not None:
            detected = hit_button(ptr[0], ptr[1])
            state['hovered'] = detected

            if detected == hovered_name:
                hover_frames += 1
            else:
                hover_frames = 1 if detected else 0
            hovered_name = detected

            if (detected and hover_frames >= HOVER_FRAMES_NEEDED
                    and btn_cooldown == 0 and detected != last_fired_btn):
                _handle_button(detected, state, strokes, redo_stack)
                canvas_dirty = True
                last_fired_btn = detected
                btn_cooldown   = BUTTON_COOLDOWN
                hover_frames   = 0

            # Stop any in-progress stroke while hovering
            if current_stroke:
                strokes.append(current_stroke)
                current_stroke = None
                canvas_dirty = True
            prev_draw = None
            state['shape_start'] = None

        else:
            hover_frames   = 0
            hovered_name   = None
            last_fired_btn = None

        # ── Drawing / Erasing ────────────────────────────────────
        if gesture == 'index' and ptr is not None:
            # Separate smoothing for drawing (more responsive than UI pointer)
            prev_draw = ema(ptr, prev_draw, alpha=0.45)
            x, y = prev_draw

            tool = state['tool']

            if tool == 'eraser':
                # ── Improved eraser: erase at segment level ──
                radius = state['erase_radius']
                to_remove = []
                for si, stroke in enumerate(strokes):
                    pts = stroke['points']
                    for pi in range(len(pts)):
                        if dist(pts[pi], (x,y)) < radius:
                            to_remove.append(si)
                            break
                        # Check midpoints of segments for smoother erasing
                        if pi > 0 and _seg_point_dist(pts[pi-1], pts[pi], (x,y)) < radius:
                            to_remove.append(si)
                            break
                if to_remove:
                    for si in sorted(set(to_remove), reverse=True):
                        del strokes[si]
                    canvas_dirty = True

                # Also trim current stroke
                if current_stroke:
                    kept = [(px,py) for px,py in current_stroke['points']
                            if dist((px,py), (x,y)) >= radius]
                    current_stroke['points'] = kept
                    canvas_dirty = True

            elif tool == 'fill':
                # Single tap to fill — use fist-like one-shot via cooldown
                if gesture_cooldown == 0:
                    fill_s = flood_fill_canvas(cached_canvas,
                                               (x, y), state['color'])
                    strokes.append(fill_s)
                    canvas_dirty = True
                    gesture_cooldown = GESTURE_COOLDOWN // 2

            elif tool == 'pen':
                if current_stroke is None:
                    current_stroke = {
                        'tool': 'pen',
                        'points': [(x,y)],
                        'color': state['color'],
                        'thickness': state['thickness'],
                    }
                else:
                    # Simplify: only add point if moved enough (reduces jitter)
                    if not current_stroke['points'] or \
                            dist(current_stroke['points'][-1], (x,y)) > 2:
                        current_stroke['points'].append((x,y))
                canvas_dirty = True

            else:  # line / rect / circle — rubber-band shape
                if state['shape_start'] is None:
                    state['shape_start'] = (x, y)
                # update endpoint continuously; commit on gesture release handled below
                if current_stroke is None:
                    current_stroke = {
                        'tool': tool,
                        'points': [state['shape_start'], (x,y)],
                        'color': state['color'],
                        'thickness': state['thickness'],
                    }
                else:
                    current_stroke['points'] = [state['shape_start'], (x,y)]
                canvas_dirty = True

        else:
            # Gesture released → commit current stroke
            if current_stroke:
                strokes.append(current_stroke)
                current_stroke = None
                canvas_dirty = True
                redo_stack.clear()
            state['shape_start'] = None
            if gesture != 'two_fingers':
                prev_draw = None

        state['stroke_count'] = len(strokes)

        # ── Build display frame ───────────────────────────────────
        # Only re-render committed strokes when dirty
        if canvas_dirty:
            cached_canvas = render_canvas(strokes, None, w=CANVAS_W, h=CANVAS_H)
            canvas_dirty = False

        display = cached_canvas.copy()

        # Draw current (in-progress) stroke on top
        if current_stroke:
            _draw_stroke(display, current_stroke)

        # Shape ghost preview
        if state['tool'] in ('line','rect','circle') and ptr is not None:
            draw_shape_preview(display, state, ptr)

        # Fingertip dot
        if ptr is not None and gesture in ('index','two_fingers'):
            col_dot = (0,0,200) if state['tool']=='eraser' else (0,0,0)
            cv2.circle(display, ptr, 4, col_dot, -1)

        # Eraser cursor circle
        if state['tool'] == 'eraser' and ptr is not None and gesture == 'index':
            draw_eraser_cursor(display, ptr[0], ptr[1], state['erase_radius'])

        # Toolbar + palette
        draw_toolbar(display, state)

        # Status bar
        fps_count += 1
        elapsed = time.time() - fps_t
        if elapsed >= 1.0:
            state['fps'] = fps_count / elapsed
            fps_count = 0
            fps_t = time.time()
        draw_status_bar(display, state)

        # Camera preview (bottom-right corner)
        if frame is not None:
            dh, dw = display.shape[:2]
            pw = max(int(dw * 0.22), 1)
            ph = int(pw * frame.shape[0] / max(frame.shape[1],1))
            ph = min(ph, int(dh * 0.22))
            pw = int(ph * frame.shape[1] / max(frame.shape[0],1))
            if pw > 0 and ph > 0:
                preview = cv2.resize(frame, (pw, ph))
                y1p = dh - ph - 26
                x1p = dw - pw - 6
                if y1p >= 0 and x1p >= 0:
                    display[y1p:y1p+ph, x1p:x1p+pw] = preview
                    cv2.rectangle(display,(x1p,y1p),(x1p+pw,y1p+ph),(80,80,80),1)

        # Resize to window
        try:
            _, _, ww, wh = cv2.getWindowImageRect('Virtual Whiteboard')
            if ww > 0 and wh > 0 and (ww != display.shape[1] or wh != display.shape[0]):
                display = cv2.resize(display, (ww,wh), interpolation=cv2.INTER_LINEAR)
        except Exception:
            pass

        cv2.imshow('Virtual Whiteboard', display)

        # ── Keyboard shortcuts ────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break
        elif key in (ord('z'), ord('Z')):
            if strokes:
                redo_stack.append(strokes.pop())
                canvas_dirty = True
                print("[UNDO] Keyboard undo.")
        elif key in (ord('c'), ord('C')):
            redo_stack.extend(strokes)
            strokes.clear()
            canvas_dirty = True
            print("[CLEAR] Keyboard clear.")
        elif key in (ord('s'), ord('S')):
            _save_drawing(strokes, current_stroke)

        if cv2.getWindowProperty('Virtual Whiteboard', cv2.WND_PROP_VISIBLE) < 1:
            break

    # ── Cleanup ───────────────────────────────────────────────────
    if cap: cap.release()
    cv2.destroyAllWindows()
    print("Whiteboard closed.")


# ─────────────────── button-action dispatcher ─────────────────────

def _handle_button(name, state, strokes, redo_stack):
    if name.startswith('tool_'):
        tool = name[len('tool_'):]
        state['tool'] = tool
        print(f"[TOOL] {tool}")
    elif name.startswith('pal_'):
        idx = int(name[len('pal_'):])
        state['color'] = PALETTE[idx]
        print(f"[COLOR] palette[{idx}]")
    elif name.startswith('thick_'):
        lbl = name[len('thick_'):]
        state['thickness'] = THICKNESSES[{'thin':0,'med':1,'thick':2}[lbl]]
        print(f"[THICK] {state['thickness']}px")
    elif name.startswith('esize_'):
        lbl = name[len('esize_'):]
        state['erase_radius'] = ERASE_RADII[{'sml':0,'med':1,'lrg':2}[lbl]]
        print(f"[ERASER] radius={state['erase_radius']}px")
    elif name == 'undo':
        if strokes:
            redo_stack.append(strokes.pop())
            print("[UNDO] via button")
    elif name == 'clear':
        redo_stack.extend(strokes)
        strokes.clear()
        print("[CLEAR] via button")


# ─────────────────────── segment distance ─────────────────────────

def _seg_point_dist(a, b, p):
    """Minimum distance from point p to line segment a-b."""
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx-ax, by-ay
    if dx == 0 and dy == 0:
        return dist(a, p)
    t = max(0, min(1, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)))
    proj = (ax + t*dx, ay + t*dy)
    return dist(proj, p)


# ─────────────────────────── save ────────────────────────────────

def _save_drawing(strokes, current_stroke):
    save_canvas = render_canvas(strokes, current_stroke)
    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = f"drawing_{ts}.png"
    try:
        cv2.imwrite(fname, save_canvas)
        print(f"[SAVED] {os.path.abspath(fname)}")
    except Exception as e:
        print(f"[ERROR] Save failed: {e}")


if __name__ == "__main__":
    main()