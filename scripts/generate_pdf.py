import subprocess
import time
import json
import base64
import os
import sys

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests', '-q'])
    import requests

try:
    import websocket
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websocket-client', '-q'])
    import websocket

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HTML_FILE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\blueprint_to_pdf.html"
OUTPUT_PDF = r"C:\Users\Nehoray_Cohen\Projects\Game translator\translation_manager_winhanced_master_blueprint2.pdf"
DEBUG_PORT = 9222

file_url = "file:///" + HTML_FILE.replace("\\", "/").replace(" ", "%20")

subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
time.sleep(1)

print("Launching Chrome...")
chrome_proc = subprocess.Popen([
    CHROME_PATH,
    f"--remote-debugging-port={DEBUG_PORT}",
    "--remote-allow-origins=*",
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-extensions",
    "--window-size=1200,1600",
    file_url
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(3)

try:
    resp = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json")
    targets = resp.json()
    
    ws_url = None
    for target in targets:
        if target.get("type") == "page":
            ws_url = target["webSocketDebuggerUrl"]
            break
    
    if not ws_url:
        print("ERROR: No page target found!")
        sys.exit(1)
    
    ws = websocket.create_connection(ws_url)
    msg_id = 1
    
    def send_cdp(method, params=None):
        global msg_id
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        ws.send(json.dumps(msg))
        
        while True:
            response = json.loads(ws.recv())
            if response.get("id") == msg_id:
                msg_id += 1
                return response
    
    send_cdp("Page.enable")
    time.sleep(2)
    
    print("Generating PDF...")
    result = send_cdp("Page.printToPDF", {
        "printBackground": True,
        "preferCSSPageSize": True,
        "paperWidth": 8.27,    # 210mm
        "paperHeight": 11.69,   # 297mm
        "marginTop": 0,
        "marginBottom": 0,
        "marginLeft": 0,
        "marginRight": 0,
        "displayHeaderFooter": False,
        "scale": 1.0
    })
    
    if "result" in result and "data" in result["result"]:
        pdf_data = base64.b64decode(result["result"]["data"])
        with open(OUTPUT_PDF, "wb") as f:
            f.write(pdf_data)
        file_size = os.path.getsize(OUTPUT_PDF)
        print(f"SUCCESS! PDF saved to: {OUTPUT_PDF}")
        print(f"Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    else:
        print("ERROR: Failed to generate PDF")
        print(json.dumps(result, indent=2))
    
    ws.close()

finally:
    chrome_proc.terminate()
    try:
        chrome_proc.wait(timeout=3)
    except:
        chrome_proc.kill()
    print("Chrome closed.")
