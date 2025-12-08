from PyQt5.QtWidgets import QDialog, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import sqlite3
import os
import datetime
import sys
from PIL import Image as PILImage

class MatplotlibDialog(QDialog):
    def __init__(self):
        super(MatplotlibDialog, self).__init__()
        self.setWindowTitle("Grafik")
        self.setGeometry(100, 100, 1280, 720)
        layout = QVBoxLayout(self)
        self.canvas = FigureCanvas(Figure())
        layout.addWidget(self.canvas)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

    def convert_time(self, time_string):
        try:
            time_obj = datetime.datetime.strptime(time_string, "%Y-%m-%d %H:%M:%S")
            return time_obj.strftime("%H:%M:%S")
        except ValueError:
            return time_string

    def update_graph(self, id):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID=' + str(id))
        data = cursor.fetchall()
        conn.close()
        time_data = [self.convert_time(row[15]) for row in data]
        y_data = [list(row[:15]) for row in data]
        axes = self.canvas.figure.add_subplot(111)
        axes.clear()
        for i in range(15):
            values_to_plot = [y[i] if y[i] != 00.00 else None for y in y_data]
            if any(val is not None for val in values_to_plot):
                if i == 13:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 1')
                elif i == 14:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 2')
                else:
                    axes.plot(time_data, values_to_plot, marker='o', label=f'Prob{i + 1}')
        axes.set_title('Grafik Detayı')
        axes.set_xticklabels(time_data, rotation=45)
        axes.legend(loc='upper right', bbox_to_anchor=(1, 0.5))
        axes.yaxis.set_major_locator(MaxNLocator(nbins=10))
        self.canvas.draw()
        
    def update_graph_10(self, id):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID=' + str(id) + ' LIMIT 12')
        data = cursor.fetchall()
        conn.close()
        time_data = [self.convert_time(row[15]) for row in data]
        y_data = [[float(value) for value in row[:15]] for row in data]
        axes = self.canvas.figure.add_subplot(111)
        axes.clear()
        for i in range(15):
            values_to_plot = [y[i] if y[i] != 00.00 else None for y in y_data]
            if any(val is not None for val in values_to_plot):
                if i == 13:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 1')
                elif i == 14:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 2')
                else:
                    axes.plot(time_data, values_to_plot, marker='o', label=f'Prob{i + 1}')
        axes.set_title('Grafik Detayı')
        axes.set_xticklabels(time_data, rotation=45)
        axes.legend(loc='upper right', bbox_to_anchor=(1, 0.5))
        self.canvas.draw()
        
    def get_row_count_and_first_id(self, id):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(ID), MIN(ID), MAX(ID) FROM Report_Details WHERE REPORT_ID=' + str(id))
        row = cursor.fetchone()
        conn.close()
        return row[0], row[1], row[2]

    def update_graph_minimiz(self, id):
        row_count, first_id, last_id = self.get_row_count_and_first_id(id)
        if row_count is None or row_count == 0:
             return
             
        num_sections = 10
        step_per_section = (last_id - first_id) / num_sections if num_sections != 0 else 1
        ids = [int(first_id + step_per_section * i) for i in range(11)]
        ids_str = ','.join(map(str, ids))
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID=' + str(id) + ' AND ID IN (' + ids_str + ');')
        data = cursor.fetchall()
        conn.close()
        time_data = [self.convert_time(row[15]) for row in data]
        y_data = [list(row[:15]) for row in data]
        axes = self.canvas.figure.add_subplot(111)
        axes.clear()
        for i in range(15):
            values_to_plot = [y[i] if y[i] != 00.00 else None for y in y_data]
            if any(val is not None for val in values_to_plot):
                if i == 13:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 1')
                elif i == 14:
                    axes.plot(time_data, values_to_plot, marker='*', label='Ortam 2')
                else:
                    axes.plot(time_data, values_to_plot, marker='o', label=f'Prob{i + 1}')
        axes.set_title('Grafik Detayı')
        axes.set_xticklabels(time_data, rotation=45)
        axes.legend(loc='upper right', bbox_to_anchor=(1, 0.5))
        self.canvas.draw()

    def save_filtered_graph_png(self, id):
        row_count, first_id, last_id = self.get_row_count_and_first_id(id)
        if row_count is None or row_count == 0:
             return None

        num_sections = 10
        step_per_section = (last_id - first_id) / num_sections if num_sections != 0 else 1
        ids = [int(first_id + step_per_section * i) for i in range(11)]
        ids_str = ','.join(map(str, ids))
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID=' + str(id) + ' AND ID IN (' + ids_str + ');')
        data = cursor.fetchall()
        conn.close()
        time_data = [self.convert_time(row[15]) for row in data]
        y_data = [[float(value) for value in row[:15]] for row in data]
        plt.figure(figsize=(16, 9))
        for i in range(15):
            values_to_plot = [float(y[i]) if y[i] != 00.00 else None for y in y_data]
            if any(val is not None for val in values_to_plot):
                if i == 13:
                    plt.plot(time_data, values_to_plot, marker='*', label='Ortam 1')
                elif i == 14:
                    plt.plot(time_data, values_to_plot, marker='*', label='Ortam 2')
                else:
                    plt.plot(time_data, values_to_plot, marker='o', label=f'Prob{i + 1}')
        plt.title("Parti " + str(id) + " Grafik Detayı")
        plt.xticks(rotation=45)
        plt.legend(loc='upper right', bbox_to_anchor=(1, 0.5))
        save_path = "filtered_graph_real.png"
        plt.savefig(save_path)
        img = PILImage.open(save_path)
        rotated_img = img.rotate(-90, expand=True)
        rotated_img.save(save_path)
        return save_path
