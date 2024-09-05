import os
import serial
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QTimer
import numpy as np
import pandas as pd

BUFFER_LENGTH = 5000

# Cấu hình cổng serial
port = '/dev/ttyACM0'  # Thay đổi tùy theo cổng USB của bạn (ví dụ: 'COM3' trên Windows)

# Khởi tạo cổng serial
try:
    ser = serial.Serial(port)
    print(f"Đã mở cổng serial {port} thành công.")
except Exception as e:
    print(f"Không thể mở cổng serial: {e}")
    exit()

# Khởi tạo cửa sổ đồ thị và các nút điều khiển
app = QApplication([])
win = QWidget()
layout = QVBoxLayout()
win.setLayout(layout)

# Khởi tạo widget đồ thị
plot_widget = pg.GraphicsLayoutWidget()
plot = plot_widget.addPlot(title="Dữ liệu từ cổng serial")
curve = plot.plot([], [], pen=pg.mkPen('r', width=1))  # Đường đỏ với độ dày 1
plot.setLabel('left', 'Giá trị')
plot.setLabel('bottom', 'Thời gian')

# Điều chỉnh phạm vi Y-axis để phù hợp với giá trị 12-bit
plot.setYRange(0, 4096)  # 16-bit values range from 0 to 65535

# Đặt nền của đồ thị thành màu trắng
plot_widget.setBackground('w')  # Sử dụng phương thức này để đặt nền trắng cho toàn bộ widget

layout.addWidget(plot_widget)

# Thêm các nút điều khiển
btn_zoom_in = QPushButton('Phóng to')
btn_zoom_out = QPushButton('Thu nhỏ')
btn_pause = QPushButton('Pause')
btn_export_excel = QPushButton('Xuất Excel')

layout.addWidget(btn_zoom_in)
layout.addWidget(btn_zoom_out)
layout.addWidget(btn_pause)
layout.addWidget(btn_export_excel)

# Danh sách lưu trữ dữ liệu
data_buffer = []
last_plot_buffer = []
is_paused = False

def update_plot():
    global data_buffer, last_plot_buffer
    try:
        if not is_paused:
            if ser.in_waiting > 1:  # Đảm bảo có ít nhất 2 byte để đọc
                # Đọc dữ liệu từ cổng serial
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
                    # Tạo trục thời gian tương ứng với dữ liệu
                    time_data = np.linspace(0, 1, len(data_buffer))
                    
                    # Cập nhật đồ thị
                    curve.setData(time_data, data_buffer)
                    plot.setXRange(0, 1, padding=0)  # Thiết lập trục x cho 1 giây
                    
                    last_plot_buffer = data_buffer.copy()
                    
                    # Xóa bộ đệm sau khi đã vẽ dữ liệu
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
            # Chỉ ghi 100,000 giá trị vào file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, 'serial_data.txt')
            
            # Lưu dữ liệu vào file txt
            with open(file_path, 'w') as f:
                for value in last_plot_buffer[:BUFFER_LENGTH]:
                    f.write(f"{value}\n")
            print("Dữ liệu đã được xuất ra file 'serial_data.txt'.")
        else:
            print("Không có dữ liệu để xuất.")
    except Exception as e:
        print(f"Lỗi khi xuất file TXT: {e}")
        
def export_to_excel():
    try:
        if data_buffer:
            # Tao dataframe với 2 cot: Thu tu va gia tri
            df = pd.DataFrame({
                'Thứ tự': range(1, len(data_buffer) + 1),
                'Giá trị': data_buffer
            })
            # Luu du lieu vao file excel
            df.to_excel('serial_data.xlsx', index=False)
            print("Dữ liệu đã được xuất ra file 'serial_data.xlsx'.")
        else:
            print("Không có dữ liệu để xuất.")
    except Exception as e:
        print(f"Lỗi khi xuất file Excel: {e}")

# Kết nối các nút với các hàm điều chỉnh
btn_zoom_in.clicked.connect(zoom_in)
btn_zoom_out.clicked.connect(zoom_out)
btn_pause.clicked.connect(pause_update)
btn_export_excel.clicked.connect(export_to_txt)

# Cập nhật đồ thị mỗi giây
timer = QTimer()
timer.timeout.connect(update_plot)
timer.start(10)  # Cập nhật mỗi 10 ms (100,000 giá trị mỗi giây)

win.show()
app.exec_()  # Khởi chạy ứng dụng

ser.close()  # Đóng cổng serial khi kết thúc
