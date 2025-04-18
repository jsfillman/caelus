#!/usr/bin/env python3
"""
Murnau - Cinematic Synthesizer Control Interface
A stylish PyQt6 UI for controlling legato_synth via OSC
Inspired by German Expressionist cinema aesthetics
"""
import sys
import socket
import struct
import threading
import time
import os
import mido
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QSlider, 
                           QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                           QGridLayout, QFrame, QDial, QComboBox, QGroupBox,
                           QSplashScreen, QCheckBox, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor, QLinearGradient, QPainter, QBrush, QPen, QPixmap, QIcon, QFontDatabase

# OSC Communication
def send_osc(ip, port, address, value):
    """Send OSC message"""
    address_bytes = address.encode('utf-8')
    address_padded = address_bytes + (b'\0' * (4 - len(address_bytes) % 4))
    
    type_tag = b',f'
    type_tag_padded = type_tag + (b'\0' * (4 - len(type_tag) % 4))
    
    value_bytes = struct.pack('>f', float(value))
    
    message = address_padded + type_tag_padded + value_bytes
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message, (ip, port))
    sock.close()

# Custom styled knob with value label
class LabeledKnob(QWidget):
    valueChanged = pyqtSignal(float)
    
    def __init__(self, name, min_val, max_val, default, is_log=False, parent=None, midi_cc=None, is_integer=False):
        super().__init__(parent)
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.is_log = is_log
        self.midi_cc = midi_cc
        self.is_integer = is_integer
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        # Create label with name
        self.name_label = QLabel(name)
        self.name_label.setFont(QFont("Futura", 11))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: #E6E6E6;")
        
        # Add MIDI CC label if assigned
        if midi_cc is not None:
            self.name_label.setText(f"{name} (CC{midi_cc})")
        
        # Create knob
        self.knob = QDial()
        self.knob.setMinimum(0)
        self.knob.setMaximum(1000)
        self.knob.setNotchesVisible(True)
        self.knob.setWrapping(False)
        self.knob.setFixedSize(80, 80)
        self.knob.setStyleSheet("""
            QDial {
                background-color: #2A2A2A;
                border: 1px solid #3A3A3A;
                border-radius: 40px;
            }
            QDial::groove {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1,
                                          stop:0 #8A7A55, stop:1 #5D5236);
                border-radius: 40px;
            }
            QDial::handle {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                          stop:0 #E5D5A0, stop:1 #C0AA70);
                border: 1px solid #555555;
                width: 16px;
                height: 16px;
                border-radius: 8px;
            }
        """)
        
        # Set default position based on input value
        default_pos = self.value_to_knob(default)
        self.knob.setValue(default_pos)
        
        # Create value label with decorative frame
        value_frame = QFrame()
        value_frame.setFrameShape(QFrame.Shape.Panel)
        value_frame.setFrameShadow(QFrame.Shadow.Sunken)
        value_frame.setStyleSheet("""
            background-color: #1A1A1A;
            border: 1px solid #3A3A3A;
            border-radius: 3px;
        """)
        value_layout = QVBoxLayout(value_frame)
        value_layout.setContentsMargins(2, 2, 2, 2)
        
        self.value_label = QLabel(f"{default:.2f}")
        self.value_label.setFont(QFont("Futura", 10))
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("color: #D4BF8A;")
        
        value_layout.addWidget(self.value_label)
        
        # Connect signal
        self.knob.valueChanged.connect(self.handle_knob_change)
        
        # Add widgets to layout
        layout.addWidget(self.name_label)
        layout.addWidget(self.knob)
        layout.addWidget(value_frame)
        
        # Set layout properties
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        # Animation effect for value changes
        self._animation_timer = QTimer()
        self._animation_timer.setSingleShot(True)
        self._animation_timer.timeout.connect(self._reset_label_style)
        
    def _animate_value_change(self):
        """Visual feedback when value changes"""
        self.value_label.setStyleSheet("color: #FFFFFF; font-weight: bold;")
        self._animation_timer.start(300)
        
    def _reset_label_style(self):
        """Reset label style after animation"""
        self.value_label.setStyleSheet("color: #D4BF8A;")
        
    def value_to_knob(self, value):
        """Convert actual value to knob position"""
        if self.is_log:
            # Logarithmic scaling for values like frequency
            normalized = (value - self.min_val) / (self.max_val - self.min_val)
            return int(normalized * 1000)
        else:
            # Linear scaling
            normalized = (value - self.min_val) / (self.max_val - self.min_val)
            return int(normalized * 1000)
    
    def knob_to_value(self, position):
        """Convert knob position to actual value"""
        if self.is_log:
            # Logarithmic scaling
            normalized = position / 1000
            return self.min_val + normalized * (self.max_val - self.min_val)
        else:
            # Linear scaling
            normalized = position / 1000
            return self.min_val + normalized * (self.max_val - self.min_val)
    
    def handle_knob_change(self, position):
        """Handle knob value change"""
        value = self.knob_to_value(position)
        if self.is_integer:
            self.value_label.setText(f"{int(value)}")
        else:
            self.value_label.setText(f"{value:.2f}")
        self._animate_value_change()
        self.valueChanged.emit(value)
    
    def set_value(self, value):
        """Set knob from outside"""
        position = self.value_to_knob(value)
        self.knob.setValue(position)
    
    def set_from_midi_cc(self, cc_value):
        """Set from MIDI CC value (0-127)"""
        if self.midi_cc is not None:
            # Convert from 0-127 range to knob range
            normalized = cc_value / 127.0
            value = self.min_val + normalized * (self.max_val - self.min_val)
            self.set_value(value)
            return value
        return None

# Waveform selector with visual icons
class WaveformSelector(QWidget):
    waveformChanged = pyqtSignal(int)
    
    def __init__(self, parent=None, midi_cc=1):
        super().__init__(parent)
        self.midi_cc = midi_cc
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create label
        self.name_label = QLabel(f"Waveform (CC{midi_cc})")
        self.name_label.setFont(QFont("Futura", 11))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: #E6E6E6;")
        
        # Waveform buttons layout
        wave_buttons_layout = QHBoxLayout()
        
        # Waveform buttons
        self.wave_buttons = []
        waveforms = [("Sine", "○"), ("Triangle", "△"), ("Sawtooth", "◸"), ("Square", "□")]
        
        for i, (name, symbol) in enumerate(waveforms):
            button = QPushButton(symbol)
            button.setToolTip(name)
            button.setMinimumSize(40, 40)
            button.setMaximumSize(40, 40)
            button.setCheckable(True)
            button.setProperty("wave_index", i)
            button.setFont(QFont("Arial", 16))
            
            # Set sawtooth as default
            if i == 2:  # Sawtooth
                button.setChecked(True)
            
            button.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2A;
                    color: #D4BF8A;
                    border: 1px solid #555555;
                    border-radius: 5px;
                }
                QPushButton:checked {
                    background-color: #5D5236;
                    color: #FFFFFF;
                    border: 1px solid #D4BF8A;
                }
                QPushButton:hover {
                    background-color: #3A3A3A;
                }
            """)
            
            button.clicked.connect(self.button_clicked)
            
            self.wave_buttons.append(button)
            wave_buttons_layout.addWidget(button)
        
        # Create waveform visualization
        self.wave_viz = QFrame()
        self.wave_viz.setMinimumHeight(100)
        self.wave_viz.setFrameShape(QFrame.Shape.Box)
        self.wave_viz.setFrameShadow(QFrame.Shadow.Sunken)
        self.wave_viz.setStyleSheet("""
            background-color: #0F0F0F;
            border: 1px solid #3A3A3A;
            border-radius: 4px;
        """)
        
        # Add widgets to layout
        layout.addWidget(self.name_label)
        layout.addLayout(wave_buttons_layout)
        layout.addWidget(self.wave_viz)
        
        # Current waveform index
        self.current_index = 2  # Default to sawtooth
        
        # Set layout properties
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        # Animation for waveform changes
        self._animation_timer = QTimer()
        self._animation_timer.setSingleShot(True)
        self._animation_timer.timeout.connect(self._reset_wave_viz_style)
    
    def button_clicked(self):
        """Handle button click"""
        button = self.sender()
        wave_index = button.property("wave_index")
        
        # Uncheck all buttons
        for btn in self.wave_buttons:
            if btn != button:
                btn.setChecked(False)
        
        # Update current index and emit signal
        self.current_index = wave_index
        self.wave_viz.setWaveType(wave_index)
        self.waveformChanged.emit(wave_index)
        
        # Update visualization
        self._animate_wave_change()
    
    def _animate_wave_change(self):
        """Animate waveform change"""
        # Add a flash effect to the wave visualization frame
        self.wave_viz.setStyleSheet("""
            background-color: #252525;
            border: 1px solid #D4BF8A;
            border-radius: 4px;
        """)
        self._animation_timer.start(300)
    
    def _reset_wave_viz_style(self):
        """Reset wave viz style after animation"""
        self.wave_viz.setStyleSheet("""
            background-color: #0F0F0F;
            border: 1px solid #3A3A3A;
            border-radius: 4px;
        """)
    
    def set_from_midi_cc(self, cc_value):
        """Set waveform from MIDI CC value (0-127)"""
        if self.midi_cc is not None:
            # Map 0-127 to 0-3 range for waveforms
            wave = min(3, int(cc_value / 32))
            self.set_waveform(wave)
            return wave
        return None
    
    def set_waveform(self, index):
        """Set waveform from outside"""
        if 0 <= index <= 3:
            self.current_index = index
            
            # Update button states
            for i, button in enumerate(self.wave_buttons):
                button.setChecked(i == index)
            
            # Update the wave visualization
            self.wave_viz.setWaveType(index)
            
            # Animation and update
            self._animate_wave_change()
            self.waveformChanged.emit(index)
    
    # Create a subclass of QFrame to handle wave visualization
    class WaveVizFrame(QFrame):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(100)
            self.setFrameShape(QFrame.Shape.Box)
            self.setFrameShadow(QFrame.Shadow.Sunken)
            self.setStyleSheet("""
                background-color: #0F0F0F;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
            """)
            self.wave_type = 2  # Default sawtooth
            self.offset = 0  # For animation
        
        def setWaveType(self, wave_type):
            self.wave_type = wave_type
            self.update()
        
        def animate(self):
            self.offset = (self.offset + 1) % 50  # Cycle through 0-49
            self.update()
        
        def paintEvent(self, event):
            super().paintEvent(event)
            
            qp = QPainter(self)
            qp.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            width = self.width()
            height = self.height()
            middle = height / 2
            
            # Use a gradient pen for more expressionist look
            gradient = QLinearGradient(0, 0, width, height)
            gradient.setColorAt(0, QColor("#D4BF8A"))
            gradient.setColorAt(1, QColor("#8A7A55"))
            
            # Draw grid lines for reference
            qp.setPen(QPen(QColor("#2A2A2A"), 1))
            qp.drawLine(0, int(middle), width, int(middle))  # Horizontal center line
            for x in range(0, width, int(width/8)):  # Vertical grid lines
                qp.drawLine(x, 0, x, height)
            
            # Switch to gradient pen for waveform
            qp.setPen(QPen(QBrush(gradient), 2))
            
            # Points to connect with lines instead of individual points
            points = []
            
            # Animate by shifting start position
            start_x = -self.offset
            
            if self.wave_type == 0:  # Sine
                # Draw sine wave
                for x in range(start_x, width + 10):
                    if x < 0:
                        continue
                    y = middle - middle * 0.7 * math.sin((x + self.offset) / width * 4 * math.pi)
                    points.append((x, int(y)))
            
            elif self.wave_type == 1:  # Triangle
                # Draw triangle wave
                period = width / 2
                for x in range(start_x, width + 10):
                    if x < 0:
                        continue
                    phase = ((x + self.offset) % period) / period
                    if (x + self.offset) % (2 * period) < period:
                        y = middle - middle * 0.7 * (2 * phase - 1)
                    else:
                        y = middle - middle * 0.7 * (1 - 2 * phase)
                    points.append((x, int(y)))
            
            elif self.wave_type == 2:  # Sawtooth
                # Draw sawtooth wave
                period = width / 2
                for x in range(start_x, width + 10):
                    if x < 0:
                        continue
                    phase = ((x + self.offset) % period) / period
                    y = middle - middle * 0.7 * (2 * phase - 1)
                    points.append((x, int(y)))
            
            elif self.wave_type == 3:  # Square
                # Draw square wave
                period = width / 2
                for x in range(start_x, width + 10):
                    if x < 0:
                        continue
                    if (x + self.offset) % period < period / 2:
                        y = middle - middle * 0.7
                    else:
                        y = middle + middle * 0.7
                    points.append((x, int(y)))
            
            # Draw connected lines for smoother look
            if len(points) > 1:
                for i in range(1, len(points)):
                    qp.drawLine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])
    
    def __init__(self, parent=None, midi_cc=1):
        super().__init__(parent)
        self.midi_cc = midi_cc
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create label
        self.name_label = QLabel(f"Waveform (CC{midi_cc})")
        self.name_label.setFont(QFont("Futura", 11))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: #E6E6E6;")
        
        # Waveform buttons layout
        wave_buttons_layout = QHBoxLayout()
        
        # Waveform buttons
        self.wave_buttons = []
        waveforms = [("Sine", "○"), ("Triangle", "△"), ("Sawtooth", "◸"), ("Square", "□")]
        
        for i, (name, symbol) in enumerate(waveforms):
            button = QPushButton(symbol)
            button.setToolTip(name)
            button.setMinimumSize(40, 40)
            button.setMaximumSize(40, 40)
            button.setCheckable(True)
            button.setProperty("wave_index", i)
            button.setFont(QFont("Arial", 16))
            
            # Set sawtooth as default
            if i == 2:  # Sawtooth
                button.setChecked(True)
            
            button.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2A;
                    color: #D4BF8A;
                    border: 1px solid #555555;
                    border-radius: 5px;
                }
                QPushButton:checked {
                    background-color: #5D5236;
                    color: #FFFFFF;
                    border: 1px solid #D4BF8A;
                }
                QPushButton:hover {
                    background-color: #3A3A3A;
                }
            """)
            
            button.clicked.connect(self.button_clicked)
            
            self.wave_buttons.append(button)
            wave_buttons_layout.addWidget(button)
        
        # Create waveform visualization using custom frame
        self.wave_viz = self.WaveVizFrame()
        
        # Add widgets to layout
        layout.addWidget(self.name_label)
        layout.addLayout(wave_buttons_layout)
        layout.addWidget(self.wave_viz)
        
        # Current waveform index
        self.current_index = 2  # Default to sawtooth
        self.wave_viz.setWaveType(self.current_index)
        
        # Set layout properties
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        
        # Animation for waveform changes
        self._animation_timer = QTimer()
        self._animation_timer.setSingleShot(True)
        self._animation_timer.timeout.connect(self._reset_wave_viz_style)
    
    def animate_wave(self):
        """Animate the waveform visualization"""
        self.wave_viz.animate()
        
    def update(self):
        """Update the widget"""
        super().update()
        self.wave_viz.update()

# Piano key widgets for playing notes
class PianoKeys(QWidget):
    noteOn = pyqtSignal(float)
    noteOff = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setMinimumWidth(500)
        
        # Expanded keyboard range
        self.notes = [
            261.63, 277.18, 293.66, 311.13, 329.63, 349.23, 369.99,
            392.00, 415.30, 440.00, 466.16, 493.88, 523.25
        ]
        self.note_names = ["C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4", "C5"]
        self.is_black_key = [False, True, False, True, False, False, True, False, True, False, True, False, False]
        self.active_keys = set()  # Track multiple active keys for polyphonic display
        self.last_midi_note = None
        
        # Key shadows for expressionist effect
        self.key_shadows = []
        for i in range(len(self.notes)):
            self.key_shadows.append(QColor(10, 10, 10, 100))
        
        # Set focus policy to enable key press events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def paintEvent(self, event):
        """Draw piano keys with expressionist perspective distortion"""
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # First draw all white keys
        white_keys = [i for i, is_black in enumerate(self.is_black_key) if not is_black]
        white_key_width = width / len(white_keys)
        
        # Draw white key background
        qp.setBrush(QBrush(QColor("#232323")))
        qp.setPen(Qt.PenStyle.NoPen)
        qp.drawRect(0, 0, width, height)
        
        # Draw each white key
        white_key_index = 0
        for i in range(len(self.notes)):
            if not self.is_black_key[i]:
                # Set color based on active state
                if i in self.active_keys:
                    # Gold gradient for active keys
                    gradient = QLinearGradient(0, 0, 0, height)
                    gradient.setColorAt(0, QColor("#D4BF8A"))
                    gradient.setColorAt(1, QColor("#8A7A55"))
                    qp.setBrush(QBrush(gradient))
                else:
                    # Ivory gradient for inactive keys
                    gradient = QLinearGradient(0, 0, 0, height)
                    gradient.setColorAt(0, QColor("#E6E6E6"))
                    gradient.setColorAt(1, QColor("#BBBBBB"))
                    qp.setBrush(QBrush(gradient))
                
                # Draw key with slight perspective distortion
                x = int(white_key_index * white_key_width)
                y = 0
                w = int(white_key_width - 1)
                
                # Draw shadow first
                shadow_color = QColor(0, 0, 0, 50)
                qp.setPen(Qt.PenStyle.NoPen)
                qp.setBrush(QBrush(shadow_color))
                shadow_offset = 3
                qp.drawRect(x + shadow_offset, y + shadow_offset, w, height)
                
                # Draw key
                qp.setPen(QPen(QColor("#555555"), 1))
                if i in self.active_keys:
                    qp.setBrush(QBrush(gradient))
                else:
                    qp.setBrush(QBrush(gradient))
                qp.drawRect(x, y, w, height)
                
                # Draw note name
                if i in self.active_keys:
                    qp.setPen(QPen(QColor("#FFFFFF"), 1))
                else:
                    qp.setPen(QPen(QColor("#333333"), 1))
                qp.setFont(QFont("Futura", 9, QFont.Weight.Bold))
                qp.drawText(int(x + 5), height - 8, self.note_names[i])
                
                white_key_index += 1
        
        # Then draw all black keys on top
        for i in range(len(self.notes)):
            if self.is_black_key[i]:
                # Find the white keys before and after
                prev_white = -1
                next_white = -1
                
                for j in range(i-1, -1, -1):
                    if not self.is_black_key[j]:
                        prev_white = j
                        break
                
                for j in range(i+1, len(self.notes)):
                    if not self.is_black_key[j]:
                        next_white = j
                        break
                
                if prev_white >= 0 and next_white >= 0:
                    # Calculate position based on surrounding white keys
                    prev_index = white_keys.index(prev_white)
                    next_index = white_keys.index(next_white)
                    
                    x = int((prev_index + 0.7) * white_key_width)
                    y = 0
                    w = int(white_key_width * 0.6)
                    h = int(height * 0.65)
                    
                    # Set color based on active state
                    if i in self.active_keys:
                        gradient = QLinearGradient(0, 0, 0, h)
                        gradient.setColorAt(0, QColor("#8A7A55"))
                        gradient.setColorAt(1, QColor("#5D5236"))
                        qp.setBrush(QBrush(gradient))
                    else:
                        gradient = QLinearGradient(0, 0, 0, h)
                        gradient.setColorAt(0, QColor("#222222"))
                        gradient.setColorAt(1, QColor("#111111"))
                        qp.setBrush(QBrush(gradient))
                    
                    # Draw shadow
                    shadow_color = QColor(0, 0, 0, 70)
                    qp.setPen(Qt.PenStyle.NoPen)
                    qp.setBrush(QBrush(shadow_color))
                    shadow_offset = 2
                    qp.drawRect(x + shadow_offset, y + shadow_offset, w, h)
                    
                    # Draw key
                    qp.setPen(QPen(QColor("#444444"), 1))
                    qp.setBrush(QBrush(gradient))
                    qp.drawRect(x, y, w, h)
    
    def mousePressEvent(self, event):
        """Handle mouse press to play note"""
        self._handle_mouse_position(event.position().x(), event.position().y(), True)
    
    def mouseMoveEvent(self, event):
        """Handle mouse drag over keys"""
        # Only process if mouse button is pressed
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._handle_mouse_position(event.position().x(), event.position().y(), True)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop note"""
        self.active_keys.clear()
        self.noteOff.emit()
        self.update()
    
    def _handle_mouse_position(self, x, y, trigger_note=True):
        """Process mouse position and determine which key is activated"""
        width = self.width()
        height = self.height()
        
        # First check black keys (they're on top)
        white_keys = [i for i, is_black in enumerate(self.is_black_key) if not is_black]
        white_key_width = width / len(white_keys)
        
        # Check black keys first (they're on top)
        for i in range(len(self.notes)):
            if self.is_black_key[i]:
                # Find surrounding white keys
                prev_white = -1
                for j in range(i-1, -1, -1):
                    if not self.is_black_key[j]:
                        prev_white = j
                        break
                
                if prev_white >= 0:
                    prev_index = white_keys.index(prev_white)
                    black_key_x = int((prev_index + 0.7) * white_key_width)
                    black_key_width = int(white_key_width * 0.6)
                    black_key_height = int(height * 0.65)
                    
                    if (x >= black_key_x and x < black_key_x + black_key_width and 
                            y < black_key_height):
                        if i not in self.active_keys and trigger_note:
                            self.active_keys.add(i)
                            self.noteOn.emit(self.notes[i])
                        self.update()
                        return
        
        # If no black key was clicked, check white keys
        white_key_index = 0
        for i in range(len(self.notes)):
            if not self.is_black_key[i]:
                key_x = int(white_key_index * white_key_width)
                if x >= key_x and x < key_x + white_key_width:
                    if i not in self.active_keys and trigger_note:
                        self.active_keys.add(i)
                        self.noteOn.emit(self.notes[i])
                    self.update()
                    return
                white_key_index += 1
    
    def keyPressEvent(self, event):
        """Handle keyboard input for notes"""
        key_mapping = {
            Qt.Key.Key_Z: 0,   # C4
            Qt.Key.Key_S: 1,   # C#4
            Qt.Key.Key_X: 2,   # D4
            Qt.Key.Key_D: 3,   # D#4
            Qt.Key.Key_C: 4,   # E4
            Qt.Key.Key_V: 5,   # F4
            Qt.Key.Key_G: 6,   # F#4
            Qt.Key.Key_B: 7,   # G4
            Qt.Key.Key_H: 8,   # G#4
            Qt.Key.Key_N: 9,   # A4
            Qt.Key.Key_J: 10,  # A#4
            Qt.Key.Key_M: 11,  # B4
            Qt.Key.Key_Comma: 12,  # C5
        }
        
        # Prevent key repeat events
        if event.isAutoRepeat():
            return
            
        if event.key() in key_mapping:
            note_idx = key_mapping[event.key()]
            if note_idx not in self.active_keys:
                self.active_keys.add(note_idx)
                self.noteOn.emit(self.notes[note_idx])
                self.update()
    
    def keyReleaseEvent(self, event):
        """Handle keyboard release for notes"""
        # Prevent key repeat events
        if event.isAutoRepeat():
            return
            
        key_mapping = {
            Qt.Key.Key_Z: 0,   # C4
            Qt.Key.Key_S: 1,   # C#4
            Qt.Key.Key_X: 2,   # D4
            Qt.Key.Key_D: 3,   # D#4
            Qt.Key.Key_C: 4,   # E4
            Qt.Key.Key_V: 5,   # F4
            Qt.Key.Key_G: 6,   # F#4
            Qt.Key.Key_B: 7,   # G4
            Qt.Key.Key_H: 8,   # G#4
            Qt.Key.Key_N: 9,   # A4
            Qt.Key.Key_J: 10,  # A#4
            Qt.Key.Key_M: 11,  # B4
            Qt.Key.Key_Comma: 12,  # C5
        }
        
        if event.key() in key_mapping:
            note_idx = key_mapping[event.key()]
            if note_idx in self.active_keys:
                self.active_keys.remove(note_idx)
                
                # Only emit noteOff if all keys are released
                if not self.active_keys:
                    self.noteOff.emit()
                # Otherwise, play the last pressed note
                else:
                    self.noteOn.emit(self.notes[max(self.active_keys)])
                
                self.update()
    
    def handle_midi_note_on(self, note, velocity):
        """Handle MIDI note on event"""
        # Convert MIDI note number to our note array
        note_idx = note - 60  # MIDI note 60 = C4
        
        if 0 <= note_idx < len(self.notes):
            self.active_keys.add(note_idx)
            self.last_midi_note = note_idx
            self.update()
            return True
        return False
    
    def handle_midi_note_off(self, note):
        """Handle MIDI note off event"""
        note_idx = note - 60  # MIDI note 60 = C4
        
        if note_idx in self.active_keys:
            self.active_keys.remove(note_idx)
            if note_idx == self.last_midi_note:
                self.last_midi_note = None if not self.active_keys else max(self.active_keys)
            self.update()
            return True
        return False

# Main window
class MurnauUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # OSC settings
        self.osc_ip = "127.0.0.1"
        self.osc_port = 5510
        self.synth_name = "legato_synth"
        
        # MIDI settings
        self.midi_input = None
        self.midi_thread = None
        self.midi_running = False
        
        # Active notes for MIDI tracking
        self.active_notes = {}  # note_num -> frequency
        self.current_note = None
        self.LEGATO_THRESHOLD = 0.03  # 30ms threshold for legato transitions
        self.last_gate_off_time = 0
        
        # Initialize UI
        self.init_ui()
        
        # Initialize MIDI
        self.init_midi()
        
        # Initialize parameters
        self.init_parameters()
        
        # Show the window
        self.show()
        
        # Set focus to piano keys
        self.piano.setFocus()
        
        # Start animation effects
        self._animate_ui_elements()
    
    def init_ui(self):
        """Initialize the main UI"""
        # Set window properties
        self.setWindowTitle("Murnau")
        self.setStyleSheet("background-color: #121212; color: #e0d9c6;")
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        
        # Top section with MIDI and controls
        top_section = QHBoxLayout()
        
        # Left column - MIDI controls
        left_column = QVBoxLayout()
        
        # MIDI control section
        midi_group = QGroupBox("MIDI Control")
        midi_layout = QHBoxLayout()
        
        # MIDI port selector
        self.midi_port_combo = QComboBox()
        self.midi_port_combo.setFont(QFont("Futura", 10))
        self.midi_port_combo.setStyleSheet("""
            QComboBox {
                background-color: #2A2A2A;
                color: #E6E6E6;
                border: 1px solid #3A3A3A;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        
        # MIDI enable/disable button
        self.midi_toggle = QPushButton("Enable MIDI")
        self.midi_toggle.setCheckable(True)
        self.midi_toggle.setFont(QFont("Futura", 10))
        self.midi_toggle.setStyleSheet("""
            QPushButton {
                background-color: #2A2A2A;
                color: #E6E6E6;
                border: 1px solid #3A3A3A;
                border-radius: 3px;
                padding: 5px 15px;
            }
            QPushButton:checked {
                background-color: #5D5236;
                color: #FFFFFF;
                border: 1px solid #D4BF8A;
            }
            QPushButton:hover {
                background-color: #3A3A3A;
            }
        """)
        self.midi_toggle.clicked.connect(self.toggle_midi)
        
        midi_layout.addWidget(QLabel("MIDI Port:"))
        midi_layout.addWidget(self.midi_port_combo)
        midi_layout.addWidget(self.midi_toggle)
        
        midi_group.setLayout(midi_layout)
        left_column.addWidget(midi_group)
        
        # Waveform selector below MIDI
        self.waveform_selector = WaveformSelector(midi_cc=1)
        self.waveform_selector.waveformChanged.connect(self.on_waveform_change)
        left_column.addWidget(self.waveform_selector)
        
        top_section.addLayout(left_column)
        
        # Right side - Controls
        right_section = QHBoxLayout()
        
        # Pitch control section
        pitch_group = QGroupBox("Pitch")
        pitch_layout = QHBoxLayout()
        
        self.stability_knob = LabeledKnob("Stability", 0, 20, 0, midi_cc=4)  # CC4 is foot control, repurposed
        self.stability_knob.valueChanged.connect(self.on_stability_change)
        pitch_layout.addWidget(self.stability_knob)
        
        self.coarse_tune_knob = LabeledKnob("Coarse", -24, 24, 0, midi_cc=2, is_integer=True)  # CC2 is breath control, repurposed
        self.coarse_tune_knob.valueChanged.connect(self.on_coarse_tune_change)
        self.coarse_tune_knob.knob.setNotchTarget(1.0)  # Force whole number steps
        pitch_layout.addWidget(self.coarse_tune_knob)
        
        self.fine_tune_knob = LabeledKnob("Fine", -100, 100, 0, midi_cc=3)  # CC3 is undefined, using for fine tune
        self.fine_tune_knob.valueChanged.connect(self.on_fine_tune_change)
        pitch_layout.addWidget(self.fine_tune_knob)
        
        pitch_group.setLayout(pitch_layout)
        right_section.addWidget(pitch_group)
        
        # Filter section
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout()
        
        self.cutoff_knob = LabeledKnob("Cutoff", 20, 20000, 2000, is_log=True, midi_cc=74)  # CC74 is filter cutoff
        self.cutoff_knob.valueChanged.connect(self.on_cutoff_change)
        filter_layout.addWidget(self.cutoff_knob)
        
        self.resonance_knob = LabeledKnob("Resonance", 0.1, 4, 0.5, midi_cc=71)  # Minimum of 0.1 to prevent silence
        self.resonance_knob.valueChanged.connect(self.on_resonance_change)
        filter_layout.addWidget(self.resonance_knob)
        
        filter_group.setLayout(filter_layout)
        right_section.addWidget(filter_group)
        
        # ADSR knobs
        adsr_group = QGroupBox("Envelope")
        adsr_layout = QHBoxLayout()
        
        self.attack_slider = LabeledKnob("Attack", 0.001, 5.0, 0.005, midi_cc=73)  # Up to 5 seconds
        self.attack_slider.valueChanged.connect(self.on_attack_change)
        adsr_layout.addWidget(self.attack_slider)
        
        self.decay_slider = LabeledKnob("Decay", 0.001, 3.0, 0.1, midi_cc=75)  # Up to 3 seconds
        self.decay_slider.valueChanged.connect(self.on_decay_change)
        adsr_layout.addWidget(self.decay_slider)
        
        self.sustain_slider = LabeledKnob("Sustain", 0.0, 1.0, 0.9, midi_cc=31)  # 0-1 range (unchanged)
        self.sustain_slider.valueChanged.connect(self.on_sustain_change)
        adsr_layout.addWidget(self.sustain_slider)
        
        self.release_slider = LabeledKnob("Release", 0.1, 5.0, 0.5, midi_cc=72)  # Up to 5 seconds
        self.release_slider.valueChanged.connect(self.on_release_change)
        adsr_layout.addWidget(self.release_slider)
        
        adsr_group.setLayout(adsr_layout)
        right_section.addWidget(adsr_group)
        
        # Gain knob
        gain_group = QGroupBox("Output")
        gain_layout = QHBoxLayout()
        
        self.gain_slider = LabeledKnob("Gain", 0.0, 1.0, 1.0, midi_cc=7)
        self.gain_slider.valueChanged.connect(self.on_gain_change)
        gain_layout.addWidget(self.gain_slider)
        
        gain_group.setLayout(gain_layout)
        right_section.addWidget(gain_group)
        
        top_section.addLayout(right_section)
        
        # Add top section to main layout
        main_layout.addLayout(top_section)
        
        # Add spacer to push keyboard to bottom
        main_layout.addStretch()
        
        # Piano keyboard at the bottom
        keyboard_group = QGroupBox("Keyboard")
        keyboard_layout = QVBoxLayout()
        
        self.piano = PianoKeys()
        self.piano.noteOn.connect(self.on_note_on)
        self.piano.noteOff.connect(self.on_note_off)
        keyboard_layout.addWidget(self.piano)
        
        keyboard_group.setLayout(keyboard_layout)
        main_layout.addWidget(keyboard_group)
        
        # Set window size
        self.resize(800, 600)
        
        # Initialize MIDI
        self.init_midi()
        
        # Update MIDI ports
        self.update_midi_ports()
        
        # Animate UI elements
        self._animate_ui_elements()
    
    def _animate_ui_elements(self):
        """Add start-up animations for expressionist feel"""
        # Create animated elements
        self.animations = []
        
        # Create a timer to animate waveform visualization
        self.wave_animation_timer = QTimer()
        self.wave_animation_timer.timeout.connect(self.waveform_selector.animate_wave)
        self.wave_animation_timer.start(50)  # Update every 50ms for smooth animation
        
    def init_parameters(self):
        """Initialize synth parameters via OSC"""
        # Send initial parameter values
        self.on_gain_change(1.0)
        self.on_waveform_change(2)  # sawtooth
        self.on_attack_change(0.005)
        self.on_decay_change(0.1)
        self.on_sustain_change(0.9)
        self.on_release_change(0.5)
        self.on_cutoff_change(2000)
        self.on_resonance_change(0.5)
        self.on_coarse_tune_change(0)
        self.on_fine_tune_change(0)
        self.on_stability_change(0)
    
    def update_midi_ports(self):
        """Update MIDI port selection dropdown"""
        current_port = self.midi_port_combo.currentText()
        
        # Clear current items
        self.midi_port_combo.clear()
        
        # Get available ports
        try:
            ports = mido.get_input_names()
            if ports:
                self.midi_port_combo.addItems(ports)
                
                # Restore previous selection if available
                if current_port in ports:
                    index = ports.index(current_port)
                    self.midi_port_combo.setCurrentIndex(index)
            else:
                self.midi_port_combo.addItem("No MIDI devices found")
        except Exception as e:
            self.midi_port_combo.addItem(f"Error: {str(e)}")
    
    def init_midi(self):
        """Initialize MIDI processing"""
        # To be initialized when user connects
        pass
    
    def toggle_midi(self):
        """Toggle MIDI connection on/off"""
        if not self.midi_running:
            self.start_midi()
        else:
            self.stop_midi()
    
    def start_midi(self):
        """Start MIDI processing"""
        if self.midi_running:
            return
            
        # Get selected port
        port_name = self.midi_port_combo.currentText()
        if not port_name or port_name.startswith("No MIDI") or port_name.startswith("Error"):
            self.midi_toggle.setText("Error: No valid MIDI port selected")
            self.midi_toggle.setStyleSheet("color: #FF5555; background: transparent;")
            return
        
        try:
            # Open MIDI input
            self.midi_input = mido.open_input(port_name)
            self.midi_running = True
            
            # Start MIDI processing thread
            self.midi_thread = threading.Thread(target=self.process_midi, daemon=True)
            self.midi_thread.start()
            
            # Update UI
            self.midi_toggle.setText("Disconnect MIDI")
            self.midi_toggle.setStyleSheet("color: #8AFF7A; background: transparent;")
            self.statusBar().showMessage(f"MIDI: Connected to {port_name} | OSC: {self.synth_name} on {self.osc_ip}:{self.osc_port}")
        
        except Exception as e:
            self.midi_toggle.setText(f"Error: {str(e)}")
            self.midi_toggle.setStyleSheet("color: #FF5555; background: transparent;")
    
    def stop_midi(self):
        """Stop MIDI processing"""
        if not self.midi_running:
            return
            
        # Close MIDI
        self.midi_running = False
        if self.midi_input:
            self.midi_input.close()
            self.midi_input = None
        
        # Update UI
        self.midi_toggle.setText("Connect MIDI")
        self.midi_toggle.setStyleSheet("color: #8A7A55; background: transparent;")
        self.statusBar().showMessage(f"OSC: {self.synth_name} on {self.osc_ip}:{self.osc_port}")
    
    def process_midi(self):
        """Process MIDI messages in a background thread"""
        while self.midi_running and self.midi_input:
            try:
                # Get pending messages
                for message in self.midi_input.iter_pending():
                    # Process in the main thread
                    self.handle_midi_message(message)
                
                # Brief sleep to prevent CPU overload
                time.sleep(0.001)
            except Exception as e:
                print(f"MIDI processing error: {e}")
                break
    
    def handle_midi_message(self, message):
        """Handle incoming MIDI message"""
        try:
            # Note on
            if message.type == 'note_on' and message.velocity > 0:
                # Convert MIDI note to frequency
                freq = 440.0 * (2.0 ** ((message.note - 69) / 12.0))
                
                # Add to active notes
                self.active_notes[message.note] = freq
                
                # Determine if we should use legato mode
                now = time.time()
                use_legato = (self.current_note is not None and 
                             (now - self.last_gate_off_time < self.LEGATO_THRESHOLD))
                
                # Set frequency first
                send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/freq", freq)
                
                # If not in legato mode or no current note, send gate on
                if not use_legato or self.current_note is None:
                    send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gate", 1.0)
                
                self.current_note = message.note
                
                # Update piano UI
                if self.piano.handle_midi_note_on(message.note, message.velocity):
                    # UI was updated successfully
                    pass
            
            # Note off
            elif message.type == 'note_off' or (message.type == 'note_on' and message.velocity == 0):
                # Remove from active notes
                if message.note in self.active_notes:
                    del self.active_notes[message.note]
                
                # Only react if this is the current sounding note
                if message.note == self.current_note:
                    # Check if we have other active notes
                    if self.active_notes:
                        # Find the highest note (usually most recently pressed)
                        next_note = max(self.active_notes.keys())
                        next_freq = self.active_notes[next_note]
                        
                        # Set the new frequency
                        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/freq", next_freq)
                        self.current_note = next_note
                    else:
                        # No more active notes, turn off gate
                        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gate", 0.0)
                        self.last_gate_off_time = time.time()
                        self.current_note = None
                
                # Update piano UI
                self.piano.handle_midi_note_off(message.note)
            
            # Control changes for parameters
            elif message.type == 'control_change':
                cc = message.control
                value = message.value
                
                # Map CC values to parameters
                if cc == self.waveform_selector.midi_cc:  # Modwheel for waveform
                    self.waveform_selector.set_from_midi_cc(value)
                
                elif cc == self.attack_slider.midi_cc:  # Attack
                    self.attack_slider.set_from_midi_cc(value)
                
                elif cc == self.decay_slider.midi_cc:  # Decay
                    self.decay_slider.set_from_midi_cc(value)
                
                elif cc == self.sustain_slider.midi_cc:  # Sustain
                    self.sustain_slider.set_from_midi_cc(value)
                
                elif cc == self.release_slider.midi_cc:  # Release
                    self.release_slider.set_from_midi_cc(value)
                
                elif cc == self.gain_slider.midi_cc:  # Main volume
                    self.gain_slider.set_from_midi_cc(value)
        
        except Exception as e:
            print(f"Error handling MIDI message: {e}")
    
    def on_gain_change(self, value):
        """Handle gain change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gain", value)
    
    def on_waveform_change(self, index):
        """Handle waveform change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/wave_type", index)
    
    def on_attack_change(self, value):
        """Handle attack change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/attack", value)
    
    def on_decay_change(self, value):
        """Handle decay change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/decay", value)
    
    def on_sustain_change(self, value):
        """Handle sustain change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/sustain", value)
    
    def on_release_change(self, value):
        """Handle release change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/release", value)
    
    def on_note_on(self, frequency):
        """Handle note on from UI"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/freq", frequency)
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gate", 1.0)
    
    def on_note_off(self):
        """Handle note off from UI"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gate", 0.0)
        
    def on_cutoff_change(self, value):
        """Handle filter cutoff change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/cutoff", value)
    
    def on_resonance_change(self, value):
        """Handle filter resonance change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/resonance", value)
    
    def on_coarse_tune_change(self, value):
        """Handle coarse tune change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/coarse_tune", value)
    
    def on_fine_tune_change(self, value):
        """Handle fine tune change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/fine_tune", value)
    
    def on_stability_change(self, value):
        """Handle stability change"""
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/stability", value)
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop MIDI processing
        self.stop_midi()
        
        # Turn off any sound
        send_osc(self.osc_ip, self.osc_port, f"/{self.synth_name}/gate", 0.0)
        
        # Accept the event
        event.accept()

# Entry point
if __name__ == "__main__":
    # Needed for waveform visualization
    import math
    
    # Allow custom synth name and OSC port
    synth_name = "legato_synth"
    osc_port = 5510
    
    if len(sys.argv) > 1:
        synth_name = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            osc_port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid OSC port: {sys.argv[2]}. Using default 5510.")
    
    # Create QApplication with custom style
    app = QApplication(sys.argv)
    
    # Show app icon
    try:
        app_icon = QPixmap("Murnau-App.png")
        if not app_icon.isNull():
            app.setWindowIcon(QIcon(app_icon))
    except Exception as e:
        print(f"Could not load app icon: {e}")
    
    # Create and display our window
    window = MurnauUI()
    window.synth_name = synth_name
    window.osc_port = osc_port
    
    # Apply expressionist style darkening effect to the app
    app.setStyle("Fusion")
    
    # Exit when app is closed
    sys.exit(app.exec())