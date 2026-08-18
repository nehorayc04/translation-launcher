import time
import sys
import pyautogui
import pyperclip

seconds_to_wait = 10

def countdown(seconds):
    print(f"--- מתחיל ספירה לאחור ---")
    for i in range(seconds, 0, -1):
        mins, secs = divmod(i, 60)
        sys.stdout.write(f"\rזמן שנותר: {mins:02d}:{secs:02d}")
        sys.stdout.flush()
        time.sleep(1)

countdown(seconds_to_wait)

# העתקה ללוח
pyperclip.copy("המשך")
time.sleep(1) # נשימה לפני פעולה
# הדבקה
pyautogui.hotkey('ctrl', 'v')
time.sleep(0.5) # נשימה לפני ה-Enter
# שליחה
pyautogui.press('enter')

print("\nבוצע.")