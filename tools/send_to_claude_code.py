#!/usr/bin/env python3
"""
Send text to the currently focused input (e.g. Claude Code in VS Code).

Usage:
  python tools/send_to_claude_code.py --test          # 60s demo, types seconds
  python tools/send_to_claude_code.py --delay 10800   # wait 10800s (3h) then send 'המשך' + Enter

Make sure the target input in VS Code is focused when the script types.
"""
from pynput.keyboard import Key, Controller
import time
import argparse
import sys


def select_all(kb: Controller):
    kb.press(Key.ctrl)
    kb.press('a')
    kb.release('a')
    kb.release(Key.ctrl)


def send_text(kb: Controller, text: str, press_enter: bool = False):
    select_all(kb)
    time.sleep(0.05)
    kb.type(text)
    if press_enter:
        kb.press(Key.enter)
        kb.release(Key.enter)


def run_test(duration_seconds: int = 60, final_text: str = "המשך", send_final: bool = True):
    kb = Controller()
    print(f"Test (countdown) mode: focus the Claude Code input now. Starting in 3 seconds...")
    time.sleep(3)
    end_time = time.time() + duration_seconds
    try:
        while True:
            remaining = int(max(0, end_time - time.time()))
            # Print countdown to the terminal (not into the chat input)
            print(f"seconds remaining: {remaining}", end='\r', flush=True)
            if remaining <= 0:
                break
            time.sleep(1)
        print()  # newline after the progress line
        if send_final:
            # after the countdown, send the final text into the focused chat input
            time.sleep(0.5)
            send_text(kb, final_text, press_enter=True)
            print(f"Sent final text: {final_text}")
    except KeyboardInterrupt:
        print("Test interrupted by user.")


def schedule_send(delay_seconds: int, text: str = "המשך"):
    kb = Controller()
    print(f"Scheduled: will send after {delay_seconds} seconds. Focus the Claude Code input when the time arrives.")
    try:
        # Sleep in small chunks so the user can see progress if running in terminal
        remaining = delay_seconds
        while remaining > 0:
            # print every 60s or last 10s
            if remaining % 60 == 0 or remaining <= 10:
                mins = remaining // 60
                secs = remaining % 60
                print(f"Time until send: {mins}m {secs}s")
            time.sleep(1)
            remaining -= 1

        print("Sending now: make sure the input is focused (typing will begin in 2s)...")
        time.sleep(2)
        send_text(kb, text, press_enter=True)
        print("Sent.")
    except KeyboardInterrupt:
        print("Scheduled send cancelled by user.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--delay', type=int, default=6000, help='Delay in seconds before sending (default 6000 = 1h40m)')
    parser.add_argument('--test', action='store_true', help='Run countdown test that updates seconds')
    parser.add_argument('--duration', type=int, default=6000, help='Duration for test/countdown mode in seconds (default 6000 = 1h40m)')
    parser.add_argument('--text', type=str, default='המשך', help='Text to send after delay')
    parser.add_argument('--no-send-on-complete', action='store_true', help='If set, do not send final text when test completes')
    args = parser.parse_args()

    if args.test:
        send_final = not args.no_send_on_complete
        run_test(args.duration, final_text=args.text, send_final=send_final)
        return

    # Scheduling mode
    schedule_send(args.delay, text=args.text)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('Error:', e)
        sys.exit(1)
