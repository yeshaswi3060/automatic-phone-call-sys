import subprocess
import time
import os

def capture_screen_xml():
    adb_path = "platform-tools\\adb.exe"
    phone_number = "9217555449"
    message = "Testing SMS Diagnostic"
    
    print("Opening Samsung Messaging app...")
    # Launch the app using monkey
    subprocess.run([
        adb_path, "shell", "monkey", "-p", "com.samsung.android.messaging", 
        "-c", "android.intent.category.LAUNCHER", "1"
    ])
    
    time.sleep(5)
    
    print(f"Directing to {phone_number}...")
    # Use the intent but WITHOUT the failing pkg=SMS
    subprocess.run([
        adb_path, "shell", "am", "start", 
        "-a", "android.intent.action.VIEW", 
        "-d", f"sms:{phone_number}", 
        "--es", "sms_body", message
    ])
    
    time.sleep(4)
    
    print("Capturing screen XML...")
    subprocess.run([adb_path, "shell", "uiautomator", "dump", "/sdcard/diag.xml"])
    result = subprocess.run([adb_path, "shell", "cat", "/sdcard/diag.xml"], capture_output=True, text=True, errors="ignore")
    
    with open("screen_diagnostic.xml", "w", encoding="utf-8") as f:
        f.write(result.stdout)
    
    print("Done! XML saved to 'screen_diagnostic.xml'. Please check this file.")

if __name__ == "__main__":
    capture_screen_xml()
