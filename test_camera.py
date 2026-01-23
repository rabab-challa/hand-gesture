# -*- coding: utf-8 -*-
import cv2
for i in range(4):
    cap = cv2.VideoCapture(i)
    print("index", i, "opened=", cap.isOpened())
    if cap.isOpened():
        cap.release()
