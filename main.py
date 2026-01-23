import cv2
import numpy as np
import time
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
    canvas_width, canvas_height = 640, 480
    canvas = np.ones((canvas_height, canvas_width, 3), np.uint8) * 255  # White canvas

    # Drawing settings
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # Blue, Green, Red (BGR)
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
    buttons = {
        'color_blue': (10, 10, 60, 60),
        'color_green': (80, 10, 130, 60),
        'color_red': (150, 10, 200, 60),
        'thin': (10, 80, 60, 130),
        'medium': (80, 80, 130, 130),
        'thick': (150, 80, 200, 130),
        'eraser': (10, 150, 60, 200)
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
                color_name = name.split('_')[1]
                if (color_name == 'blue' and current_color == colors[0]) or \
                   (color_name == 'green' and current_color == colors[1]) or \
                   (color_name == 'red' and current_color == colors[2]):
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
                color_name = name.split('_')[1]
                if color_name == 'blue':
                    cv2.circle(img, (center_x, center_y), 15, colors[0], -1)
                elif color_name == 'green':
                    cv2.circle(img, (center_x, center_y), 15, colors[1], -1)
                elif color_name == 'red':
                    cv2.circle(img, (center_x, center_y), 15, colors[2], -1)
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
    cv2.resizeWindow('Virtual Whiteboard', 640, 480)
    
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
            if lm_list and len(lm_list) >= 21:
                current_fingers = tracker.fingers_up(lm_list)

        if lm_list and len(lm_list) >= 21 and len(current_fingers) == 5:
            fingers = current_fingers
            if len(fingers) == 5:  # Ensure we got valid finger states
                index_tip = lm_list[8]  # Index finger tip
                x, y = index_tip[1], index_tip[2]

                # Determine mode based on gestures
                if fingers == [0, 1, 0, 0, 0]:  # Only index finger up
                    if eraser_mode:
                        # In eraser mode, index finger is for erasing (handled separately)
                        drawing_mode = False
                        selection_mode = False
                    else:
                        # Normal drawing mode
                        drawing_mode = True
                        selection_mode = False
                elif fingers == [0, 1, 1, 0, 0]:  # Index and middle fingers up
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
                else:
                    # Stop current stroke if not drawing
                    if current_stroke:
                        strokes.append(current_stroke)
                        current_stroke = None

                # Handle selection (with debouncing)
                if selection_mode:
                    button_press_cooldown = max(0, button_press_cooldown - 1)
                    
                    # Clamp coordinates to canvas bounds for button detection
                    x_btn = max(0, min(canvas_width - 1, x))
                    y_btn = max(0, min(canvas_height - 1, y))
                    
                    for name, (x1, y1, x2, y2) in buttons.items():
                        # Check if finger is over button (with larger margin for easier selection)
                        margin = 10  # Increased margin
                        if (x1 - margin) <= x_btn <= (x2 + margin) and (y1 - margin) <= y_btn <= (y2 + margin):
                            hovered_button_name = name
                            
                            # Only trigger if this is a new button press (debouncing)
                            if name != last_selected_button and button_press_cooldown == 0:
                                if name == 'color_blue':
                                    current_color = colors[0]
                                    print("✓ Selected: Blue color")
                                elif name == 'color_green':
                                    current_color = colors[1]
                                    print("✓ Selected: Green color")
                                elif name == 'color_red':
                                    current_color = colors[2]
                                    print("✓ Selected: Red color")
                                elif name == 'thin':
                                    current_thickness = thicknesses[0]
                                    print("✓ Selected: Thin brush")
                                elif name == 'medium':
                                    current_thickness = thicknesses[1]
                                    print("✓ Selected: Medium brush")
                                elif name == 'thick':
                                    current_thickness = thicknesses[2]
                                    print("✓ Selected: Thick brush")
                                elif name == 'eraser':
                                    # Toggle eraser mode
                                    if eraser_mode:
                                        eraser_mode = False
                                        drawing_mode = True
                                        print("✓ Eraser mode deactivated - back to drawing")
                                    else:
                                        eraser_mode = True
                                        drawing_mode = False
                                        selection_mode = False
                                        print("✓ Eraser mode activated - use index finger to erase")
                                
                                last_selected_button = name
                                button_press_cooldown = 15  # Increased cooldown frames
                                break
                else:
                    # Reset button selection when not in selection mode
                    if last_selected_button is not None:
                        last_selected_button = None
                        button_press_cooldown = 0

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
        else:
            # If no hand detected, stop current stroke
            if current_stroke:
                strokes.append(current_stroke)
                current_stroke = None

        # Create display canvas
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

        # Draw UI
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
            mode_text = f"MODE: DRAWING (Color: {['Blue', 'Green', 'Red'][colors.index(current_color)]}, Thickness: {current_thickness}px)"
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
            cv2.circle(display, (ex, ey), 25, (0, 0, 255), 2)  # Red circle indicator
        
        # Show the whiteboard
        cv2.imshow('Virtual Whiteboard', display)

        # Exit on 'q', 'Q', or ESC key, or window close button
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q') or key == 27:  # 27 is ESC key
            break
        
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