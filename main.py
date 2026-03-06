import cv2
import numpy as np
import time
import os  # For saving drawings with timestamped filenames
from hand_tracking_module import HandTracker

def main():
    """
    Main function to run the virtual whiteboard application.
    """
    # Initialize camera (optional - whiteboard will work without it)
    cap = None
    camera_available = False
    
    print("Initializing camera...")
    try:
        # Try different camera backends
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        cap = None
        
        for backend in backends:
            try:
                cap = cv2.VideoCapture(0, backend)
                if cap.isOpened():
                    # Set camera properties for better compatibility
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to minimize latency
                    
                    # Give camera time to initialize
                    time.sleep(0.5)
                    
                    # Try reading multiple frames (sometimes first few fail)
                    test_success = False
                    for attempt in range(5):
                        ret, test_frame = cap.read()
                        if ret and test_frame is not None:
                            test_success = True
                            break
                        time.sleep(0.1)
                    
                    if test_success:
                        camera_available = True
                        print("[OK] Camera initialized successfully!")
                        break
                    else:
                        print(f"  Camera opened but cannot read frames (backend {backend})")
                        cap.release()
                        cap = None
                else:
                    if cap:
                        cap.release()
                    cap = None
            except Exception as e:
                print(f"  Backend {backend} failed: {e}")
                if cap:
                    cap.release()
                cap = None
                continue
        
        if not camera_available:
            print("[WARNING] Could not initialize camera. Running whiteboard without camera.")
            print("  The whiteboard will still work, but hand tracking will be disabled.")
            
    except Exception as e:
        print(f"[WARNING] Camera initialization failed: {e}")
        print("  Running whiteboard without camera.")
        if cap:
            cap.release()
            cap = None

    # Initialize hand tracker
    tracker = HandTracker()

    # Canvas settings
    # Logical canvas size (display is later resized to window size so it fills screen)
    canvas_width, canvas_height = 640, 480
    canvas = np.ones((canvas_height, canvas_width, 3), np.uint8) * 255  # White canvas
    
    # Drawing settings
    # Extended color palette (BGR)
    colors = [
        (255, 0, 0),    # Blue
        (0, 255, 0),    # Green
        (0, 0, 255),    # Red
        (0, 255, 255),  # Yellow
        (255, 0, 255),  # Purple
        (0, 0, 0),      # Black
    ]
    color_names = ['Blue', 'Green', 'Red', 'Yellow', 'Purple', 'Black']
    current_color_index = 0
    current_color = colors[current_color_index]
    thicknesses = [2, 5, 8]  # Thin, Medium, Thick
    current_color = colors[0]
    current_thickness = thicknesses[0]

    # Strokes storage: list of dicts with 'points', 'color', 'thickness'
    strokes = []
    current_stroke = None

    # Modes
    drawing_mode = False
    selection_mode = False
    eraser_mode = False
    
    # Button selection tracking (for debouncing)
    last_selected_button = None
    button_press_cooldown = 0

    # UI Buttons: dict of name: (x1, y1, x2, y2)
    # Color buttons are mapped to indices in the colors list above.
    buttons = {
        'color_blue': (10, 10, 60, 60),
        'color_green': (70, 10, 120, 60),
        'color_red': (130, 10, 180, 60),
        'color_yellow': (190, 10, 240, 60),
        'color_purple': (250, 10, 300, 60),
        'color_black': (310, 10, 360, 60),
        'thin': (10, 80, 60, 130),
        'medium': (80, 80, 130, 130),
        'thick': (150, 80, 200, 130),
        'eraser': (10, 150, 60, 200)
    }

    color_button_indices = {
        'color_blue': 0,
        'color_green': 1,
        'color_red': 2,
        'color_yellow': 3,
        'color_purple': 4,
        'color_black': 5,
    }

    def draw_ui(img, hovered_button_name=None):
        """
        Draw UI buttons on the image.

        Args:
            img: Image to draw on.
            hovered_button_name: Name of button being hovered (for highlighting)
        """
        for name, (x1, y1, x2, y2) in buttons.items():
            # Highlight selected color/thickness
            is_selected = False
            if name.startswith('color_'):
                # Highlight the currently selected color button
                idx = color_button_indices.get(name, -1)
                if idx == current_color_index:
                    is_selected = True
            elif name == 'thin' and current_thickness == thicknesses[0]:
                is_selected = True
            elif name == 'medium' and current_thickness == thicknesses[1]:
                is_selected = True
            elif name == 'thick' and current_thickness == thicknesses[2]:
                is_selected = True
            elif name == 'eraser' and eraser_mode:
                is_selected = True
            
            # Check if button is being hovered
            is_hovered = (name == hovered_button_name)
            
            # Draw button background (highlighted if selected or hovered)
            if is_selected:
                cv2.rectangle(img, (x1, y1), (x2, y2), (150, 255, 150), -1)  # Light green when selected
            elif is_hovered:
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 150), -1)  # Yellow when hovered
            else:
                cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), -1)
            
            # Draw border (thicker if selected or hovered)
            border_thickness = 3 if (is_selected or is_hovered) else 2
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), border_thickness)
            
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            if name.startswith('color_'):
                # Draw color swatch corresponding to this button
                idx = color_button_indices.get(name, None)
                if idx is not None and 0 <= idx < len(colors):
                    cv2.circle(img, (center_x, center_y), 15, colors[idx], -1)
            elif name == 'thin':
                cv2.line(img, (x1 + 10, center_y), (x2 - 10, center_y), (0, 0, 0), 2)
            elif name == 'medium':
                cv2.line(img, (x1 + 10, center_y), (x2 - 10, center_y), (0, 0, 0), 5)
            elif name == 'thick':
                cv2.line(img, (x1 + 10, center_y), (x2 - 10, center_y), (0, 0, 0), 8)
            elif name == 'eraser':
                cv2.putText(img, 'ERASE', (x1 + 5, center_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

    print("\n" + "="*50)
    print("Virtual Whiteboard Starting...")
    print("="*50)
    if camera_available:
        print("[OK] Camera: ENABLED - Hand tracking active")
    else:
        print("[WARNING] Camera: DISABLED - Hand tracking unavailable")
    print("Controls:")
    print("  - Press 'Q' or 'ESC' to quit")
    print("  - Click window X button to close")
    print("="*50 + "\n")
    
    # Create window first
    cv2.namedWindow('Virtual Whiteboard', cv2.WINDOW_NORMAL)
    # Try to start in fullscreen so the whiteboard fills the screen
    try:
        cv2.setWindowProperty('Virtual Whiteboard', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        # If fullscreen is not supported, window will remain resizable
        pass

    # For smoothing drawing coordinates
    prev_draw_point = None
    # For smoothing pointer (used for selection and hover)
    prev_pointer = None
    pointer_alpha = 0.25  # Lower = smoother, higher = more responsive

    # Hover/debounce tracking for button selection
    hover_frames = 0
    hover_threshold = 6  # Number of consecutive frames to consider a hover stable
    last_hovered_name = None
    # Previous landmarks for temporal smoothing
    prev_lm_list = None
    
    while True:
        # Check if window was closed
        try:
            if cv2.getWindowProperty('Virtual Whiteboard', cv2.WND_PROP_VISIBLE) < 1:
                break
        except:
            # Window might not exist yet or was closed
            break
        
        # Read from camera if available
        if camera_available and cap is not None:
            success, frame = cap.read()
            if not success:
                # Camera failed during runtime, continue without it
                if camera_available:  # Only print once
                    print("[WARNING] Camera disconnected during runtime. Continuing without camera.")
                camera_available = False
                frame = None
        else:
            frame = None
        
        # Process hand tracking if camera frame is available
        lm_list = []
        current_fingers = []
        hovered_button_name = None  # Track which button is being hovered
        
        if frame is not None:
            frame = cv2.flip(frame, 1)  # Mirror the frame
            frame = tracker.find_hands(frame)  # Detect hands and draw landmarks
            lm_list = tracker.get_positions(frame)
            # Apply temporal smoothing to landmarks if available
            if lm_list and len(lm_list) >= 21:
                lm_list = tracker.smooth_landmarks(lm_list, prev_lm_list, alpha=0.45)
                # Store a copy for next frame
                prev_lm_list = [list(x) for x in lm_list]
                current_fingers = tracker.fingers_up(lm_list)
            else:
                prev_lm_list = None

        if lm_list and len(lm_list) >= 21 and len(current_fingers) == 5:
            fingers = current_fingers
            if len(fingers) == 5:  # Ensure we got valid finger states
                index_tip = lm_list[8]  # Index finger tip

                # NOTE: HandTracker already returns coordinates in image space.
                # Apply separate smoothing for the pointer used to select UI buttons
                raw_x, raw_y = index_tip[1], index_tip[2]

                frame_h, frame_w = frame.shape[:2]
                raw_x = int(raw_x * canvas_width / frame_w)
                raw_y = int(raw_y * canvas_height / frame_h)

                # Pointer EMA smoothing (keeps selection stable even when not drawing)
                if prev_pointer is None:
                    ptr_x, ptr_y = raw_x, raw_y
                else:
                    ptr_x = int(pointer_alpha * raw_x + (1 - pointer_alpha) * prev_pointer[0])
                    ptr_y = int(pointer_alpha * raw_y + (1 - pointer_alpha) * prev_pointer[1])
                prev_pointer = (ptr_x, ptr_y)

                # Smooth drawing coordinates separately (so strokes remain responsive)
                if prev_draw_point is None:
                    smooth_x, smooth_y = ptr_x, ptr_y
                else:
                    alpha = 0.3  # Higher = closer to current position (for drawing responsiveness)
                    smooth_x = int(alpha * ptr_x + (1 - alpha) * prev_draw_point[0])
                    smooth_y = int(alpha * ptr_y + (1 - alpha) * prev_draw_point[1])

                x, y = smooth_x, smooth_y

                # Determine mode based on gestures
                if fingers[1] == 1 and fingers[2] == 0:  # Only index finger up
                    if eraser_mode:
                        # In eraser mode, index finger is for erasing (handled separately)
                        drawing_mode = False
                        selection_mode = False
                    else:
                        # Normal drawing mode
                        drawing_mode = True
                        selection_mode = False
                elif fingers[1] == 1 and fingers[2] == 1:  # Index and middle fingers up
                    selection_mode = True
                    drawing_mode = False
                    # Don't disable eraser_mode here - let user select eraser button again or use gesture
                elif fingers == [1, 1, 0, 0, 0]:  # Thumb and index up - exit eraser mode
                    if eraser_mode:
                        eraser_mode = False
                        drawing_mode = True
                        selection_mode = False
                        print("Eraser mode deactivated - back to drawing")
                    else:
                        # If not in eraser mode, thumb+index can also be drawing
                        drawing_mode = True
                        selection_mode = False
                else:
                    # Other gestures - disable drawing and selection
                    drawing_mode = False
                    selection_mode = False
                    # Don't auto-disable eraser_mode

                # Handle drawing
                if drawing_mode and not eraser_mode:
                    # Clamp coordinates to canvas bounds
                    x = max(0, min(canvas_width - 1, x))
                    y = max(0, min(canvas_height - 1, y))
                    
                    if current_stroke is None:
                        current_stroke = {'points': [(x, y)], 'color': current_color, 'thickness': current_thickness}
                    else:
                        current_stroke['points'].append((x, y))
                    # Update previous point for smoothing
                    prev_draw_point = (x, y)
                else:
                    # Stop current stroke if not drawing
                    if current_stroke:
                        strokes.append(current_stroke)
                        current_stroke = None
                    prev_draw_point = None

                # Handle selection (with debouncing)
                if selection_mode:
                    button_press_cooldown = max(0, button_press_cooldown - 1)

                    # Use the smoothed pointer for button detection (ptr_x, ptr_y)
                    x_btn = max(0, min(canvas_width - 1, ptr_x))
                    y_btn = max(0, min(canvas_height - 1, ptr_y))

                    # Detect hovered button (don't trigger selection immediately)
                    margin = 15  # Larger margin to make hovering easier
                    hovered_button_name = None
                    for name, (x1, y1, x2, y2) in buttons.items():
                        if (x1 - margin) <= x_btn <= (x2 + margin) and (y1 - margin) <= y_btn <= (y2 + margin):
                            hovered_button_name = name
                            break

                    # Sustained-hover debouncing: require stable hover for several frames
                    if hovered_button_name == last_hovered_name:
                        hover_frames += 1
                    else:
                        hover_frames = 1 if hovered_button_name else 0
                    last_hovered_name = hovered_button_name

                    if hovered_button_name and hover_frames >= hover_threshold and button_press_cooldown == 0 and hovered_button_name != last_selected_button:
                        name = hovered_button_name
                        if name.startswith('color_'):
                            idx = color_button_indices.get(name, None)
                            if idx is not None and 0 <= idx < len(colors):
                                current_color_index = idx
                                current_color = colors[current_color_index]
                                print(f"[SELECTED] {color_names[current_color_index]} color")
                        elif name == 'thin':
                            current_thickness = thicknesses[0]
                            print("[SELECTED] Thin brush")
                        elif name == 'medium':
                            current_thickness = thicknesses[1]
                            print("[SELECTED] Medium brush")
                        elif name == 'thick':
                            current_thickness = thicknesses[2]
                            print("[SELECTED] Thick brush")
                        elif name == 'eraser':
                            if eraser_mode:
                                eraser_mode = False
                                drawing_mode = True
                                print("[ERASER] Deactivated - back to drawing")
                            else:
                                eraser_mode = True
                                drawing_mode = False
                                selection_mode = False
                                print("[ERASER] Activated - use index finger to erase")

                        last_selected_button = name
                        button_press_cooldown = 15
                        hover_frames = 0
                else:
                    # Reset button selection when not in selection mode
                    if last_selected_button is not None:
                        last_selected_button = None
                        button_press_cooldown = 0
                    # Reset hover tracking
                    hover_frames = 0
                    last_hovered_name = None

                # Handle erasing (works with index finger when eraser mode is active)
                if eraser_mode:
                    # Use index finger to erase (same gesture as drawing)
                    erase_radius = 25  # Increased radius for easier erasing
                    to_remove = []
                    for i, stroke in enumerate(strokes):
                        for px, py in stroke['points']:
                            distance = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
                            if distance < erase_radius:
                                to_remove.append(i)
                                break
                    for i in sorted(set(to_remove), reverse=True):
                        del strokes[i]
                    if current_stroke:
                        current_stroke['points'] = [(px, py) for px, py in current_stroke['points'] 
                                                    if ((px - x) ** 2 + (py - y) ** 2) ** 0.5 >= erase_radius]
                    
                    # Draw eraser indicator circle
                    if frame is not None:
                        cv2.circle(frame, (x, y), erase_radius, (0, 0, 255), 2)  # Red circle indicator
            else:
                # If fingers list is invalid, stop current stroke
                if current_stroke:
                    strokes.append(current_stroke)
                    current_stroke = None
                prev_draw_point = None
        else:
            # If no hand detected, stop current stroke
            if current_stroke:
                strokes.append(current_stroke)
                current_stroke = None
            prev_draw_point = None

        # Create display canvas (pure drawing surface; UI and overlays added later)
        display = canvas.copy()

        # Draw all strokes
        for stroke in strokes:
            points = stroke['points']
            if len(points) > 1:
                for i in range(len(points) - 1):
                    cv2.line(display, points[i], points[i + 1], stroke['color'], stroke['thickness'])

        # Draw current stroke
        if current_stroke:
            points = current_stroke['points']
            if len(points) > 1:
                for i in range(len(points) - 1):
                    cv2.line(display, points[i], points[i + 1], current_stroke['color'], current_stroke['thickness'])

        # Draw fingertip indicator on drawing canvas (for visual feedback)
        if lm_list and len(lm_list) >= 21 and len(current_fingers) == 5:
            index_tip = lm_list[8]
            fx, fy = index_tip[1], index_tip[2]
            fx = max(0, min(canvas_width - 1, fx))
            fy = max(0, min(canvas_height - 1, fy))
            cv2.circle(display, (fx, fy), 5, (0, 0, 0), -1)  # Small black dot

        # Draw UI (buttons, etc.)
        draw_ui(display, hovered_button_name)

        # Add mode indicator
        mode_text = ""
        if eraser_mode:
            mode_text = "MODE: ERASER (Index finger to erase)"
        elif selection_mode:
            if hovered_button_name:
                mode_text = f"MODE: SELECTION (Hovering: {hovered_button_name.replace('_', ' ').title()})"
            else:
                mode_text = "MODE: SELECTION (Point at buttons to select)"
        elif drawing_mode:
            mode_text = f"MODE: DRAWING (Color: {color_names[current_color_index]}, Thickness: {current_thickness}px)"
        else:
            mode_text = "MODE: IDLE (Raise index finger to draw)"
        
        cv2.putText(display, mode_text, (10, display.shape[0] - 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # Add instructions and camera status text
        status_text = "Press 'Q' or 'ESC' to quit"
        if not camera_available:
            status_text += " | Camera: OFF"
        cv2.putText(display, status_text, (10, display.shape[0] - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        
        # Draw eraser indicator on display if in eraser mode and hand is detected
        if eraser_mode and lm_list and len(lm_list) >= 21 and len(current_fingers) == 5:
            index_tip = lm_list[8]
            ex, ey = index_tip[1], index_tip[2]
            ex = max(0, min(canvas_width - 1, ex))
            ey = max(0, min(canvas_height - 1, ey))
            cv2.circle(display, (ex, ey), 25, (0, 0, 255), 2)  # Red circle indicator

        # Add live camera preview in the bottom-right corner (does not block the main canvas)
        if frame is not None:
            # Create a small preview while preserving aspect ratio
            disp_h, disp_w = display.shape[:2]
            preview_width = max(int(disp_w * 0.25), 1)
            preview_height = int(preview_width * frame.shape[0] / max(frame.shape[1], 1))
            preview_height = min(preview_height, int(disp_h * 0.25))
            preview_width = int(preview_height * frame.shape[1] / max(frame.shape[0], 1))

            if preview_width > 0 and preview_height > 0:
                preview = cv2.resize(frame, (preview_width, preview_height))
                y1 = disp_h - preview_height - 10
                x1 = disp_w - preview_width - 10
                y2 = y1 + preview_height
                x2 = x1 + preview_width

                if y1 >= 0 and x1 >= 0 and y2 <= disp_h and x2 <= disp_w:
                    display[y1:y2, x1:x2] = preview
                    cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 0), 1)
                    cv2.putText(display, "Camera", (x1 + 5, y1 + 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

        # Resize display to current window size so the whiteboard fills the screen
        try:
            _, _, win_w, win_h = cv2.getWindowImageRect('Virtual Whiteboard')
            if win_w > 0 and win_h > 0 and (win_w != display.shape[1] or win_h != display.shape[0]):
                display_to_show = cv2.resize(display, (win_w, win_h), interpolation=cv2.INTER_LINEAR)
            else:
                display_to_show = display
        except Exception:
            display_to_show = display

        # Show the whiteboard
        cv2.imshow('Virtual Whiteboard', display_to_show)

        # Exit on 'q', 'Q', or ESC key, or window close button
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q') or key == 27:  # 27 is ESC key
            break
        elif key == ord('s') or key == ord('S'):
            # Save only the drawing canvas (without UI/camera preview) to a timestamped PNG
            save_canvas = np.ones_like(canvas) * 255
            for stroke in strokes:
                pts = stroke['points']
                if len(pts) > 1:
                    for i in range(len(pts) - 1):
                        cv2.line(save_canvas, pts[i], pts[i + 1], stroke['color'], stroke['thickness'])
            if current_stroke:
                pts = current_stroke['points']
                if len(pts) > 1:
                    for i in range(len(pts) - 1):
                        cv2.line(save_canvas, pts[i], pts[i + 1], current_stroke['color'], current_stroke['thickness'])

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"drawing_{timestamp}.png"
            try:
                cv2.imwrite(filename, save_canvas)
                print(f"Saved drawing to {os.path.abspath(filename)}")
            except Exception as e:
                print(f"[ERROR] Failed to save drawing: {e}")
        
        # Check if window was closed
        if cv2.getWindowProperty('Virtual Whiteboard', cv2.WND_PROP_VISIBLE) < 1:
            break

    # Clean up
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    print("Whiteboard closed.")

if __name__ == "__main__":
    main()