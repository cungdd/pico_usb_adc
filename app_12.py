import os
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QTimer
import numpy as np

BUFFER_LENGTH = 5000

app = QApplication([])
pg.setConfigOption('background', 'w')  # Đặt nền đồ thị trắng

win = QWidget()
layout = QVBoxLayout()
win.setLayout(layout)

plot_widget = pg.PlotWidget(title="Dữ liệu từ cổng serial")
plot = plot_widget.getPlotItem()
curve = plot.plot([], [], pen=pg.mkPen('r', width=1))
plot.setLabel('left', 'Giá trị')
plot.setLabel('bottom', 'Thời gian')
plot.setYRange(0, 255)

layout.addWidget(plot_widget)

btn_zoom_in = QPushButton('Phóng to')
btn_zoom_out = QPushButton('Thu nhỏ')
btn_pause = QPushButton('Pause')

layout.addWidget(btn_zoom_in)
layout.addWidget(btn_zoom_out)
layout.addWidget(btn_pause)

data_buffer = []
is_paused = False

# Cấu hình cổng serial
port = '/dev/ttyACM0'  # Thay đổi tùy theo cổng USB của bạn (ví dụ: 'COM3' trên Windows)
baudrate = 115200
# Khởi tạo cổng serial
try:
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"Đã mở cổng serial {port} thành công.")
except Exception as e:
    print(f"Không thể mở cổng serial: {e}")
    exit()

def update_plot():
    global data_buffer, last_plot_buffer
    try:
        if not is_paused:
            if ser.in_waiting > 1:
                data = ser.read(ser.in_waiting)
                
                i = 0
                while i < len(data) - 1:
                    if (data[i] & 0x80):
                        value = ((data[i+1] & 0x3f) << 6) | (data[i] & 0x3f)
                        data_buffer.append(value)
                        i += 2
                    else:
                        i += 1
                
                if len(data_buffer) >= BUFFER_LENGTH:
                    time_data = np.linspace(0, 1, len(data_buffer))
                    curve.setData(time_data, data_buffer)
                    plot.setXRange(0, 1, padding=0)
                    last_plot_buffer = data_buffer.copy()
                    data_buffer = []
    except Exception as e:
        print(f"Lỗi trong quá trình cập nhật đồ thị: {e}")

def zoom_in():
    x_range = plot.viewRange()[0]
    current_range = x_range[1] - x_range[0]
    new_range = current_range / 1.2
    plot.setXRange(x_range[0], x_range[0] + new_range, padding=0)

def zoom_out():
    x_range = plot.viewRange()[0]
    current_range = x_range[1] - x_range[0]
    new_range = current_range * 1.2
    plot.setXRange(x_range[0], x_range[0] + new_range, padding=0)

def pause_update():
    global is_paused
    is_paused = not is_paused
    if is_paused:
        btn_pause.setText('Resume')
    else:
        btn_pause.setText('Pause')
        
def export_to_txt():
    global last_plot_buffer
    try:
        if last_plot_buffer:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'serial_data.txt')
            with open(file_path, 'w') as f:
                for value in last_plot_buffer[:BUFFER_LENGTH]:
                    f.write(f"{value}\n")
            print("Dữ liệu đã được xuất ra file 'serial_data.txt'.")
        else:
            print("Không có dữ liệu để xuất.")
    except Exception as e:
        print(f"Lỗi khi xuất file TXT: {e}")

# Kết nối các nút với các hàm điều chỉnh
btn_zoom_in.clicked.connect(zoom_in)
btn_zoom_out.clicked.connect(zoom_out)
btn_pause.clicked.connect(pause_update)

# Cập nhật đồ thị mỗi 10 ms
timer = QTimer()
timer.timeout.connect(update_plot)
timer.start(10)

win.show()
app.exec_()
ser.close()
