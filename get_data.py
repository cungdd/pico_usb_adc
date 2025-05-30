import os
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QTimer
import numpy as np
import time
import threading
import queue
import sys

sample_count = 0
last_time = time.time()

BUFFER_LENGTH = 5000
SAMPLE_RATE = 10000
EXPORT_DURATION_SEC = 10

# Hàng đợi để ghi dữ liệu nền
is_exporting = False
export_data_queue = queue.Queue()
log_queue = queue.Queue()
export_requests = queue.Queue()
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'serial_log.txt')

# Bộ nhớ chính
data_buffer = []
all_data = []
is_paused = False

# Thread ghi file
def log_writer():
    current_log_file = None
    current_hour = None

    buffer = []

    export_file = None

    while True:
        try:
            item = log_queue.get(timeout=1)
            if item is None:
                if current_log_file:
                    current_log_file.close()
                if export_file:
                    export_file.close()
                break

            # Ghi log bình thường
            buffer.extend(item)
            now = time.localtime()
            hour_str = time.strftime("%Y-%m-%d_%H", now)

            if hour_str != current_hour:
                if current_log_file:
                    current_log_file.close()
                filename = f"serial_log_{hour_str}.txt"
                full_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
                current_log_file = open(full_path, 'a')
                current_hour = hour_str
                print(f"📝 Ghi vào file log mới: {filename}")

            for val in item:
                current_log_file.write(f"{val}\n")
            current_log_file.flush()

            # Ghi dữ liệu export nếu đang bật
            try:
                while True:
                    export_item = export_data_queue.get_nowait()
                    if export_file is None:
                        export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'export_data.txt')
                        export_file = open(export_path, 'a')
                        print(f"📁 Bắt đầu ghi dữ liệu xuất vào 'export_data.txt'")
                    for v in export_item:
                        export_file.write(f"{v}\n")
                    export_file.flush()
            except queue.Empty:
                pass

            # Nếu export tắt thì đóng file export
            if export_file and export_data_queue.empty() and not is_exporting:
                export_file.close()
                export_file = None
                print("📁 Đã ngừng ghi dữ liệu xuất.")

        except queue.Empty:
            continue

# Khởi chạy thread ghi
log_thread = threading.Thread(target=log_writer)
log_thread.start()

# GUI setup
app = QApplication([])
pg.setConfigOption('background', 'w')

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
btn_export = QPushButton('Xuất 10s tiếp theo')

layout.addWidget(btn_zoom_in)
layout.addWidget(btn_zoom_out)
layout.addWidget(btn_pause)
layout.addWidget(btn_export)

# Serial config
port = input("Nhap port:")
baudrate = 115200
try:
    ser = serial.Serial(port, baudrate, timeout=1)
    print(f"Đã mở cổng serial {port} thành công.")
except Exception as e:
    print(f"Không thể mở cổng serial: {e}")
    log_queue.put(None)   # ⬅ Gửi tín hiệu kết thúc cho log_writer
    log_thread.join()     # ⬅ Chờ thread ghi kết thúc
    app.quit()            # ⬅ Thoát GUI nếu đã khởi tạo
    sys.exit()

def update_plot():
    global data_buffer, all_data, sample_count, last_time
    try:
        if not is_paused:
            if ser.in_waiting > 1:
                data = ser.read(ser.in_waiting)
                i = 0
                while i < len(data) - 1:
                    if (data[i] & 0x80):
                        value = ((data[i+1] & 0x3f) << 6) | (data[i] & 0x3f)
                        data_buffer.append(value)
                        sample_count += 1
                        i += 2
                    else:
                        i += 1

                if len(data_buffer) >= BUFFER_LENGTH:
                    time_data = np.linspace(0, 1, len(data_buffer))
                    curve.setData(time_data, data_buffer)
                    plot.setXRange(0, 1, padding=0)
                    
                    all_data.extend(data_buffer)
                    log_queue.put(list(data_buffer))  # Ghi log bình thường

                    if is_exporting:
                        export_data_queue.put(list(data_buffer))  # Ghi dữ liệu xuất

                    data_buffer = []

            current_time = time.time()
            if current_time - last_time >= 1.0:
                print(f"Tốc độ: {sample_count} mẫu/giây")
                sample_count = 0
                last_time = current_time
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
    btn_pause.setText('Resume' if is_paused else 'Pause')

def toggle_export():
    global is_exporting
    is_exporting = not is_exporting
    if is_exporting:
        btn_export.setText("Đang xuất dữ liệu...")
        btn_export.setStyleSheet("background-color: green; color: white;")
        print("▶️ Bắt đầu xuất dữ liệu vào file 'export_data.txt'")
    else:
        btn_export.setText("Bắt đầu xuất dữ liệu")
        btn_export.setStyleSheet("")
        print("⏹️ Dừng xuất dữ liệu")


# Nút
btn_zoom_in.clicked.connect(zoom_in)
btn_zoom_out.clicked.connect(zoom_out)
btn_pause.clicked.connect(pause_update)
btn_export.clicked.connect(toggle_export)
btn_export.setText("Bắt đầu xuất dữ liệu")

# Bắt đầu cập nhật
timer = QTimer()
timer.timeout.connect(update_plot)
timer.start(10)

win.show()
app.exec_()

# Kết thúc: dọn dẹp
ser.close()
log_queue.put(None)
log_thread.join()
