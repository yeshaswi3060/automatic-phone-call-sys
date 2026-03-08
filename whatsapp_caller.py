import subprocess
import time
from datetime import datetime
import pandas as pd

# ==============================================================================
# WHATSAPP AUTOMATION VIA ADB
# Note: Because WhatsApp calls are not standard phone calls, we automate them 
# by simulating human screen taps (X, Y coordinates) and swipes.
# If your phone screen resolution is different, you may need to tweak the X,Y coordinates.
# ==============================================================================

def is_phone_connected():
    """Checks if an Android device is successfully connected via ADB."""
    print("Checking phone connection...")
    try:
        result = subprocess.run(
            ["platform-tools\\adb.exe", "devices"], 
            capture_output=True, text=True, check=True
        )
        output_lines = result.stdout.strip().split('\n')
        
        if len(output_lines) > 1 and "device" in output_lines[1]:
            print("\n[SYSTEM] ALRIGHT! Phone is successfully connected and ADB is ready to go!\n")
            return True
        else:
            print("\n[ERROR] No phone detected! Please make sure your phone is plugged in via USB and 'USB Debugging' is enabled.")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] ADB is not installed or there is an issue: {e}")
        return False

def make_whatsapp_call(phone_number):
    print(f"\n--- Initiating WhatsApp Call to {phone_number} ---")
    
    # 1. Open a WhatsApp direct chat window to this exact number
    # This uses a special Android intent that bypasses the "Search Contact" screen
    # WhatsApp requires the country code! Assuming India (+91) for this example:
    if not phone_number.startswith("+"):
        phone_number = "+91" + phone_number 
        
    print(f"Opening chat for {phone_number}...")
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "am", "start", "-a", "android.intent.action.VIEW", 
         "-d", f"https://api.whatsapp.com/send?phone={phone_number.replace('+', '')}",
         "-p", "com.whatsapp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
    # Give WhatsApp 4 seconds to fully load the chat screen
    time.sleep(4)
    
    # 2. Tap the Voice Call icon (Top right of the screen)
    # Coordinates for exactly where the phone icon is on most Android phones.
    # Note: X=850, Y=150 usually hits the phone icon on a standard 1080p screen.
    print("Tapping the 'Voice Call' button...")
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "input", "tap", "850", "150"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    
def end_whatsapp_call():
    print("Ending WhatsApp call...")
    # The End Call button in WhatsApp is usually a big red button at the bottom center.
    # Coordinates X=540, Y=1900 works for most standard 1080x2400 screens.
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "input", "tap", "540", "1900"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def wait_for_whatsapp_pickup():
    """Detects when a WhatsApp call goes from Ringing -> Connected using UI screen reading"""
    print("Waiting for the user to pick up the WhatsApp call (Simulating human visually checking screen)...")
    
    import re
    # Give it 3 seconds to actually initiate the ringing state 
    time.sleep(3)
    
    while True:
        try:
            # 1. Ask Android to dump the current screen text to an XML file
            subprocess.run(
                ["platform-tools\\adb.exe", "shell", "uiautomator", "dump"],
                capture_output=True, text=True, check=True
            )
            
            # 2. Read that XML file
            result = subprocess.run(
                ["platform-tools\\adb.exe", "shell", "cat", "/sdcard/window_dump.xml"],
                capture_output=True, text=True, errors="ignore", check=True
            )
            output = result.stdout
            
            # 3. Simulate a human looking at the screen:
            # If the screen shows a timer like "00:00" or "01:23", the call answered!
            if re.search(r'text="\d{1,2}:\d{2}"', output):
                print("\n[SYSTEM] WhatsApp Call has been PICKED UP! (Call timer detected on screen) Starting AI...")
                return True
                
            # If the screen still says "Calling" or "Ringing", we keep waiting
            elif "Calling" in output or "Ringing" in output:
                pass # Still waiting for them to pick up
                
            # If we don't see the call text AND we don't see the timer, the call screen closed (They hung up)
            else:
                # Double check to make sure the screen actually closed
                time.sleep(1)
                subprocess.run(["platform-tools\\adb.exe", "shell", "uiautomator", "dump"], capture_output=True)
                res2 = subprocess.run(["platform-tools\\adb.exe", "shell", "cat", "/sdcard/window_dump.xml"], capture_output=True, text=True, errors="ignore")
                
                if not re.search(r'text="\d{1,2}:\d{2}"', res2.stdout) and "Calling" not in res2.stdout and "Ringing" not in res2.stdout:
                    print("\n[SYSTEM] WhatsApp Call was disconnected or rejected.")
                    return False
        
        except subprocess.CalledProcessError:
            pass # Ignore ADB glitches
            
        time.sleep(1) # uiautomator takes about a second to run, so standard sleep is fine


def main():
    if not is_phone_connected():
        return

    # Put your list of phone numbers here (No spaces or dashes)
    numbers_to_call = [
        "8709633071",
        "1234567890" 
    ]
    
    call_results = []

    for number in numbers_to_call:
        make_whatsapp_call(number)
        
        # Track pickup state using the Audio Manager method
        picked_up = wait_for_whatsapp_pickup()
        
        duration = 0
        if picked_up:
            start_time = datetime.now()
            
            print("Playing audio on laptop... (Person on phone will hear it!)")
            # In a more advanced script, you can trigger 'pygame' or 'playsound' here
            time.sleep(10) # Simulating 10 seconds of talking/audio playback
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            status = "Answered"
        else:
            status = "Missed/Rejected"
        
        # Send physical tap to hang up the WhatsApp call
        end_whatsapp_call()
        
        # Clean up - go back to the Android home screen so the next call starts fresh
        subprocess.run(["platform-tools\\adb.exe", "shell", "input", "keyevent", "3"])
        
        # Save result
        call_results.append({
            "WhatsApp Number": number,
            "Pickup Status": status,
            "Call Duration (Seconds)": round(duration, 1)
        })
        
        time.sleep(5) 

    # ==========================================
    # Generate Analytics Excel Sheet
    # ==========================================
    print("\n" + "="*40)
    print("ALL CALLS COMPLETE. Generating Report...")
    print("="*40)
    
    df = pd.DataFrame(call_results)
    
    answered_calls = df[df["Pickup Status"] == "Answered"]
    if not answered_calls.empty:
        avg_duration = answered_calls["Call Duration (Seconds)"].mean()
        print(f"Average WhatsApp Call Duration: {avg_duration:.1f} seconds")
    else:
        print("Average WhatsApp Call Duration: No calls were answered.")
        
    excel_filename = "whatsapp_call_log.xlsx"
    df.to_excel(excel_filename, index=False)
    print(f"\n✅ All WhatsApp call data saved to {excel_filename}!")


if __name__ == "__main__":
    main()
