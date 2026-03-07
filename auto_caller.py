import subprocess
import time
from datetime import datetime
import pandas as pd

def call_number(phone_number):
    print(f"Dialing {phone_number}...")
    # ADB command to start a phone call
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone_number}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def is_phone_connected():
    """Checks if an Android device is successfully connected via ADB."""
    print("Checking phone connection...")
    try:
        result = subprocess.run(
            ["platform-tools\\adb.exe", "devices"], 
            capture_output=True, text=True, check=True
        )
        output_lines = result.stdout.strip().split('\n')
        
        # 'adb devices' output always has a header line "List of devices attached"
        # Any lines after that are actual connected devices.
        if len(output_lines) > 1 and "device" in output_lines[1]:
            print("\n[SYSTEM] ALRIGHT! Phone is successfully connected and ADB is ready to go!\n")
            return True
        else:
            print("\n[ERROR] No phone detected! Please make sure your phone is plugged in via USB and 'USB Debugging' is enabled in Developer Options.")
            return False
            
    except FileNotFoundError:
        print("\n[ERROR] ADB is not installed or the path to 'platform-tools\\adb.exe' is incorrect.")
        return False
    except subprocess.CalledProcessError:
        print("\n[ERROR] Failed to run ADB. Is the ADB server hung?")
        return False


def end_call():
    print("Ending call...")
    # ADB command to simulate pressing the 'End Call' button (KeyCode 6)
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "input", "keyevent", "6"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def wait_for_pickup():
    """Continuously checks the Android Telecom system to see when the call is picked up."""
    print("Waiting for the user to pick up the call...")
    
    # We will poll ADB every 2 seconds
    while True:
        try:
            # dumpsys telecom contains the current state of all calls on the phone
            result = subprocess.run(
                ["platform-tools\\adb.exe", "shell", "dumpsys", "telecom"],
                capture_output=True, text=True, check=True
            )
            output = result.stdout
            
            # If the call is actively connected, telecom dumpsys will show state: ACTIVE
            if "state: ACTIVE" in output or "State: ACTIVE" in output:
                print("\n[SYSTEM] Call has been PICKED UP! Starting AI...")
                return True
                
            # If the call was rejected, missed, or failed, it will disappear or show DISCONNECTED
            if "state: DISCONNECTED" in output or "State: DISCONNECTED" in output:
                print("\n[SYSTEM] Call was disconnected or rejected.")
                return False
                
        except subprocess.CalledProcessError:
            pass # ADB might have glitched, just try again next loop
            
        time.sleep(2)


def main():
    # 1. Verify connection first
    if not is_phone_connected():
        return # Stop the script if no phone is found

    # 2. Put your list of phone numbers here
    numbers_to_call = [
        "1234567890",
        "0987654321" 
    ]
    
    # 3. List to store the results of each call
    call_results = []

    for number in numbers_to_call:
        print(f"\n--- Starting call flow for {number} ---")
        call_number(number)
        
        # Poll ADB to see exactly when they pick up
        picked_up = wait_for_pickup()
        
        duration = 0
        if picked_up:
            start_time = datetime.now()
            
            # Here is where you would normally run your Custom AI Logic
            print("Playing audio on laptop... (Person on phone will hear it!)")
            # In a more advanced script, you can trigger 'pygame' or 'playsound' here to play a .wav file.
            time.sleep(10) # Simulating 10 seconds of talking/audio playback
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            status = "Answered"
        else:
            status = "Missed/Rejected"
        
        # Hang up the call
        end_call()
        
        # Save the result to our tracking list
        call_results.append({
            "Phone Number": number,
            "Pickup Status": status,
            "Call Duration (Seconds)": round(duration, 1)
        })
        
        # Wait a few seconds before calling the next number
        time.sleep(5) 

    # ==========================================
    # 4. Generate the Analytics Excel Sheet
    # ==========================================
    print("\n" + "="*40)
    print("ALL CALLS COMPLETE. Generating Report...")
    print("="*40)
    
    df = pd.DataFrame(call_results)
    
    # Calculate Average Call Duration for those who picked up
    answered_calls = df[df["Pickup Status"] == "Answered"]
    if not answered_calls.empty:
        avg_duration = answered_calls["Call Duration (Seconds)"].mean()
        print(f"Average Call Duration (for answered calls): {avg_duration:.1f} seconds")
    else:
        print("Average Call Duration: No calls were answered.")
        
    # Export to Excel
    excel_filename = "call_log.xlsx"
    df.to_excel(excel_filename, index=False)
    print(f"\n✅ All call data has been successfully saved to {excel_filename} in this folder!")


if __name__ == "__main__":
    main()
