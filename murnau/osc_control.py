from pythonosc import udp_client
import time

# Create OSC client
client = udp_client.SimpleUDPClient("127.0.0.1", 5510)
print("OSC client initialized - sending to 127.0.0.1:5510")

# Program name from your terminal output
PROGRAM_NAME = "simple_saw"

try:
    # Turn off gate initially
    print("Setting gate OFF")
    client.send_message(f"/{PROGRAM_NAME}/gate", 0.0)
    time.sleep(0.5)
    
    # Set initial frequency
    print("Setting initial frequency to 440 Hz")
    client.send_message(f"/{PROGRAM_NAME}/freq", 440.0)
    time.sleep(0.5)
    
    # Turn on gate
    print("Setting gate ON")
    client.send_message(f"/{PROGRAM_NAME}/gate", 1.0)
    time.sleep(1.0)
    
    # Test different frequencies
    test_frequencies = [
        (110.0, "A2 - 110 Hz"),
        (293.66, "D4 - 293.66 Hz"),
        (329.63, "E4 - 329.63 Hz"),
        (392.0, "G4 - 392 Hz"),
        (440.0, "A4 - 440 Hz"),
        (493.88, "B4 - 493.88 Hz"),
        (523.25, "C5 - 523.25 Hz")
    ]
    
    for freq, name in test_frequencies:
        print(f"Playing {name}")
        client.send_message(f"/{PROGRAM_NAME}/freq", freq)
        time.sleep(2.0)  # Play each note for 2 seconds
    
except KeyboardInterrupt:
    print("\nStopping...")
    
finally:
    # Always turn off gate when done
    print("Setting gate OFF")
    client.send_message(f"/{PROGRAM_NAME}/gate", 0.0)
    print("Test complete")