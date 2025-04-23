#!/usr/bin/env python3
"""
OSC Router Debugging Patch

This script provides enhanced note tracking and debugging for the Caelus OSC system.
It intercepts OSC messages between midi_osc.py and the synthesizer, providing detailed
logging and automatic detection/correction of stuck notes.
"""

import argparse
import logging
import os
import sys
import time
import json
from collections import defaultdict, deque
from pythonosc import dispatcher, osc_server, udp_client
from pythonosc.udp_client import SimpleUDPClient
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("osc_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OSC_ROUTER_DEBUG")

class VoiceDebugger:
    """Tracks voice allocation and note states for debugging stuck notes"""
    
    def __init__(self, synth_port=9200):
        self.synth_port = synth_port
        self.synth_client = SimpleUDPClient("127.0.0.1", synth_port)
        
        # Track which notes are active on which voices
        self.voice_note_map = {}  # voice_id -> note_number
        self.note_voice_map = {}  # note_number -> voice_id
        self.note_timestamps = {}  # note_number -> timestamp when note was turned on
        self.active_voices = set()  # Set of active voice IDs
        
        # Historical tracking for diagnostics
        self.history_length = 100
        self.note_history = deque(maxlen=self.history_length)  # Recent note events
        self.voice_history = defaultdict(lambda: deque(maxlen=20))  # Voice -> recent notes
        self.note_durations = defaultdict(list)  # note_number -> list of durations (for pattern detection)
        
        # Enhanced tracking for stuck note forensics
        self.note_on_counts = defaultdict(int)     # Count note-on events per note
        self.note_off_counts = defaultdict(int)    # Count note-off events per note
        self.voice_usage_count = defaultdict(int)  # Track which voices are used most often
        self.problematic_notes = set()             # Track notes that have caused issues
        self.problematic_voices = set()            # Track voices that have had issues
        self.state_transitions = []                # History of major state transitions for forensics
        
        # Stuck note monitoring thresholds
        self.stuck_note_threshold = 15.0  # Seconds before a note is considered stuck
        self.inconsistency_check_interval = 30.0  # Seconds between consistency checks
        self.aggressive_check_interval = 5.0  # Faster checks for known problematic notes
        
        # Track the last time we sent a full state query
        self.last_state_query_time = 0
        self.last_consistency_check_time = 0
        self.last_aggressive_check_time = 0
        
        # Statistics
        self.stats = {
            "notes_processed": 0,
            "stuck_notes_detected": 0,
            "note_reassignments": 0,
            "inconsistencies_detected": 0,
            "emergency_resets": 0,
            "note_on_events": 0,
            "note_off_events": 0,
            "max_concurrent_notes": 0,
            "missed_note_off_events": 0,
            "problem_pattern_detected": 0
        }
        
        # Start the monitoring thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_stuck_notes)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Start a separate thread for analyzing patterns
        self.pattern_thread = threading.Thread(target=self._analyze_patterns)
        self.pattern_thread.daemon = True
        self.pattern_thread.start()
        
        # Log initialization
        logger.info("VoiceDebugger initialized with enhanced tracking and pattern detection")
        self._record_state_transition("initialized")
        
    def handle_note_on(self, voice_id, note_number, velocity):
        """Track a note-on event"""
        logger.info(f"NOTE ON: voice={voice_id}, note={note_number}, vel={velocity}")
        self.stats["notes_processed"] += 1
        self.stats["note_on_events"] += 1
        self.note_on_counts[note_number] += 1
        self.voice_usage_count[voice_id] += 1
        
        # Record start time for this note
        current_time = time.time()
        
        # Add to history
        event = {
            "type": "note_on",
            "voice": voice_id,
            "note": note_number,
            "velocity": velocity,
            "timestamp": current_time
        }
        self.note_history.append(event)
        self.voice_history[voice_id].append(event)
        
        # Check if this note is already playing on another voice
        if note_number in self.note_voice_map:
            old_voice = self.note_voice_map[note_number]
            logger.warning(f"Note {note_number} already assigned to voice {old_voice}, now reassigned to {voice_id}")
            self.stats["note_reassignments"] += 1
            self.problematic_notes.add(note_number)
            
            # Record this for pattern analysis
            self._record_state_transition(f"note_reassignment note={note_number} old_voice={old_voice} new_voice={voice_id}")
            
            # Send an explicit note-off to the old voice to prevent stuck notes
            self._send_note_off(old_voice, note_number)
            
            # Record duration of the previous instance if we have a timestamp
            if note_number in self.note_timestamps:
                duration = current_time - self.note_timestamps[note_number]
                self.note_durations[note_number].append(duration)
                logger.debug(f"Note {note_number} lasted {duration:.2f}s on voice {old_voice}")
        
        # Check if this voice is already playing another note
        if voice_id in self.voice_note_map:
            old_note = self.voice_note_map[voice_id]
            logger.warning(f"Voice {voice_id} already playing note {old_note}, now playing {note_number}")
            self.problematic_voices.add(voice_id)
            
            # Record this for pattern analysis
            self._record_state_transition(f"voice_overwrite voice={voice_id} old_note={old_note} new_note={note_number}")
            
            # Send an explicit note-off to ensure the old note is released
            self._send_note_off(voice_id, old_note)
            
            # Record duration of the previous note if we have a timestamp
            if old_note in self.note_timestamps:
                duration = current_time - self.note_timestamps[old_note]
                self.note_durations[old_note].append(duration)
                logger.debug(f"Note {old_note} lasted {duration:.2f}s on voice {voice_id}")
            
            # Mark the old note as off in our tracking maps
            if old_note in self.note_voice_map:
                del self.note_voice_map[old_note]
            if old_note in self.note_timestamps:
                del self.note_timestamps[old_note]
        
        # Update our tracking maps
        self.voice_note_map[voice_id] = note_number
        self.note_voice_map[note_number] = voice_id
        self.note_timestamps[note_number] = current_time
        self.active_voices.add(voice_id)
        
        # Update stats
        if len(self.note_voice_map) > self.stats["max_concurrent_notes"]:
            self.stats["max_concurrent_notes"] = len(self.note_voice_map)
        
    def handle_note_off(self, voice_id, note_number):
        """Track a note-off event"""
        logger.info(f"NOTE OFF: voice={voice_id}, note={note_number}")
        self.stats["note_off_events"] += 1
        self.note_off_counts[note_number] += 1
        
        current_time = time.time()
        
        # Add to history
        event = {
            "type": "note_off",
            "voice": voice_id,
            "note": note_number,
            "timestamp": current_time
        }
        self.note_history.append(event)
        self.voice_history[voice_id].append(event)
        
        # Record duration if we have a timestamp for this note
        if note_number in self.note_timestamps:
            duration = current_time - self.note_timestamps[note_number]
            self.note_durations[note_number].append(duration)
            logger.debug(f"Note {note_number} lasted {duration:.2f}s on voice {voice_id}")
        
        # Check for potential issues
        if voice_id not in self.voice_note_map:
            logger.warning(f"Note-off for voice {voice_id} which isn't in our tracking map")
            # Record this for pattern analysis
            self._record_state_transition(f"voice_not_tracked voice={voice_id} note={note_number}")
            
            # Try to find if this note exists in any voice
            for v, n in self.voice_note_map.items():
                if n == note_number:
                    logger.warning(f"Found note {note_number} on voice {v} instead of {voice_id}")
                    # Send note-off to the actual voice
                    self._send_note_off(v, note_number)
                    self.problematic_notes.add(note_number)
                    self.problematic_voices.add(voice_id)
                    self.problematic_voices.add(v)
                    self._record_state_transition(f"note_voice_mismatch note={note_number} expected_voice={voice_id} actual_voice={v}")
                    break
            else:
                # Note not found in any voice, count as missed note-off
                self.stats["missed_note_off_events"] += 1
            return
            
        if self.voice_note_map[voice_id] != note_number:
            logger.warning(f"Voice {voice_id} is playing note {self.voice_note_map[voice_id]}, not {note_number}")
            self.stats["inconsistencies_detected"] += 1
            self.problematic_notes.add(note_number)
            self.problematic_voices.add(voice_id)
            
            # Record this for pattern analysis
            actual_note = self.voice_note_map[voice_id]
            self._record_state_transition(f"note_mismatch voice={voice_id} expected_note={note_number} actual_note={actual_note}")
            
            # Fix the issue by sending note-off for the actual note
            logger.info(f"Sending corrected note-off for actual note {actual_note} on voice {voice_id}")
            self._send_note_off(voice_id, actual_note)
            
            # Also see if the requested note is playing on another voice
            if note_number in self.note_voice_map:
                actual_voice = self.note_voice_map[note_number]
                logger.info(f"Sending note-off for note {note_number} on its actual voice {actual_voice}")
                self._send_note_off(actual_voice, note_number)
                self._record_state_transition(f"fixing_note note={note_number} on_voice={actual_voice}")
            
        # Clean up our tracking maps
        if voice_id in self.voice_note_map:
            del self.voice_note_map[voice_id]
        if note_number in self.note_voice_map:
            del self.note_voice_map[note_number]
        if note_number in self.note_timestamps:
            del self.note_timestamps[note_number]
            
        # Mark voice as inactive
        if voice_id in self.active_voices:
            self.active_voices.remove(voice_id)
            
    def _send_note_off(self, voice_id, note_number):
        """Send an OSC note-off message directly to the synth"""
        logger.info(f"Sending emergency note-off: voice={voice_id}, note={note_number}")
        self.synth_client.send_message(f"/voice/{voice_id}/noteOff", [note_number, 0])
        
        # Also send allNotesOff as a backup
        self.synth_client.send_message(f"/voice/{voice_id}/allNotesOff", [1])
        
    def _record_state_transition(self, description):
        """Record a significant state transition for later analysis"""
        self.state_transitions.append({
            "timestamp": time.time(),
            "description": description,
            "active_notes": len(self.note_voice_map),
            "active_voices": len(self.active_voices)
        })
        
        # Keep only the last 100 transitions
        if len(self.state_transitions) > 100:
            self.state_transitions = self.state_transitions[-100:]
            
    def _monitor_stuck_notes(self):
        """Thread that monitors for stuck notes and clears them"""
        while self.running:
            current_time = time.time()
            
            # Check for notes that have been on too long (stuck)
            for note, timestamp in list(self.note_timestamps.items()):
                if current_time - timestamp > self.stuck_note_threshold:
                    if note in self.note_voice_map:
                        voice = self.note_voice_map[note]
                        logger.warning(f"Stuck note detected: note={note} on voice={voice} for {current_time - timestamp:.1f}s")
                        self.stats["stuck_notes_detected"] += 1
                        self.problematic_notes.add(note)
                        self.problematic_voices.add(voice)
                        self._record_state_transition(f"stuck_note_cleared note={note} voice={voice} duration={current_time-timestamp:.1f}")
                        self._send_note_off(voice, note)
                        
                        # Clean up tracking maps
                        if voice in self.voice_note_map:
                            del self.voice_note_map[voice]
                        if note in self.note_voice_map:
                            del self.note_voice_map[note]
                        if note in self.note_timestamps:
                            del self.note_timestamps[note]
                        if voice in self.active_voices:
                            self.active_voices.remove(voice)
            
            # More aggressive checking for known problematic notes/voices
            if self.problematic_notes or self.problematic_voices:
                if current_time - self.last_aggressive_check_time > self.aggressive_check_interval:
                    self.last_aggressive_check_time = current_time
                    self._aggressive_check()
            
            # Periodically check for consistency between our maps
            if current_time - self.last_consistency_check_time > self.inconsistency_check_interval:
                self.last_consistency_check_time = current_time
                self._check_state_consistency()
            
            # Periodically query the state of all voices
            if current_time - self.last_state_query_time > 60:  # Every 60 seconds
                self.last_state_query_time = current_time
                self.query_all_voice_states()
                self._log_statistics()
                
            time.sleep(0.5)  # Check twice per second
    
    def _aggressive_check(self):
        """More aggressive checking for known problematic notes/voices"""
        logger.debug("Performing aggressive check on problematic notes/voices...")
        
        # Look for problematic notes that might be stuck but not for long enough yet
        for note in self.problematic_notes:
            if note in self.note_timestamps:
                timestamp = self.note_timestamps[note]
                duration = time.time() - timestamp
                if duration > self.stuck_note_threshold / 2:  # Check at half the normal threshold
                    voice = self.note_voice_map.get(note)
                    if voice is not None:
                        logger.warning(f"Preemptively clearing problematic note {note} on voice {voice} after {duration:.1f}s")
                        self._send_note_off(voice, note)
                        self._record_state_transition(f"preemptive_clear note={note} voice={voice} duration={duration:.1f}")
                        
                        # Clean up tracking maps
                        if voice in self.voice_note_map:
                            del self.voice_note_map[voice]
                        if note in self.note_voice_map:
                            del self.note_voice_map[note]
                        if note in self.note_timestamps:
                            del self.note_timestamps[note]
                        if voice in self.active_voices and voice in self.voice_note_map:
                            if self.voice_note_map[voice] == note:
                                self.active_voices.remove(voice)
        
        # Check problematic voices
        for voice in self.problematic_voices:
            if voice in self.voice_note_map:
                note = self.voice_note_map[voice]
                if note in self.note_timestamps:
                    duration = time.time() - self.note_timestamps[note]
                    if duration > self.stuck_note_threshold / 2:  # Check at half the normal threshold
                        logger.warning(f"Preemptively clearing problematic voice {voice} playing note {note} for {duration:.1f}s")
                        self._send_note_off(voice, note)
                        self._record_state_transition(f"preemptive_voice_clear voice={voice} note={note} duration={duration:.1f}")
                        
                        # Clean up tracking maps
                        if voice in self.voice_note_map:
                            del self.voice_note_map[voice]
                        if note in self.note_voice_map:
                            del self.note_voice_map[note]
                        if note in self.note_timestamps:
                            del self.note_timestamps[note]
                        if voice in self.active_voices:
                            self.active_voices.remove(voice)
    
    def _analyze_patterns(self):
        """Analyzes patterns in note events to detect potential issues"""
        while self.running:
            time.sleep(10)  # Run analysis every 10 seconds
            
            # Check for notes with significantly more on events than off events
            for note, on_count in self.note_on_counts.items():
                off_count = self.note_off_counts.get(note, 0)
                if on_count > off_count + 3:  # More than 3 missing note-offs
                    logger.warning(f"Pattern detected: Note {note} has {on_count} on events but only {off_count} off events")
                    self.stats["problem_pattern_detected"] += 1
                    self.problematic_notes.add(note)
                    
                    # If this note is currently active, consider it suspicious
                    if note in self.note_voice_map:
                        voice = self.note_voice_map[note]
                        timestamp = self.note_timestamps.get(note, time.time())
                        duration = time.time() - timestamp
                        
                        # If it's been active for a while, clear it proactively
                        if duration > 5.0:  # 5 seconds is a reasonable threshold here
                            logger.warning(f"Preemptively clearing suspicious note {note} on voice {voice} after {duration:.1f}s")
                            self._send_note_off(voice, note)
                            self._record_state_transition(f"pattern_triggered_clear note={note} voice={voice}")
                    
            # Check for voices that appear in problems frequently
            voice_problem_count = defaultdict(int)
            for voice in self.problematic_voices:
                voice_problem_count[voice] += 1
                
            # Check for notes that appear in problems frequently
            note_problem_count = defaultdict(int)
            for note in self.problematic_notes:
                note_problem_count[note] += 1
            
            # Log the top problematic voices and notes
            if voice_problem_count:
                top_problematic_voices = sorted(voice_problem_count.items(), key=lambda x: x[1], reverse=True)[:3]
                logger.info(f"Top problematic voices: {top_problematic_voices}")
                
            if note_problem_count:
                top_problematic_notes = sorted(note_problem_count.items(), key=lambda x: x[1], reverse=True)[:3]
                logger.info(f"Top problematic notes: {top_problematic_notes}")
                
    def _check_state_consistency(self):
        """Check internal state for consistency"""
        logger.debug("Checking internal state consistency...")
        
        # Check that voice_note_map and note_voice_map are consistent
        for voice, note in list(self.voice_note_map.items()):
            if note not in self.note_voice_map or self.note_voice_map[note] != voice:
                logger.warning(f"Inconsistency detected: voice {voice} plays note {note} but note_voice_map doesn't match")
                self.stats["inconsistencies_detected"] += 1
                
                # Correct it
                self.note_voice_map[note] = voice
                
        for note, voice in list(self.note_voice_map.items()):
            if voice not in self.voice_note_map or self.voice_note_map[voice] != note:
                logger.warning(f"Inconsistency detected: note {note} assigned to voice {voice} but voice_note_map doesn't match")
                self.stats["inconsistencies_detected"] += 1
                
                # If serious inconsistencies are detected, perform an emergency reset
                if self.stats["inconsistencies_detected"] % 10 == 0:
                    logger.error("Too many inconsistencies detected, performing emergency reset")
                    self.stats["emergency_resets"] += 1
                    self._emergency_reset()
                    return
                
                # Correct it
                self.voice_note_map[voice] = note
        
        # Check that all timestamps have corresponding entries in note_voice_map
        for note in list(self.note_timestamps.keys()):
            if note not in self.note_voice_map:
                logger.warning(f"Inconsistency detected: note {note} has timestamp but no voice assignment")
                self.stats["inconsistencies_detected"] += 1
                del self.note_timestamps[note]
    
    def _emergency_reset(self):
        """Perform an emergency reset of all state and send allNotesOff to all voices"""
        logger.warning("EMERGENCY RESET: Clearing all state and sending allNotesOff to all voices")
        
        # Capture state before reset for debugging purposes
        pre_reset_state = {
            "timestamp": time.time(),
            "voice_note_map": dict(self.voice_note_map),
            "note_voice_map": dict(self.note_voice_map),
            "active_voices": list(self.active_voices),
            "note_timestamps": dict(self.note_timestamps),
            "problematic_notes": list(self.problematic_notes),
            "problematic_voices": list(self.problematic_voices),
            "note_on_counts": dict(self.note_on_counts),
            "note_off_counts": dict(self.note_off_counts),
            "stats": dict(self.stats),
            "state_transitions": self.state_transitions[-10:] if self.state_transitions else []
        }
        
        # Record the emergency reset event
        self._record_state_transition("emergency_reset_triggered")
        
        # Send allNotesOff to all tracked voices
        for voice_id in range(16):  # Assuming 16 voices
            self.synth_client.send_message(f"/voice/{voice_id}/noteOff", [1])
            self.synth_client.send_message(f"/voice/{voice_id}/allNotesOff", [1])
        
        # Clear all tracking maps
        self.voice_note_map.clear()
        self.note_voice_map.clear()
        self.note_timestamps.clear()
        self.active_voices.clear()
        
        # Also send a global panic message
        self.synth_client.send_message("/panic", [1])
        
        # Save the pre-reset state for offline analysis
        reset_filename = f"emergency_reset_state_{int(time.time())}.json"
        with open(reset_filename, 'w') as f:
            json.dump(pre_reset_state, f, indent=2)
        
        logger.info(f"Pre-reset state dumped to {reset_filename}")
    
    def query_all_voice_states(self):
        """Query the state of all voices to verify our tracking is accurate"""
        logger.info("Querying state of all voices...")
        active_voices = len(self.active_voices)
        active_notes = len(self.note_voice_map)
        logger.info(f"Internal state: {active_notes} active notes on {active_voices} voices")
        
        # Log information about each active voice
        if self.active_voices:
            logger.info("Active voice details:")
            current_time = time.time()
            for voice in sorted(self.active_voices):
                if voice in self.voice_note_map:
                    note = self.voice_note_map[voice]
                    if note in self.note_timestamps:
                        duration = current_time - self.note_timestamps[note]
                        is_problematic = voice in self.problematic_voices or note in self.problematic_notes
                        status = "PROBLEMATIC" if is_problematic else "OK"
                        logger.info(f"  Voice {voice}: Note {note} for {duration:.1f}s - {status}")
                else:
                    logger.warning(f"  Voice {voice} marked active but has no note assigned")
                    # Fix this inconsistency
                    self.active_voices.remove(voice)
                    self._record_state_transition(f"fixed_active_voice_inconsistency voice={voice}")
        
        # Check for inconsistencies in note duration tracking
        for note, timestamp in list(self.note_timestamps.items()):
            if note not in self.note_voice_map:
                logger.warning(f"Note {note} has timestamp but no voice assignment")
                del self.note_timestamps[note]
                self._record_state_transition(f"fixed_timestamp_inconsistency note={note}")
        
        # This is a placeholder - in a real implementation, you'd query the synth
        # for information about which voices are playing which notes and compare
        # with internal state to detect and fix inconsistencies
        
    def _log_statistics(self):
        """Log statistics about note tracking and issue detection"""
        logger.info("=== Voice Debugger Statistics ===")
        for key, value in self.stats.items():
            logger.info(f"{key}: {value}")
        
        # Calculate note-on vs note-off consistency
        if self.stats["note_on_events"] > 0:
            on_off_ratio = self.stats["note_off_events"] / self.stats["note_on_events"] * 100
            logger.info(f"Note-off to Note-on ratio: {on_off_ratio:.1f}%")
            if on_off_ratio < 95:
                logger.warning(f"Only {on_off_ratio:.1f}% of notes have matching off events")
        
        # List all currently active notes
        if self.note_voice_map:
            logger.info("Currently active notes:")
            current_time = time.time()
            for note, voice in self.note_voice_map.items():
                duration = current_time - self.note_timestamps.get(note, current_time)
                is_problematic = note in self.problematic_notes or voice in self.problematic_voices
                status = "PROBLEMATIC" if is_problematic else "OK"
                logger.info(f"  Note {note} on voice {voice} for {duration:.1f}s - {status}")
        
        # Log top problematic entities
        if self.problematic_notes:
            top_notes = sorted(self.problematic_notes)[:5]
            logger.info(f"Top problematic notes: {top_notes}")
        
        if self.problematic_voices:
            top_voices = sorted(self.problematic_voices)[:5]
            logger.info(f"Top problematic voices: {top_voices}")
    
    def get_debug_info(self):
        """Return a dictionary with debug information"""
        return {
            "active_voices": list(self.active_voices),
            "active_notes": len(self.note_voice_map),
            "voice_note_map": self.voice_note_map,
            "note_voice_map": self.note_voice_map,
            "problematic_notes": list(self.problematic_notes),
            "problematic_voices": list(self.problematic_voices),
            "stats": self.stats,
            "recent_events": list(self.note_history)[-10:],  # Last 10 events
            "state_transitions": self.state_transitions[-10:] if self.state_transitions else []
        }
        
    def dump_state(self, filename="osc_debugger_state.json"):
        """Dump the current state to a JSON file for offline analysis"""
        current_time = time.time()
        
        # Prepare full state information
        state = {
            "timestamp": current_time,
            "voice_note_map": self.voice_note_map,
            "note_voice_map": self.note_voice_map,
            "active_voices": list(self.active_voices),
            "note_timestamps": self.note_timestamps,
            "stats": self.stats,
            "note_history": list(self.note_history),
            "voice_history": {v: list(h) for v, h in self.voice_history.items()},
            "note_durations": self.note_durations,
            "problematic_notes": list(self.problematic_notes),
            "problematic_voices": list(self.problematic_voices),
            "state_transitions": self.state_transitions,
            "note_on_counts": dict(self.note_on_counts),
            "note_off_counts": dict(self.note_off_counts),
            "voice_usage_count": dict(self.voice_usage_count),
            "running_duration": {
                note: current_time - timestamp 
                for note, timestamp in self.note_timestamps.items()
            }
        }
        
        # Calculate additional metrics for analysis
        state["metrics"] = {
            "avg_note_duration": self._calculate_avg_note_duration(),
            "stuck_note_ratio": (self.stats["stuck_notes_detected"] / max(1, self.stats["notes_processed"])) * 100,
            "reassignment_ratio": (self.stats["note_reassignments"] / max(1, self.stats["notes_processed"])) * 100,
            "inconsistency_ratio": (self.stats["inconsistencies_detected"] / max(1, self.stats["notes_processed"])) * 100,
            "most_used_voices": sorted(self.voice_usage_count.items(), key=lambda x: x[1], reverse=True)[:5],
            "error_summary": {
                "stuck_notes": self.stats["stuck_notes_detected"],
                "reassignments": self.stats["note_reassignments"],
                "inconsistencies": self.stats["inconsistencies_detected"],
                "emergency_resets": self.stats["emergency_resets"],
                "missed_note_offs": self.stats["missed_note_off_events"],
                "pattern_detections": self.stats["problem_pattern_detected"]
            }
        }
        
        # Identify potential issue patterns
        potential_issues = []
        
        # Check for notes with unbalanced on/off counts
        for note, on_count in self.note_on_counts.items():
            off_count = self.note_off_counts.get(note, 0)
            if on_count > off_count + 2:  # More than 2 missing note-offs
                potential_issues.append(f"Note {note} has {on_count} on events but only {off_count} off events")
        
        # Check for voices that appear in many problems
        for voice, count in sorted(self.voice_usage_count.items(), key=lambda x: x[1], reverse=True)[:3]:
            if voice in self.problematic_voices:
                potential_issues.append(f"Voice {voice} used {count} times and appears in problematic voices")
        
        state["potential_issues"] = potential_issues
        
        with open(filename, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"State dumped to {filename}")
        
    def _calculate_avg_note_duration(self):
        """Calculate the average duration of notes that have been released"""
        durations = []
        for note_durations in self.note_durations.values():
            durations.extend(note_durations)
        
        if durations:
            return sum(durations) / len(durations)
        return 0
        
    def shutdown(self):
        """Clean shutdown of the voice debugger"""
        logger.info("Shutting down voice debugger")
        self.running = False
        
        # Dump state for offline analysis
        self.dump_state("shutdown_state.json")
        
        # Send all notes off to every active voice
        logger.info(f"Sending all-notes-off to {len(self.active_voices)} active voices")
        for voice_id in self.active_voices:
            self.synth_client.send_message(f"/voice/{voice_id}/allNotesOff", [1])
            
        # Clear tracking maps
        self.voice_note_map.clear()
        self.note_voice_map.clear()
        self.note_timestamps.clear()
        self.active_voices.clear()

class OSCRouterPatch:
    """
    OSC Router Patch
    
    Intercepts OSC messages between midi_osc.py and the synthesizer,
    adding enhanced note tracking and stuck note detection.
    """
    
    def __init__(self, listen_port=9000, synth_port=9200, original_port=9001):
        """
        Initialize the OSC router
        
        Args:
            listen_port: Port to listen for messages from midi_osc.py
            synth_port: Port to forward messages to (the synthesizer)
            original_port: Original port that midi_osc.py was sending to
        """
        self.listen_port = listen_port
        self.synth_port = synth_port
        self.original_port = original_port
        
        # Create a client to forward messages to the synth
        self.synth_client = SimpleUDPClient("127.0.0.1", synth_port)
        
        # Create a dispatcher for handling incoming OSC messages
        self.dispatcher = dispatcher.Dispatcher()
        
        # Set the default handler for all messages
        self.dispatcher.set_default_handler(self._default_handler)
        
        # Add specific handlers for note-on, note-off, and panic messages
        for i in range(16):  # Assuming 16 voices
            self.dispatcher.map(f"/voice/{i}/noteOn", self._handle_note_on)
            self.dispatcher.map(f"/voice/{i}/noteOff", self._handle_note_off)
            self.dispatcher.map(f"/voice/{i}/panic", self._handle_panic)
            self.dispatcher.map(f"/voice/{i}/allNotesOff", self._handle_panic)
        
        # Global panic handler
        self.dispatcher.map("/panic", self._handle_global_panic)
        
        # Initialize the voice debugger
        self.voice_debugger = VoiceDebugger(synth_port=synth_port)
        
        # Create a server to listen for incoming messages
        self.server = osc_server.ThreadingOSCUDPServer(
            ("127.0.0.1", listen_port), self.dispatcher)
        
        self.server_thread = None
        self.running = False
        
        # Track error counts to determine if we need a full reset
        self.consecutive_errors = 0
        self.error_threshold = 10
        self.last_health_report_time = 0
        self.health_report_interval = 300  # 5 minutes
        
        # Enhanced debug mode
        self.debug_mode = True
        self.message_counter = 0
        self.message_history = {}  # Track recent messages by address
        
    def _default_handler(self, address, *args):
        """Default handler for all OSC messages"""
        try:
            # Forward the message to the synthesizer
            self.synth_client.send_message(address, args)
            
            if self.debug_mode:
                self.message_counter += 1
                # Keep track of message types for debugging
                if address not in self.message_history:
                    self.message_history[address] = 0
                self.message_history[address] += 1
                
                # Periodically log message statistics
                if self.message_counter % 1000 == 0:
                    logger.debug(f"Processed {self.message_counter} messages so far")
                    top_messages = sorted(self.message_history.items(), key=lambda x: x[1], reverse=True)[:10]
                    logger.debug(f"Top message types: {top_messages}")
            
            # Reset error counter on successful message handling
            self.consecutive_errors = 0
            
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error in default handler: {e}")
            
            # If we hit the error threshold, perform a health check
            if self.consecutive_errors >= self.error_threshold:
                logger.warning(f"Error threshold reached ({self.consecutive_errors} consecutive errors)")
                self._perform_health_check()
                
    def _handle_note_on(self, address, *args):
        """Handler for note-on messages"""
        try:
            # Extract voice ID from the address
            voice_id = int(address.split('/')[2])
            
            # args should be [note_number, velocity]
            if len(args) >= 2:
                note_number = int(args[0])
                velocity = int(args[1])
                
                # Use our voice debugger to track this note
                self.voice_debugger.handle_note_on(voice_id, note_number, velocity)
                
                # Forward the message to the synthesizer
                self.synth_client.send_message(address, args)
            else:
                logger.warning(f"Invalid note-on message: {address} {args}")
                
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error in note-on handler: {e}")
            
    def _handle_note_off(self, address, *args):
        """Handler for note-off messages"""
        try:
            # Extract voice ID from the address
            voice_id = int(address.split('/')[2])
            
            # args should be [note_number, velocity]
            if len(args) >= 1:
                note_number = int(args[0])
                
                # Use our voice debugger to track this note-off
                self.voice_debugger.handle_note_off(voice_id, note_number)
                
                # Forward the message to the synthesizer
                self.synth_client.send_message(address, args)
            else:
                logger.warning(f"Invalid note-off message: {address} {args}")
                
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error in note-off handler: {e}")
            
    def _handle_panic(self, address, *args):
        """Handler for panic or all-notes-off messages for a single voice"""
        try:
            # Extract voice ID from the address
            voice_id = int(address.split('/')[2])
            
            logger.info(f"Received panic/all-notes-off for voice {voice_id}: {address} {args}")
            
            # Clear any tracked notes for this voice
            if voice_id in self.voice_debugger.voice_note_map:
                note = self.voice_debugger.voice_note_map[voice_id]
                if note in self.voice_debugger.note_voice_map:
                    del self.voice_debugger.note_voice_map[note]
                if note in self.voice_debugger.note_timestamps:
                    del self.voice_debugger.note_timestamps[note]
                del self.voice_debugger.voice_note_map[voice_id]
            
            if voice_id in self.voice_debugger.active_voices:
                self.voice_debugger.active_voices.remove(voice_id)
            
            # Forward the message to the synthesizer
            self.synth_client.send_message(address, args)
            
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error in panic handler: {e}")
            
    def _handle_global_panic(self, address, *args):
        """Handler for global panic messages"""
        try:
            logger.info(f"Received global panic: {address} {args}")
            
            # Clear all voice/note mappings
            self.voice_debugger.voice_note_map.clear()
            self.voice_debugger.note_voice_map.clear()
            self.voice_debugger.note_timestamps.clear()
            self.voice_debugger.active_voices.clear()
            
            # Forward the message to the synthesizer
            self.synth_client.send_message(address, args)
            
            # Reset error counter
            self.consecutive_errors = 0
            
        except Exception as e:
            self.consecutive_errors += 1
            logger.error(f"Error in global panic handler: {e}")
    
    def _perform_health_check(self):
        """Perform a health check on the system"""
        logger.warning("Performing system health check...")
        
        try:
            # Check if we have any voices that are in an inconsistent state
            inconsistencies = 0
            
            # Check for notes with timestamps but no voice assignment
            for note in list(self.voice_debugger.note_timestamps.keys()):
                if note not in self.voice_debugger.note_voice_map:
                    logger.warning(f"Inconsistency: Note {note} has timestamp but no voice assignment")
                    del self.voice_debugger.note_timestamps[note]
                    inconsistencies += 1
            
            # Check for voice-note mapping inconsistencies
            for voice, note in list(self.voice_debugger.voice_note_map.items()):
                if note not in self.voice_debugger.note_voice_map or self.voice_debugger.note_voice_map[note] != voice:
                    logger.warning(f"Inconsistency: Voice {voice} -> Note {note}, but Note -> Voice mapping is incorrect")
                    inconsistencies += 1
            
            # Check for stuck notes based on duration
            current_time = time.time()
            for note, timestamp in list(self.voice_debugger.note_timestamps.items()):
                duration = current_time - timestamp
                if duration > 60:  # Over a minute is definitely suspicious
                    voice = self.voice_debugger.note_voice_map.get(note)
                    if voice is not None:
                        logger.warning(f"Health check found potentially stuck note: note {note} on voice {voice} for {duration:.1f}s")
                        inconsistencies += 1
                        
                        # Clear this note preemptively
                        self._send_recovery_action(f"clear_note {voice} {note}")
            
            # If we have serious inconsistencies, perform a full reset
            if inconsistencies > 5:
                logger.error(f"Health check found {inconsistencies} inconsistencies, performing emergency reset")
                self._emergency_reset()
            elif inconsistencies > 0:
                logger.info(f"Health check complete: {inconsistencies} minor inconsistencies found and fixed")
                # Send a partial reset signal targeting only the problematic voices
                self._send_targeted_reset()
            else:
                logger.info("Health check complete: System consistent")
                
            # Reset error counter after health check
            self.consecutive_errors = 0
            
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            # If health check itself fails, do an emergency reset
            self._emergency_reset()
    
    def _send_targeted_reset(self):
        """Send a targeted reset to only problematic voices"""
        logger.info("Performing targeted reset of problematic voices...")
        
        # Get problematic voices from the voice debugger
        problematic_voices = self.voice_debugger.problematic_voices
        if not problematic_voices:
            logger.info("No specifically problematic voices to reset")
            return
            
        # Send note-off to each problematic voice
        for voice in problematic_voices:
            logger.info(f"Sending targeted reset to voice {voice}")
            self.synth_client.send_message(f"/voice/{voice}/allNotesOff", [1])
            
            # If this voice has a note currently assigned, clear it from tracking
            if voice in self.voice_debugger.voice_note_map:
                note = self.voice_debugger.voice_note_map[voice]
                
                # Clean up tracking maps
                del self.voice_debugger.voice_note_map[voice]
                if note in self.voice_debugger.note_voice_map:
                    del self.voice_debugger.note_voice_map[note]
                if note in self.voice_debugger.note_timestamps:
                    del self.voice_debugger.note_timestamps[note]
                if voice in self.voice_debugger.active_voices:
                    self.voice_debugger.active_voices.remove(voice)
                    
        # Record the targeted reset in transitions
        self.voice_debugger._record_state_transition(f"targeted_reset voices={list(problematic_voices)}")
    
    def _send_recovery_action(self, action):
        """Send a recovery action to fix a specific issue"""
        logger.info(f"Recovery action: {action}")
        
        parts = action.split()
        action_type = parts[0]
        
        if action_type == "clear_note":
            # Format: clear_note voice_id note_number
            if len(parts) >= 3:
                voice = int(parts[1])
                note = int(parts[2])
                
                # Send note-off to the voice
                self.synth_client.send_message(f"/voice/{voice}/noteOff", [note, 0])
                
                # Also clear it from our tracking
                if voice in self.voice_debugger.voice_note_map:
                    current_note = self.voice_debugger.voice_note_map[voice]
                    if current_note == note:
                        del self.voice_debugger.voice_note_map[voice]
                
                if note in self.voice_debugger.note_voice_map:
                    del self.voice_debugger.note_voice_map[note]
                
                if note in self.voice_debugger.note_timestamps:
                    del self.voice_debugger.note_timestamps[note]
                    
                # Record the recovery action
                self.voice_debugger._record_state_transition(f"recovery_action clear_note voice={voice} note={note}")
                
        elif action_type == "reset_voice":
            # Format: reset_voice voice_id
            if len(parts) >= 2:
                voice = int(parts[1])
                
                # Send allNotesOff to the voice
                self.synth_client.send_message(f"/voice/{voice}/allNotesOff", [1])
                
                # Clear tracking for this voice
                if voice in self.voice_debugger.voice_note_map:
                    note = self.voice_debugger.voice_note_map[voice]
                    del self.voice_debugger.voice_note_map[voice]
                    
                    if note in self.voice_debugger.note_voice_map:
                        del self.voice_debugger.note_voice_map[note]
                    
                    if note in self.voice_debugger.note_timestamps:
                        del self.voice_debugger.note_timestamps[note]
                
                if voice in self.voice_debugger.active_voices:
                    self.voice_debugger.active_voices.remove(voice)
                    
                # Record the recovery action
                self.voice_debugger._record_state_transition(f"recovery_action reset_voice voice={voice}")
                
        elif action_type == "panic":
            # Global panic - full reset
            self._emergency_reset()

    def health_report(self):
        """Generate a health report"""
        current_time = time.time()
        
        # Only generate a report every N seconds
        if current_time - self.last_health_report_time < self.health_report_interval:
            return
            
        self.last_health_report_time = current_time
        
        logger.info("=== OSC Router Health Report ===")
        logger.info(f"Server running: {self.running}")
        logger.info(f"Messages processed: {self.message_counter}")
        logger.info(f"Active voices: {len(self.voice_debugger.active_voices)}")
        logger.info(f"Active notes: {len(self.voice_debugger.note_voice_map)}")
        
        # Check for long-running notes
        if self.voice_debugger.note_timestamps:
            long_notes = []
            for note, timestamp in self.voice_debugger.note_timestamps.items():
                duration = current_time - timestamp
                if duration > 30:  # Note on for more than 30 seconds
                    voice = self.voice_debugger.note_voice_map.get(note, "unknown")
                    long_notes.append((note, voice, duration))
                    
            if long_notes:
                logger.info(f"Long-running notes ({len(long_notes)}):")
                for note, voice, duration in sorted(long_notes, key=lambda x: x[2], reverse=True)[:5]:
                    logger.info(f"  Note {note} on voice {voice} for {duration:.1f}s")
                    
                    # For extremely long notes, consider them stuck and clear them
                    if duration > 120:  # 2 minutes is extremely long for a note
                        if voice != "unknown":
                            logger.warning(f"Health report clearing suspected stuck note {note} on voice {voice} after {duration:.1f}s")
                            self._send_recovery_action(f"clear_note {voice} {note}")
        
        # Check if we have a significant imbalance between note-on and note-off events
        note_on = self.voice_debugger.stats.get("note_on_events", 0)
        note_off = self.voice_debugger.stats.get("note_off_events", 0)
        if note_on > 0 and note_off / note_on < 0.9:  # Less than 90% of notes have matching offs
            logger.warning(f"Health report detected note on/off imbalance: {note_on} ons, {note_off} offs ({note_off/note_on*100:.1f}%)")
            
            # If the imbalance is severe, consider a targeted reset
            if len(self.voice_debugger.note_voice_map) > 10 or note_off / note_on < 0.7:
                logger.warning("Severe note on/off imbalance detected, performing targeted reset")
                self._send_targeted_reset()
        
        # Dump stats from voice debugger
        for key, value in self.voice_debugger.stats.items():
            logger.info(f"{key}: {value}")
        
        # Generate debug file if we have activity
        if self.voice_debugger.note_history:
            self.voice_debugger.dump_state(f"health_report_{int(current_time)}.json")
        
    def run(self):
        """Run the OSC router server"""
        logger.info(f"Starting OSC router server on port {self.listen_port}")
        logger.info(f"Forwarding messages to synth on port {self.synth_port}")
        
        self.running = True
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        try:
            while self.running:
                # Generate periodic health reports
                self.health_report()
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()
            
    def shutdown(self):
        """Shutdown the OSC router server"""
        logger.info("Shutting down OSC router server")
        self.running = False
        
        if self.server:
            self.server.shutdown()
            
        if self.voice_debugger:
            self.voice_debugger.shutdown()
            
        logger.info("OSC router server shutdown complete")

def main():
    """Main entry point for the OSC router debug patch"""
    parser = argparse.ArgumentParser(description="OSC Router Debug Patch")
    parser.add_argument("--listen-port", type=int, default=9000,
                        help="Port to listen on for incoming OSC messages")
    parser.add_argument("--synth-port", type=int, default=9200,
                        help="Port where the synth is listening")
    
    args = parser.parse_args()
    
    logger.info("=== OSC Router Debug Patch ===")
    logger.info(f"Listen port: {args.listen_port}")
    logger.info(f"Synth port: {args.synth_port}")
    
    router = OSCRouterPatch(
        listen_port=args.listen_port,
        synth_port=args.synth_port
    )
    
    router.run()

if __name__ == "__main__":
    main() 