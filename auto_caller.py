import subprocess
import time
import os
from datetime import datetime
import pandas as pd
import pygame

# Initialize Pygame Mixer for high-quality, loud audio playback
# 44100Hz frequency prevents "glittery" or static sound
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.mixer.init()

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
            capture_output=True, text=True, errors="ignore", check=True
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

def play_recorded_message(file_path):
    """Plays an MP3 file at maximum software volume."""
    if not os.path.exists(file_path):
        print(f"[ERROR] Audio file '{file_path}' not found! Skipping playback.")
        return

    print(f"[AUDIO] Playing '{file_path}' at MAX volume...")
    try:
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.set_volume(1.0) # Set software volume to 100%
        pygame.mixer.music.play()
        
        # Wait until the audio finishes playing
        while pygame.mixer.music.get_busy():
            time.sleep(0.5)
            
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"[ERROR] Failed to play audio: {e}")

import re

def send_sms(phone_number, message):
    """Sends a plain text SMS by explicitly typing and clicking the Send button."""
    print(f"[SMS] Sending follow-up message to {phone_number}...")
    
    adb_path = "platform-tools\\adb.exe"
    
    # 1. Open Samsung Messaging app for this specific number
    subprocess.run([
        adb_path, "shell", "am", "start", 
        "-a", "android.intent.action.VIEW", 
        "-d", f"sms:{phone_number}", 
        "com.samsung.android.messaging"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    time.sleep(3) # Wait for app to load
    
    # 2. Click the Message Edit Box to ensure it's focused
    # Coordinates from dump: [95,892][609,981] -> Center: (352, 936)
    print("[SMS] Focusing text box...")
    subprocess.run([adb_path, "shell", "input", "tap", "352", "936"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)

    # 3. Type the message
    # ADB 'input text' doesn't like spaces, so we replace them with %s
    formatted_msg = message.replace(" ", "%s")
    print(f"[SMS] Typing: {message}")
    subprocess.run([adb_path, "shell", "input", "text", formatted_msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

    # 4. Click the Send Button
    # Coordinates from dump: [632,914][699,981] -> Center: (665, 947)
    print("[SMS] Clicking Send...")
    subprocess.run([adb_path, "shell", "input", "tap", "665", "947"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    # 5. Backup Send Triggers: Try Enter key and a slightly different coordinate
    # (Sometimes the keyboard shift or a missed tap needs a second attempt)
    subprocess.run([adb_path, "shell", "input", "keyevent", "66"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # Enter
    time.sleep(0.5)
    subprocess.run([adb_path, "shell", "input", "tap", "670", "950"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # Slightly offset tap
    
    # Back to home to clean up for next call
    time.sleep(2)
    subprocess.run([adb_path, "shell", "input", "keyevent", "3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[SMS] Message sent flow finished.")

def wait_for_pickup():
    """Continuously checks the Android Telecom system to see when the call is picked up."""
    print("Waiting for the user to pick up the call...")
    
    # We must give the Android Telecom stack a few seconds to transition from IDLE (0) -> DIALING (1).
    # If we check instantly, the state will still be 0, and the script will think the call was rejected.
    time.sleep(3)
    
    # We will poll ADB every 2 seconds
    while True:
        try:
            # dumpsys telephony.registry is much more reliable for finding mCallState 
            # mCallState: 0 = IDLE, 1 = RINGING (Incoming), 2 = OFFHOOK (Dialing/Active)
            # mForegroundCallState: 0 = IDLE/DIALING, 1 = ACTIVE (User picked up!)
            result = subprocess.run(
                ["platform-tools\\adb.exe", "shell", "dumpsys", "telephony.registry"],
                capture_output=True, text=True, errors="ignore", check=True
            )
            output = result.stdout
            
            call_state = 0
            fg_state = 0
            
            # Find the FIRST occurrence of mCallState and mForegroundCallState in the registry
            for line in output.split('\n'):
                if 'mCallState=' in line:
                    call_state = int(line.split('=')[1].strip())
                elif 'mForegroundCallState=' in line:
                    fg_state = int(line.split('=')[1].strip())
                    break # We found both for Phone Id 0, stop searching
            
            # If the Foreground State is 1, the call is officially connected and active!
            if fg_state == 1:
                print("\n[SYSTEM] Call has been PICKED UP! Starting AI...")
                return True
                
            # If the overall Call State goes back to 0, they hung up or rejected
            elif call_state == 0:
                print("\n[SYSTEM] Call was disconnected or rejected.")
                return False
        
        except subprocess.CalledProcessError:
            pass # ADB glitch, keep trying
            
        time.sleep(2)


def main():
    # 1. Verify connection first
    if not is_phone_connected():
        return # Stop the script if no phone is found

    # 2. Configuration
    # Put your recorded MP3 file name here
    audio_file = "message.mp3" 
    
    # Put your follow-up SMS text here
    sms_text = "Hello!! this is just a testing thing done by AllCLoths"

    numbers_to_call = [
        "8709633071",
        # "9451950686",
        # "",
        # "7042113408",
        # "9905026560",
        "" 
    ]
    
    # 3. List to store the results of each call
    call_results = []

    for number in numbers_to_call:
        if not number.strip():
            continue
            
        print(f"\n--- Starting call flow for {number} ---")
        call_number(number)
        
        # Poll ADB to see exactly when they pick up
        picked_up = wait_for_pickup()
        
        duration = 0
        if picked_up:
            start_time = datetime.now()
            
            # Wait 1 second so the user can put the phone to their ear
            time.sleep(1)
            
            # Play the recorded message instead of live AI
            play_recorded_message(audio_file)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            status = "Answered"
        else:
            status = "Missed/Rejected"
        
        # Hang up the call
        end_call()
        
        # Send follow-up SMS to EVERYONE regardless of whether they answered
        send_sms(number, sms_text)
        
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
