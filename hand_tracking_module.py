import cv2
import mediapipe as mp

class HandTracker:
    """
    A class to handle hand tracking using MediaPipe.
    """
    def __init__(self, mode=False, max_hands=1, detection_conf=0.5, track_conf=0.5):
        """
        Initialize the HandTracker.

        Args:
            mode (bool): Whether to use static image mode.
            max_hands (int): Maximum number of hands to detect.
            detection_conf (float): Minimum detection confidence.
            track_conf (float): Minimum tracking confidence.
        """
        self.mode = mode
        self.max_hands = max_hands
        self.detection_conf = detection_conf
        self.track_conf = track_conf

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.max_hands,
            min_detection_confidence=self.detection_conf,
            min_tracking_confidence=self.track_conf
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.results = None

    def find_hands(self, img, draw=True):
        """
        Find hands in the image.

        Args:
            img: Input image.
            draw (bool): Whether to draw landmarks on the image.

        Returns:
            img: Image with landmarks drawn if draw=True.
        """
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.results = self.hands.process(img_rgb)

        if self.results.multi_hand_landmarks:
            for hand_lms in self.results.multi_hand_landmarks:
                if draw:
                    self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
        return img

    def get_positions(self, img, hand_no=0):
        """
        Get landmark positions for a specific hand.

        Args:
            img: Input image.
            hand_no (int): Hand index (0 for first hand).

        Returns:
            lm_list: List of [id, x, y] for each landmark.
        """
        lm_list = []
        if self.results.multi_hand_landmarks:
            if hand_no < len(self.results.multi_hand_landmarks):
                hand = self.results.multi_hand_landmarks[hand_no]
                for id, lm in enumerate(hand.landmark):
                    h, w, c = img.shape
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    lm_list.append([id, cx, cy])
        return lm_list

    def fingers_up(self, lm_list):
        """
        Determine which fingers are up.

        Args:
            lm_list: List of landmark positions.

        Returns:
            fingers: List of finger states (1 if up, 0 if down).
        """
        fingers = [0, 0, 0, 0, 0]  # Default: all fingers down
        if len(lm_list) >= 21:
            # Thumb
            if lm_list[4][1] < lm_list[3][1]:  # For right hand
                fingers[0] = 1
            # Index
            if lm_list[8][2] < lm_list[6][2]:
                fingers[1] = 1
            # Middle
            if lm_list[12][2] < lm_list[10][2]:
                fingers[2] = 1
            # Ring
            if lm_list[16][2] < lm_list[14][2]:
                fingers[3] = 1
            # Pinky
            if lm_list[20][2] < lm_list[18][2]:
                fingers[4] = 1
        return fingers