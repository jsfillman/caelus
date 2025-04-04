# controller.py
from PyQt5 import QtWidgets
from pythonosc.udp_client import SimpleUDPClient
import mido
import sys

osc = SimpleUDPClient("127.0.0.1", 9000)

class MidiController(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pyo Controller")
        self.setFixedSize(300, 200)

        self.init_ui()
        self.init_midi()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()

        self.sliders = {}
        for label, default in zip(['Attack', 'Decay', 'Sustain', 'Release'], [0.01, 0.1, 0.7, 0.5]):
            slider = QtWidgets.QSlider()
            slider.setOrientation(QtCore.Qt.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(1000)
            slider.setValue(int(default * 1000))
            slider.valueChanged.connect(self.send_adsr)
            layout.addWidget(QtWidgets.QLabel(label))
            layout.addWidget(slider)
            self.sliders[label.lower()] = slider

        self.setLayout(layout)

    def init_midi(self):
        self.inport = mido.open_input(callback=self.handle_midi)

    def send_adsr(self):
        # convert ms to sec, sustain as %
        a = self.sliders['attack'].value() / 1000.0
        d = self.sliders['decay'].value() / 1000.0
        s = self.sliders['sustain'].value() / 1000.0
        r = self.sliders['release'].value() / 1000.0
        osc.send_message("/adsr", [a, d, s, r])

    def handle_midi(self, msg):
        if msg.type == 'note_on' and msg.velocity > 0:
            freq = 440 * 2 ** ((msg.note - 69) / 12)
            amp = msg.velocity / 127
            osc.send_message("/note", [freq, amp])
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            osc.send_message("/note", [0, 0])

if __name__ == "__main__":
    from PyQt5 import QtCore
    app = QtWidgets.QApplication(sys.argv)
    window = MidiController()
    window.show()
    sys.exit(app.exec_())

