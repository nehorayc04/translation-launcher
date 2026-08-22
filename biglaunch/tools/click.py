import ctypes, sys, time
x,y = int(sys.argv[1]), int(sys.argv[2])
ctypes.windll.user32.SetCursorPos(x,y); time.sleep(0.15)
ctypes.windll.user32.mouse_event(2,0,0,0,0); time.sleep(0.05)
ctypes.windll.user32.mouse_event(4,0,0,0,0)
