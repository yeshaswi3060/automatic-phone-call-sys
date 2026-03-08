import os
import time
import speech_recognition as sr
import edge_tts
import asyncio
import pygame
from langdetect import detect
from groq import Groq
from openai import OpenAI
import subprocess
from dotenv import load_dotenv

# ==============================================================================
# 1. API KEYS AND SETUP
# ==============================================================================
# Load environment variables from the .env file in the same directory
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY_1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize OpenRouter Client (Uses the OpenAI library structure)
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Initialize Speech Recognition
recognizer = sr.Recognizer()
recognizer.energy_threshold = 150    # Massively increased sensitivity for quiet phone lines
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 1.0     # Gives the user 1 second to pause between words without cutting them off

# Initialize Conversation History
# We use Groq for the main conversation due to its speed
conversation_history = [
    {"role": "system", "content": "You are a helpful, friendly assistant on a phone call. Keep your answers brief, conversational, and under 2 sentences. Do not use emojis. If the user speaks English, reply in English. If the user speaks Hindi, reply in Hindi. Switch languages automatically."}
]

# Configure which LLM you want to use
# Options: "groq" or "openrouter"
LLM_PROVIDER = "groq" 

# Configure your AUX Microphone Input (Set inside main)
MIC_INDEX = None

def auto_detect_mic():
    """Automatically finds the index of the Realtek AUX input."""
    import speech_recognition as sr
    devices = sr.Microphone.list_microphone_names()
    for i, name in enumerate(devices):
        # Based on user logs, this is the exact string that appears when plugged in
        if "Realtek HD Audio Mic input" in name:
            return i
    return None


# ==============================================================================
# 2. CORE FUNCTIONS
# ==============================================================================

def listen_to_user():
    """Listens to the microphone and converts speech to text."""
    global MIC_INDEX
    
    try:
        # We REMOVED sample_rate=44100 because forcing a rate can cause some 
        # Realtek drivers to fail to connect to the stream (NoneType crash).
        # We let the driver choose its own native rate.
        with sr.Microphone(device_index=MIC_INDEX) as source:
            print("\n[AI] Listening...")
            # Minimal noise adjustment
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            
            try:
                # Listen for the user's voice
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
                print("[AI] Processing speech...")
                
                # Use Google's speech recognition
                text = recognizer.recognize_google(audio, language="en-IN")  
                print(f"[USER SAYS]: {text}")
                return text
                
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                # If it's just a speech timeout/error, don't log it as critical
                return None
                
    except Exception as e:
        # This catches the 'NoneType' object error if the hardware fails to open
        print(f"\n[AI] (Microphone Index {MIC_INDEX} is currently busy or unavailable. Retrying...)")
        time.sleep(1)
        return None


def get_llm_response(user_text):
    """Sends the user's text to the LLM and gets a response."""
    global conversation_history
    
    # Add user's message to history
    conversation_history.append({"role": "user", "content": user_text})
    
    print(f"[AI] Thinking (using {LLM_PROVIDER})...")
    
    try:
        reply_text = ""
        
        if LLM_PROVIDER == "groq":
            # Groq is blazingly fast - great for voice calls
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant", # Using the updated, supported Llama model on Groq
                messages=conversation_history,
                temperature=0.7,
                max_tokens=150
            )
            reply_text = completion.choices[0].message.content
            
        elif LLM_PROVIDER == "openrouter":
            # OpenRouter gives you access to Claude, GPT-4, etc.
            completion = openrouter_client.chat.completions.create(
                model="openai/gpt-3.5-turbo", # Change to whatever model you prefer
                messages=conversation_history,
                temperature=0.7,
                max_tokens=150
            )
            reply_text = completion.choices[0].message.content
            
        # Add AI's response to history
        conversation_history.append({"role": "assistant", "content": reply_text})
        print(f"[AI SAYS]: {reply_text}")
        return reply_text
        
    except Exception as e:
        print(f"[AI ERROR]: {e}")
        return "I'm sorry, I'm having trouble connecting to my brain right now."

# Initialize Pygame Mixer for audio playback
# Setting frequency to 44100Hz perfectly matches Edge-TTS output
# This prevents audio stretching, static, or the "glittering" robotic artifacts!
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.mixer.init()

def speak(text):
    """Converts text to speech using Edge TTS (high quality) and plays it."""
    
    # We dynamically detect the language the LLM wants to talk in
    # so we can give it the correct accent!
    try:
        language = detect(text)
    except:
        language = "en" # Fallback to english if detection fails
        
    if language == 'hi':
        # Microsoft's highly realistic Indian female voice
        voice = "hi-IN-SwaraNeural" 
    else:
        # Microsoft's highly realistic American female voice
        voice = "en-US-AriaNeural" 
    
    temp_audio_file = "temp_response.mp3"
    
    # Edge-TTS is asynchronous, so we wrap it
    async def _generate_audio():
        # Added MAX volume boost and returned rate to normal speed for less robotic pitch shifting
        communicate = edge_tts.Communicate(text, voice, rate="+0%", volume="+100%") 
        await communicate.save(temp_audio_file)

    print("[AI] Generating voice...")
    # Generate the MP3
    asyncio.run(_generate_audio())
    
    # Play the MP3 using Pygame
    pygame.mixer.music.load(temp_audio_file)
    pygame.mixer.music.set_volume(1.0) # Force Pygame to play at maximum system volume
    pygame.mixer.music.play()
    
    # Wait until the audio is completely done playing before returning
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
        
    # Unload the file so we can overwrite it next time
    pygame.mixer.music.unload()


# ==============================================================================
# 3. CALL PHONE INTEGRATION
# ==============================================================================

def call_number(phone_number):
    print(f"Dialing {phone_number}...")
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone_number}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def end_call():
    print("Ending call...")
    subprocess.run(
        ["platform-tools\\adb.exe", "shell", "input", "keyevent", "6"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def wait_for_pickup():
    """Continuously checks the Android Telecom system to see when the call is picked up."""
    print("Waiting for the user to pick up the call...")
    
    # We will poll ADB every 2 seconds
    while True:
        try:
            # dumpsys telephony.registry is much more reliable for finding mCallState 
            # 0 = IDLE (Disconnected), 1 = RINGING (Dialing/Incoming), 2 = OFFHOOK (Connected/Active)
            result = subprocess.run(
                ["platform-tools\\adb.exe", "shell", "dumpsys", "telephony.registry"],
                capture_output=True, text=True, errors="ignore", check=True
            )
            output = result.stdout
            
            # Find the FIRST occurrence of mCallState in the registry
            state_lines = [line for line in output.split('\n') if 'mCallState' in line]
            
            if state_lines:
                # E.g. "mCallState=2" or "  mCallState=2"
                primary_state = state_lines[0].strip()
                
                if "mCallState=2" in primary_state:
                    print("\n[SYSTEM] Call has been PICKED UP! Starting AI...")
                    return True
                    
                # If we transition back from Dialing (1) to Idle (0) without hitting 2, they hung up / rejected
                elif "mCallState=0" in primary_state:
                    print("\n[SYSTEM] Call was disconnected or rejected.")
                    return False
        
        except subprocess.CalledProcessError:
            pass # ADB glitch, keep trying
            
        time.sleep(2)

def run_ai_conversation():
    """Runs the continuous loop of Listen -> Think -> Speak"""
    print("="*50)
    print("CALL CONNECTED. AI is now taking over the conversation.")
    print("Speak into your laptop mic (or the phone's received audio).")
    print("Press Ctrl+C to stop.")
    print("="*50)
    
    # Kick off the conversation in Hindi
    greeting = "नमस्ते! मैं आपकी एआई सहायक हूँ। मैं आज आपकी कैसे मदद कर सकती हूँ?"
    print(f"[AI SAYS]: {greeting}")
    speak(greeting)
    
    try:
        # The main conversation loop
        while True:
            # 1. Listen
            user_text = listen_to_user()
            
            if user_text:
                # 2. Think
                ai_reply = get_llm_response(user_text)
                
                # 3. Speak
                speak(ai_reply)
                
            # If silence, it just loops back and listens again
            
    except KeyboardInterrupt:
        print("\n[SYSTEM] Conversation stopped by user.")


def main():
    global MIC_INDEX
    
    # Make sure we actually found a key
    if not GROQ_API_KEY and LLM_PROVIDER == "groq":
        print("WARNING: You need to set your GROQ_API_KEY in the .env file!")
        return

    # 1. Setup Microphone / AUX Port
    print("="*50)
    print("AUDIO SETUP: Detecting AUX Port...")
    print("="*50)
    
    auto_mic = auto_detect_mic()
    if auto_mic is not None:
        MIC_INDEX = auto_mic
        print(f"-> SUCCESS: Automatically linked to AUX Mic (Index {MIC_INDEX})")
    else:
        print("-> WARNING: Could not auto-detect AUX cable. Fallback to manual selection:")
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"Device [{index}]: {name}")
        print("-"*50)
        mic_choice = input("Enter the Device Index of your AUX Phone Cable (or just press Enter for default): ")
        if mic_choice.strip():
            MIC_INDEX = int(mic_choice.strip())
            print(f"-> Set AI Microphone to Index {MIC_INDEX}")
        else:
            print("-> Using default system microphone.")
        
    print("\n")

    # You can test the AI locally without making a phone call first
    test_mode = input("Do you want to run purely in Test Mode (no phone call)? (y/n): ")
    
    if test_mode.lower() == 'y':
        run_ai_conversation()
    else:
        number = input("Enter the phone number to call: ")
        
        call_number(number)
        
        # Instead of waiting 15 seconds blindly, we poll ADB to see exactly when they pick up
        picked_up = wait_for_pickup()
        
        if picked_up:
            # Call is now live! Start the AI Loop
            run_ai_conversation()
        
        # When the AI loop breaks (e.g. you press Ctrl+C or call was rejected), hang up the phone
        end_call()
        

if __name__ == "__main__":
    main()
