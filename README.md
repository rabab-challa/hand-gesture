# Virtual Whiteboard with Hand Gestures

This Python project allows users to draw on a virtual whiteboard using hand gestures captured from a webcam. It uses OpenCV for camera access and image processing, and MediaPipe for real-time hand tracking.

## Features

- Real-time hand gesture recognition
- Drawing with index finger
- Gesture-based controls:
  - Index finger up: Drawing mode
  - Index + middle fingers up: Selection mode
- 3 pen colors: Blue, Green, Red
- Adjustable pen thickness: Thin, Medium, Thick
- Eraser mode to remove drawn strokes
- On-screen UI elements for easy interaction
- Smooth drawing with motion tracking

## Requirements

- Python 3.x
- Webcam
- Libraries: OpenCV, MediaPipe

## Installation

1. Clone or download the project files.
2. Install the required libraries:

   ```
   pip install -r requirements.txt
   ```

   Or manually:

   ```
   pip install opencv-python mediapipe
   ```

## Usage

1. Run the main script:

   ```
   python main.py
   ```

2. A window titled "Virtual Whiteboard" will appear showing the white canvas with UI buttons.
3. Position your hand in front of the webcam.
4. Use gestures to interact:
   - Raise only your index finger to enter drawing mode and draw on the canvas.
   - Raise your index and middle fingers to enter selection mode.
   - In selection mode, touch the on-screen buttons to change color, thickness, or activate eraser.
   - In eraser mode, move your index finger over drawn strokes to erase them.
5. Press 'q' to quit the application.

## Project Structure

- `main.py`: Main application script
- `hand_tracking_module.py`: Reusable hand detection and tracking logic
- `requirements.txt`: List of required Python packages

## Notes

- Ensure good lighting for better hand tracking.
- The application assumes a single hand is being tracked.
- If the camera cannot be accessed, an error message will be displayed.
- The canvas size is set to 640x480 pixels; you can adjust this in the code if needed.