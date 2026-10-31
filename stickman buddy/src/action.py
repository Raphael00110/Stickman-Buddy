import pyautogui
import time


class ActionEngine:
    def __init__(self):

        # if the cursor goes out of bound
        pyautogui.FAILSAFE = True

    def smash_button(self, target_x, target_y):

        # give animation some tiem
        time.sleep(0.3)

        # click to this location (provided by percemtion)
        pyautogui.click(x=target_x, y=target_y)
        print(f"Stickman clicked at coordinates: x: {target_x} and y:{target_y}")

    def walk_and_pull(self, from_x, to_x, y_coordinate):

        # snaps to the starting position
        pyautogui.moveTo(from_x, y_coordinate)

        # drag to the target_x position on the span on 0.8 seconds
        pyautogui.dragTo(to_x, y_coordinate, duration=0.8, button='left')