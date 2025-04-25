#!/usr/bin/env python3
"""
Play a simple melody on the synth via OSC.
Useful for testing the synth's functionality.
"""

import argparse
import time
import sys
from pythonosc import udp_client

def midi_to_freq(note):
    """Convert MIDI note number to frequency"""
    return 440.0 * (2 ** ((note - 69) / 12))

def play_note(client, prefix, note, velocity, duration, release_time=0.05):
    """Play a single note with the given parameters"""
    # Calculate frequency
    freq = midi_to_freq(note)
    
    # Print info
    print(f"Note: {note} ({freq:.2f} Hz), vel: {velocity:.2f}, dur: {duration:.2f}s")
    
    # Send note on
    client.send_message(f"{prefix}/freq", freq)
    client.send_message(f"{prefix}/gain", velocity)
    client.send_message(f"{prefix}/gate", 1)
    
    # Wait for note duration
    time.sleep(duration)
    
    # Send note off
    client.send_message(f"{prefix}/gate", 0)
    
    # Wait for release
    time.sleep(release_time)

def play_melody(client, synth_name, melody, tempo, velocity=0.8):
    """Play a melody defined as a list of (note, duration) pairs"""
    # Format OSC path
    path_prefix = f"/{synth_name}"
    
    # Calculate beat duration in seconds
    beat_duration = 60.0 / tempo
    
    print(f"Playing melody at {tempo} BPM ({beat_duration:.2f}s per beat)")
    
    # Play each note
    for i, (note, duration) in enumerate(melody):
        # Convert duration in beats to seconds
        duration_sec = duration * beat_duration
        
        # Play note
        print(f"[{i+1}/{len(melody)}] ", end="")
        play_note(client, path_prefix, note, velocity, duration_sec)

def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Play a melody via OSC")
    parser.add_argument("-p", "--port", type=int, default=5510, 
                        help="Synth OSC port (default: 5510)")
    parser.add_argument("-H", "--host", type=str, default="127.0.0.1",
                        help="Synth host (default: 127.0.0.1)")
    parser.add_argument("-s", "--synth-name", type=str, default="simple",
                        help="Synth name for OSC path (default: simple)")
    parser.add_argument("-t", "--tempo", type=float, default=120.0,
                        help="Tempo in BPM (default: 120)")
    parser.add_argument("-m", "--melody", type=str, default="scales",
                        choices=["scales", "twinkle", "jingle", "blues", "improv"],
                        help="Melody to play (default: scales)")
    
    args = parser.parse_args()
    
    # Create OSC client
    client = udp_client.SimpleUDPClient(args.host, args.port)
    print(f"Connected to OSC at {args.host}:{args.port}")
    
    # Define melodies
    melodies = {
        # C major scale up and down
        "scales": [
            (60, 0.5), (62, 0.5), (64, 0.5), (65, 0.5), (67, 0.5), (69, 0.5), (71, 0.5), (72, 1.0),
            (72, 0.5), (71, 0.5), (69, 0.5), (67, 0.5), (65, 0.5), (64, 0.5), (62, 0.5), (60, 1.0)
        ],
        
        # Twinkle Twinkle Little Star
        "twinkle": [
            (60, 1.0), (60, 1.0), (67, 1.0), (67, 1.0),  # Twinkle twinkle
            (69, 1.0), (69, 1.0), (67, 2.0),              # little star
            (65, 1.0), (65, 1.0), (64, 1.0), (64, 1.0),  # How I wonder
            (62, 1.0), (62, 1.0), (60, 2.0)               # what you are
        ],
        
        # Jingle Bells (beginning)
        "jingle": [
            (64, 1.0), (64, 1.0), (64, 2.0),             # Jin-gle bells
            (64, 1.0), (64, 1.0), (64, 2.0),             # jin-gle bells
            (64, 1.0), (67, 1.0), (60, 1.0), (62, 1.0),  # jin-gle all the
            (64, 4.0)                                     # way
        ],
        
        # Simple blues riff
        "blues": [
            (60, 0.5), (63, 0.5), (64, 0.5), (65, 0.5),  # Blues scale fragment
            (66, 0.5), (65, 0.5), (64, 0.5), (63, 0.5),  # Back down
            (60, 1.0), (67, 1.0),                         # Jump to dom7
            (66, 0.5), (65, 0.5), (64, 0.5), (63, 0.5),  # Walking down
            (60, 2.0)                                     # Resolve
        ],
        
        # Improvised melody with different durations
        "improv": [
            (64, 0.5), (67, 0.25), (69, 0.25), (71, 1.0), # Phrase 1
            (69, 0.5), (67, 0.5), (64, 1.0),              # Phrase 2
            (62, 0.25), (64, 0.25), (65, 0.25), (67, 0.25), # Faster notes
            (69, 0.5), (71, 0.5), (72, 1.0),               # Climax
            (71, 0.5), (69, 0.5), (67, 0.5), (64, 0.5),    # Descending
            (62, 0.5), (60, 1.5)                           # Resolution
        ]
    }
    
    # Get selected melody
    if args.melody in melodies:
        melody = melodies[args.melody]
    else:
        print(f"Unknown melody: {args.melody}")
        return 1
    
    try:
        # Play the melody
        play_melody(client, args.synth_name, melody, args.tempo)
        
        # Send all notes off at the end
        print("Finished melody. Sending all notes off.")
        client.send_message(f"/{args.synth_name}/gate", 0)
        client.send_message(f"/{args.synth_name}/allNotesOff", 1)
        client.send_message(f"/{args.synth_name}/panic", 1)
        
    except KeyboardInterrupt:
        print("\nInterrupted! Sending all notes off.")
        client.send_message(f"/{args.synth_name}/gate", 0)
        client.send_message(f"/{args.synth_name}/allNotesOff", 1)
        client.send_message(f"/{args.synth_name}/panic", 1)
        return 1
    
    print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main())