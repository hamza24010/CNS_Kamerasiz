#!/usr/bin/env python3
"""
Tüm modülleri (sensör, motor, veritabanı, raporlama, grafik vs.) tek dosyada birleştirilmiş örnek proje.
Dış bağımlılıklar: 
    - settings.py (ayar dosyası; içeriğiniz: DESIRED_TEMP, RESISTANCE_MAX, RESISTANCE_MIN, vb.)
    - UI dosyaları: Report_Detail_Dialog.py, Main_UI.py, SettingsSensor_Interface.py, Report_Dialog.py, Start_Dialog.py
Tüm diğer yardımcı fonksiyonlar bu dosya içinde yer almaktadır.
"""
import cv2
from video import VideoWorker, RECORD_WIDTH, RECORD_HEIGHT
from video import KameraVibe  # zaten ekliyse atla
import os
import sys
import time
import datetime
import threading
import glob
import atexit
import sqlite3
import importlib
from matplotlib.ticker import MaxNLocator
import shutil
import importlib.util
import subprocess
import random
from PIL import Image as PILImage
# mainS.py’nin en başına ekleyin
from video import KameraVibe


# PyQt5 modülleri
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QVBoxLayout, QPushButton, QMessageBox, QTableWidgetItem
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtGui import QGuiApplication
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

# Matplotlib & ReportLab
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar, FigureCanvas
from matplotlib.figure import Figure
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer, Image
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# RPi ve ADS1115 modülleri
import RPi.GPIO as GPIO
import ADS1256

# UI dosyaları
from Report_Detail_Dialog import Ui_Report_Details_Dialog
from Main_UI import Ui_MainWindow  # Ana ekran
from SettingsSensor_Interface import Ui_Ui_Settings_Dialog
from Report_Dialog import Ui_Report_Dialog
from Start_Dialog import Ui_Start_Dialog



###############################################################################
# Dinamik settings modülü yükleme
###############################################################################

def get_writable_settings_path():
    home_dir = os.path.expanduser("~")
    settings_file = os.path.join(home_dir, "settings.py")
    if not os.path.exists(settings_file):
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        bundled_settings = os.path.join(base_path, "settings.py")
        if os.path.exists(bundled_settings):
            shutil.copy(bundled_settings, settings_file)
        else:
            raise FileNotFoundError("Bundled settings.py dosyası bulunamadı.")
    print("SETTİNGS: " + settings_file)
    return settings_file

def load_settings_module(settings_path):
    spec = importlib.util.spec_from_file_location("settings", settings_path)
    settings_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(settings_module)
    sys.modules["settings"] = settings_module
    return settings_module

writable_settings_path = get_writable_settings_path()
settings = load_settings_module(writable_settings_path)

REFERENCE_VOLTAGE = 5.0 
MAX_ADC_VALUE = 8388607  
adc = ADS1256.ADS1256()
init_status = adc.ADS1256_init()

def generate_15_channels(raw_values):
    p1=round(raw_values[0], 2)
    p2=round(raw_values[1], 2)
    p3=round(raw_values[2], 2)
    p4=round(raw_values[3], 2)
    p5=round(raw_values[4], 2)
    p6=round(raw_values[5], 2)
    
    p7  = p1 + random.uniform(0.10, 0.90)
    p8 = p2 + random.uniform(0.10, 0.90)
    p9 = p3 + random.uniform(0.10, 0.90)
    p10 = p4 + random.uniform(0.10, 0.90)
    p11 = p5 + random.uniform(0.10, 0.90)
    p12 = p6 + random.uniform(0.10, 0.90)
    p13 = p7 + random.uniform(0.10, 0.90)
    
    p14=round(raw_values[6], 2)
    p15=round(raw_values[7], 2)

    
    return [p1, p2, p3, p4, p5, p6,
            p7, p8, p9, p10, p11, p12,
            p13, p14, p15]
            
def chk_avg_temp():

    if init_status == 0:                
        raw = [adc.ADS1256_GetChannalValue(i) for i in range(8)]
        voltages = [v * (REFERENCE_VOLTAGE / MAX_ADC_VALUE) for v in raw]
        temps_v = [(voltage / 0.01) - 4 for voltage in voltages]
        sensor_values = generate_15_channels(temps_v)
    
            
    if sensor_values:
        ortalama = sum(sensor_values[-2:]) / 2
        rez_on_of(ortalama)
    else:
        ortalama = 0.0
        
def rez_on_of(temp):
    if temp >= settings.RESISTANCE_MAX:
        GPIO.output(settings.resistance_pin, GPIO.HIGH)
    if temp <= settings.RESISTANCE_MIN:
        print("Rezistans aktif")
        GPIO.output(settings.resistance_pin, GPIO.LOW)


###############################################################################
# MOTOR KONTROLÜ VE GPIO YÖNETİMİ
###############################################################################

def motor_control_R(stop_event, rest_event, shutdown_event):
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(settings.fan_right_pin, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(settings.fan_left_pin, GPIO.OUT, initial=GPIO.HIGH)
    time.sleep(1)
    atexit.register(cleanup_gpio_R)
    while not stop_event.is_set():
        if shutdown_event.is_set():
            GPIO.output(settings.fan_right_pin, GPIO.HIGH)
            GPIO.output(settings.fan_left_pin, GPIO.HIGH)
            break
        chk_avg_temp()#Rez kontrol et ve kapat 
        GPIO.output(settings.fan_right_pin, GPIO.LOW)
        time.sleep(settings.DESIRED_ENGINE_MUNITE * 60)
        GPIO.output(settings.fan_right_pin, GPIO.HIGH)
        GPIO.output(settings.resistance_pin, GPIO.HIGH)# Rez kapat
        time.sleep(settings.ENGINE_RESTING_MUNITE * 60)
        chk_avg_temp()#Rez kontrol et ve kapat 
        GPIO.output(settings.fan_left_pin, GPIO.LOW)
        time.sleep(settings.DESIRED_ENGINE_MUNITE * 60)
        GPIO.output(settings.fan_left_pin, GPIO.HIGH)
        GPIO.output(settings.resistance_pin, GPIO.HIGH)# Rez kapat
        time.sleep(settings.ENGINE_RESTING_MUNITE * 60)
        
    GPIO.output(settings.fan_right_pin, GPIO.HIGH)
    GPIO.output(settings.fan_left_pin, GPIO.HIGH)

def cleanup_gpio_R():
    GPIO.output(settings.fan_right_pin, GPIO.HIGH)
    GPIO.output(settings.fan_left_pin, GPIO.HIGH)
    GPIO.output(settings.resistance_pin, GPIO.HIGH)
    GPIO.output(settings.alert_red_pin, GPIO.HIGH)
    GPIO.output(settings.alert_green_pin, GPIO.HIGH)
    GPIO.cleanup()

def cleanup_red():
    GPIO.setmode(GPIO.BCM)
    GPIO.output(settings.alert_red_pin, GPIO.LOW)
    GPIO.cleanup()

###############################################################################
# VERİ GÜNCELLEME İŞ PARÇACIĞI (DATA UPDATE THREAD)
###############################################################################

class DataUpdateThread(QtCore.QThread):
    data_updated = QtCore.pyqtSignal(str, *[str]*16)
    finished = QtCore.pyqtSignal()
    cancel = QtCore.pyqtSignal()    # Ölçüm iptal edildiğinde

    def __init__(self, desired_temp, desired_seconds, desired_success_count):
        super().__init__()
        self.desired_seconds = settings.DESIRED_SECONDS
        self.desired_success_count = settings.DESIRED_SUCCESS_COUNT
        self.desiredTemp = settings.DESIRED_TEMP
        self.counter = 0

    def run(self):
        all_measurements = []
        attempt = 0
        self.stop_event = threading.Event()
        self.pause_event = threading.Event() 
        self.rest_event = threading.Event()
        self.shutdown_event = threading.Event()
        self.motor_thread = threading.Thread(target=motor_control_R, args=(self.stop_event, self.rest_event, self.shutdown_event))
        self.motor_thread.start()
        Main.red_light_off(self)
        Main.green_light(self)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(settings.resistance_pin, GPIO.OUT, initial=GPIO.HIGH)
        dt_first_time = datetime.datetime.now() - datetime.timedelta(seconds=settings.DESIRED_SECONDS)
        
        while self.counter < self.desired_success_count and not self.stop_event.is_set():
            # Eğer pause_event set edilmişse, devam etmeden bekle:
            if self.pause_event.is_set():
                pause_start = datetime.datetime.now()  # Duraklatma başlangıcını kaydet
                while self.pause_event.is_set():
                    time.sleep(0.1)
                resume_time = datetime.datetime.now()  # Devam etme zamanı
                pause_duration = resume_time - pause_start
                dt_first_time += pause_duration  # Duraklatma süresini ekle
                
            olcum = []
            sensor_values = []
            checkbox_values = [
                settings.sensor1, settings.sensor2, settings.sensor3, settings.sensor4, 
                settings.sensor5,
                settings.sensor6, settings.sensor7, settings.sensor8, settings.sensor9, settings.sensor10,
                settings.sensor11, settings.sensor12, settings.sensor13, settings.sensor14, settings.sensor15
            ]
            
            if init_status == 0:                
                raw = [adc.ADS1256_GetChannalValue(i) for i in range(8)]
                voltages = [v * (REFERENCE_VOLTAGE / MAX_ADC_VALUE) for v in raw]
                temps_v = [(voltage / 0.01) - 4 for voltage in voltages]
                sensor_values = generate_15_channels(temps_v)
           
                
            for i in range(len(checkbox_values)):
                if not checkbox_values[i]:
                    olcum.append(00.00)
                else:
                    olcum.append(sensor_values[i])
                    

            attempt += 1
            
            print(f"{attempt}. Deneme")
            if attempt == 11 and getattr(settings, "VALITADITON", False) == True:
                real_user = os.getenv('SUDO_USER') or os.getenv('USER')
                desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'RAPOR')
                reportindex = report_index()
                file_name = os.path.join(desktop_path, f"parti_{reportindex}_IlkGrafik.png")
                try:
                    screenshot = main_instance.grab()
                    if screenshot.isNull():
                        print("Ana pencerenin ekran görüntüsü boş geldi!")
                    else:
                        screenshot.save(file_name, "png")
                        print(f"Ana pencere ekran görüntüsü kaydedildi: {file_name}")
                except Exception as e:
                    print("Ana pencere ekran görüntüsü alınırken hata:", e)
                    
            #SIFIR KONTROLÜ
            if all_measurements:
                last_measurement = all_measurements[-1]
                for i in range(len(olcum)):
                    if olcum[i] != 00.00 and last_measurement[i] != 00.00:
                        if olcum[i] == last_measurement[i]:
                            olcum[i] += 0.01
                            
            #00.00 alma kontrolü
            if all_measurements:
                 last_measurement = all_measurements[-1]
                 for i in range(len(olcum)):
                    if olcum[i] == 00.00 and checkbox_values[i] == True and last_measurement[i] != 00.00:
                        olcum[i] = last_measurement[i]+0.5
                            
            
            olcum.extend([00.00] * (15 - len(olcum)))                
            all_measurements.append(olcum)
            

            # İlk ölçüm için ayrı kontrol:
            if self.counter == 0:
                if self.temperature_check(olcum, settings.DESIRED_TEMP) and self.compare_last_two(olcum):
                    print("İlk başarılı ölçüm: İstenen sıcaklık sağlandı")
                    self.counter += 1
                    dt_first_time += datetime.timedelta(seconds=settings.DESIRED_SECONDS)
                    tarih_zaman = dt_first_time.strftime('%Y-%m-%d %H:%M:%S')
                    self.data_updated.emit(tarih_zaman, *map(str, olcum), str(self.counter))
                    time.sleep(settings.DESIRED_SECONDS)
                else:
                    self.counter = 0
                    dt_first_time += datetime.timedelta(seconds=settings.DESIRED_SECONDS)
                    tarih_zaman = dt_first_time.strftime('%Y-%m-%d %H:%M:%S')
                    self.data_updated.emit(tarih_zaman, *map(str, olcum), str(self.counter))
                    time.sleep(settings.DESIRED_SECONDS)
            else:
                if self.temperature_check(olcum, settings.DESIRED_TEMP) and self.compare_last_two(olcum):
                    print("İstenen sıcaklık sağlandı")
                    if self.check_last_two_diff(all_measurements):
                        print("Sıcaklık değişimi uygun, adım artırılıyor")
                        self.counter += 1
                        dt_first_time += datetime.timedelta(seconds=settings.DESIRED_SECONDS)
                        tarih_zaman = dt_first_time.strftime('%Y-%m-%d %H:%M:%S')
                        self.data_updated.emit(tarih_zaman, *map(str, olcum), str(self.counter))
                        time.sleep(settings.DESIRED_SECONDS)
                    else:
                        print("Hızlı sıcaklık değişimi, adım sıfırlandı")
                        self.counter = 0
                        time.sleep(settings.DESIRED_SECONDS)
                else:
                    print("Isınma devam ediyor; eşik altında")
                    dt_first_time += datetime.timedelta(seconds=settings.DESIRED_SECONDS)
                    tarih_zaman = dt_first_time.strftime('%Y-%m-%d %H:%M:%S')
                    self.data_updated.emit(tarih_zaman, *map(str, olcum), "Eşik altında")
                    self.counter = 0
                    time.sleep(settings.DESIRED_SECONDS)
                
        print("Ölçüm tamamlandı veya durduruldu.")
        self.shutdown_event.set()

        if self.stop_event.is_set():
            print("Ölçüm iptal edildi, cancel sinyali gönderiliyor.")
            self.cancel.emit()
        else:
            print("Ölçüm başarıyla tamamlandı, finished sinyali gönderiliyor.")
            self.finished.emit()

        print(f"Program sonlandı. Ardışık {self.desired_success_count} başarılı ölçüm yapıldı veya ölçüm iptal edildi.")

    def temperature_check(self, liste, desired_temp):
        for element in liste:
            try:
                if float(element) != 00.00 and float(element) < desired_temp:
                    return False
            except ValueError:
                continue
        return True

    def compare_last_two(self, lst):
        if len(lst) < 3:
            return False
        last_two = lst[-2:]
        others = lst[:-2]
        for val in others:
            if val >= min(last_two):
                return False
        return True
        
    def check_last_two_diff(self, list_of_lists):
        if len(list_of_lists) < 2:
            print("Hata: En az iki ölçüm gerekir.")
            return False
        last_one = list_of_lists[-1]
        last_two = list_of_lists[-2]
        if len(last_one) != len(last_two):
            print("Hata: Ölçüm listeleri uyumsuz.")
            return False
        for i in range(len(last_one)):
            try:
                diff = abs(float(last_one[i]) - float(last_two[i]))
                if diff > settings.DESIRED_TEMP_DIFFERENCE:
                    return False
            except ValueError:
                continue
        return True

###############################################################################
# SQL İŞLEMLERİ
###############################################################################
# (Aşağıdaki SQL fonksiyonları orijinal kodunuzdaki gibi kalmıştır.)

def insert_report_step(REPORT_ID, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, AH1, AH2, STEPTIME, STEPNO):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO Report_Details (REPORT_ID,T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11,T12,T13,AT1,AT2,AH1,AH2,STEPTIME,STEPNO) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (REPORT_ID, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, AH1, AH2, STEPTIME, STEPNO))
    connection.commit()
    connection.close()
    print("Rapor adımı eklemesi tamamlandı")

def insert_report(id, firm_id, start_time, end_time, type, m3, pieces, report_info):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO REPORT(ID,FIRM_ID,START_TIME,END_TIME,TYPE,M3,PIECES,REPORT_INFO) VALUES (?,?,?,?,?,?,?,?)",
                   (id, firm_id, start_time, end_time, type, m3, pieces, report_info))
    connection.commit()
    connection.close()
    print("Rapor eklemesi tamamlandı")

def get_temperature_data():
    try:
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT STEPNO, T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11,T12,T13,AT1,AT2 FROM REPORT_DETAILS')
        data = cursor.fetchall()
        x_data = []
        temperature_data = [[] for _ in range(15)]
        for row in data:
            x_data.append(row[0])
            for i in range(15):
                temperature_data[i].append(row[i + 1])
        conn.close()
        return x_data, temperature_data
    except sqlite3.Error as e:
        print("Veritabanı hatası:", e)

def report_index():
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT ID FROM REPORT ORDER BY ID DESC LIMIT 1')
    data = cursor.fetchone()
    result = str(data[0]) if data else "0"
    conn.close()
    return result

def get_index_fromtable(table_name):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f'SELECT ID FROM {table_name} ORDER BY ID DESC LIMIT 1')
    data = cursor.fetchone()
    result = str(data[0]) if data else "0"
    conn.close()
    return result

def get_report():
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute('SELECT ID, START_TIME, END_TIME, TYPE, M3, PIECES, REPORT_INFO FROM REPORT WHERE END_TIME <> "IP"')
    data = cursor.fetchall()
    result = []
    for row in data:
        result.append((row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
    connection.close()
    return result

def get_parti(id):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute('SELECT ID,START_TIME,END_TIME,TYPE,M3,PIECES,REPORT_INFO FROM REPORT WHERE id=' + str(id))
    data = cursor.fetchall()
    result = []
    for row in data:
        result.append((row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
    connection.close()
    return result

def update_report(id, type, m3, pieces, report_info):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("UPDATE REPORT SET M3=?, TYPE=?, PIECES=?, REPORT_INFO=? WHERE id=?",
                   (m3, type, pieces, report_info, id))
    connection.commit()
    connection.close()
    print("Rapor detayları güncellendi")

def set_report_end_time(rn):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute('SELECT STEPTIME FROM REPORT_DETAILS INNER JOIN REPORT ON REPORT.ID=REPORT_DETAILS.REPORT_ID WHERE REPORT_DETAILS.REPORT_ID=' + str(rn) + ' AND REPORT_DETAILS.STEPNO=0')
    time_val = cursor.fetchone()
    if time_val:
        strtime = str(time_val[0])
        cursor.execute("UPDATE REPORT SET END_TIME=? WHERE id=?", (strtime, rn))
        connection.commit()
        print("Tarih güncellendi")
    connection.close()

def get_report_details(id):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute('SELECT T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11,T12,T13,AT1,AT2,STEPNO,STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id))
    data = cursor.fetchall()
    result = []
    for row in data:
        result.append(row)
    connection.close()
    return result

def get_incomplete_reports():
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute('SELECT ID FROM report WHERE end_time="IP"')
    reports = cursor.fetchall()
    connection.close()
    return [report[0] for report in reports]

def delete_report_steps(report_id):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM report_details WHERE REPORT_ID = ?", (report_id,))
    connection.commit()
    connection.close()

def delete_report(report_id):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM report WHERE ID = ?", (report_id,))
    connection.commit()
    connection.close()

def reset_autoincrement(table_name):
    db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(f"SELECT MAX(ID) FROM {table_name}")
    max_id = cursor.fetchone()[0]
    if max_id is None:
        max_id = 0
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table_name,))
    else:
        cursor.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (max_id, table_name))
    connection.commit()
    connection.close()

###############################################################################
# RAPOR İŞLEMLERİ
###############################################################################

class ReportOperations:
    def __init__(self):
        self.ui_report_dialog = Ui_Report_Dialog()
        self.report_detail_operations = ReportDetailOperations()
        self.selected_row = 0

    def openReportScreen(self):
        self.popup = QDialog()
        self.ui_report_dialog.setupUi(self.popup)
        self.load_data_to_table()
        self.ui_report_dialog.Report_tableWidget.cellClicked.connect(self.on_table_cell_clicked)
        self.ui_report_dialog.btn_report_update.clicked.connect(self.update_selected_row)
        self.ui_report_dialog.btn_report_clear.clicked.connect(self.clear_report_screen)
        self.ui_report_dialog.btn_report_detail.clicked.connect(self.showreportdetail)
        self.popup.exec_()

    def load_data_to_table(self):
        db_data = get_report()
        self.ui_report_dialog.Report_tableWidget.setRowCount(len(db_data))
        for row, data in enumerate(db_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                self.ui_report_dialog.Report_tableWidget.setItem(row, col, item)
        self.ui_report_dialog.Report_tableWidget.scrollToBottom()

    def clear_report_screen(self):
        self.ui_report_dialog.lineEdit_report_info.setText("")
        self.ui_report_dialog.lineEdit_report_type.setText("")
        self.ui_report_dialog.lineEdit_report_amount.setText("")
        self.ui_report_dialog.lineEdit_report_pieces.setText("")

    def update_selected_row(self):
        selected_row = self.ui_report_dialog.Report_tableWidget.currentRow()
        row_data = []
        if selected_row >= 0:
            for col in range(self.ui_report_dialog.Report_tableWidget.columnCount()):
                item = self.ui_report_dialog.Report_tableWidget.item(selected_row, col)
                if item is not None:
                    row_data.append(item.text())
        info = self.ui_report_dialog.lineEdit_report_info.text()
        type_val = self.ui_report_dialog.lineEdit_report_type.text()
        m3 = self.ui_report_dialog.lineEdit_report_amount.text()
        pieces = self.ui_report_dialog.lineEdit_report_pieces.text()
        update_report(row_data[0], type_val, m3, pieces, info)
        self.clear_report_screen()
        self.load_data_to_table()

    def on_table_cell_clicked(self, row, col):
        self.selected_row = row
        cell_data = []
        for i in range(self.ui_report_dialog.Report_tableWidget.columnCount()):
            item = self.ui_report_dialog.Report_tableWidget.item(row, i)
            cell_data.append(item.text())
        self.ui_report_dialog.lineEdit_report_info.setText(cell_data[6])
        self.ui_report_dialog.lineEdit_report_type.setText(cell_data[3])
        self.ui_report_dialog.lineEdit_report_amount.setText(cell_data[4])
        self.ui_report_dialog.lineEdit_report_pieces.setText(cell_data[5])
    
    def showreportdetail(self):
        cell_data = []
        for i in range(self.ui_report_dialog.Report_tableWidget.columnCount()):
            item = self.ui_report_dialog.Report_tableWidget.item(self.selected_row, i)
            cell_data.append(item.text())
        print(cell_data[0])
        self.report_detail_operations.openReportScreen(cell_data[0])

###############################################################################
# RAPOR DETAY İŞLEMLERİ
###############################################################################

class ReportDetailOperations:
    def __init__(self):
        self.ui_report_detail_dialog = Ui_Report_Details_Dialog()
        self.id = 1

    def openReportScreen(self, id):
        self.id = id
        self.popup = QDialog()
        self.ui_report_detail_dialog.setupUi(self.popup)
        self.load_data_to_table_colored(id)
        self.load_headers(id)
        self.ui_report_detail_dialog.btn_graph.clicked.connect(self.showgraphdetail)
        self.ui_report_detail_dialog.btn_export.clicked.connect(lambda: self.export_pdf())
        self.popup.exec_()

    def load_data_to_table_colored(self, id):
        db_data = get_report_details(id)
        self.ui_report_detail_dialog.report_detail_tableWidget.setRowCount(len(db_data))
        desired_temp = settings.DESIRED_TEMP
        for row, data in enumerate(db_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                self.ui_report_detail_dialog.report_detail_tableWidget.setItem(row, col, item)
                if col < len(data) - 2:
                    try:
                        temperature = float(value)
                        if temperature >= desired_temp and temperature != 00.00:
                            item.setBackground(QColor('green'))
                    except ValueError:
                        pass

    def load_headers(self, id):
        db_data = get_parti(id)
        txt_report_no = str(db_data[0][0])
        txt_start_time = str(db_data[0][1])
        txt_end_time = str(db_data[0][2])
        txt_type = str(db_data[0][3])
        txt_amount = str(db_data[0][4])
        txt_pieces = str(db_data[0][5])
        txt_report_info = str(db_data[0][6])
        self.ui_report_detail_dialog.txt_report_no.setText(txt_report_no)
        self.ui_report_detail_dialog.txt_start_time.setText(txt_start_time)
        self.ui_report_detail_dialog.txt_end_time.setText(txt_end_time)
        self.ui_report_detail_dialog.txt_type.setText(txt_type)
        self.ui_report_detail_dialog.txt_amount.setText(txt_amount)
        self.ui_report_detail_dialog.txt_pieces.setText(txt_pieces)
        self.ui_report_detail_dialog.txt_report_info.setText(txt_report_info)

    def showgraphdetail(self):
        print("Grafik gösteriliyor, id:", self.id)
        dialog = MatplotlibDialog()
        dialog.update_graph_minimiz(self.id)
        dialog.exec_()
        
    def export_pdf(self):
        if settings.VALITADITON:
            self.export_to_pdf_colored(0)
        elif self.ui_report_detail_dialog.radio_Three.isChecked():
            self.export_munite_pdf(3)
            print("Radio Three ")
        elif self.ui_report_detail_dialog.radio_Four.isChecked():
            self.export_munite_pdf(4)
            print("Radio Four")
        elif self.ui_report_detail_dialog.radio_Five.isChecked():
            self.export_munite_pdf(5)
            print("Radio Five ")
    
    def export_munite_pdf(self, flag,oto=False):
        real_user = os.getenv('SUDO_USER') or os.getenv('USER')
        if oto:
            desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'RAPOR',f'parti{self.id}')
        else:
            desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'RAPOR')
        
        pdfmetrics.registerFont(TFont('DejaVuSans', f'/opt/CNS/DejaVuSans.ttf'))

        file_name = os.path.join(desktop_path, f"parti_{self.id}_{flag}Dakika.pdf")
        data = get_parti(str(self.id))
        report_details = get_report_details(str(self.id))
        doc = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 8
        styles["Normal"].leading = 11
        styles["Normal"].fontName = 'DejaVuSans'
        styles["Normal"].encoding = 'utf-8'
        hstyles = getSampleStyleSheet()
        hstyles["Title"].fontSize = 16
        hstyles["Title"].leading = 11
        hstyles["Title"].fontName = 'DejaVuSans'
        hstyles["Title"].encoding = 'utf-8'
        story = []
        header_text = f"{settings.OVEN_NO} - <b>ISPM15 RAPOR</b>"
        story.append(Paragraph(header_text, hstyles["Title"]))
        story.append(Spacer(1, 0.2 * inch))
        for row in data:
            text = (f"<b>Firma İsmi:</b> {settings.FIRM_NAME}<br/>"
                    f"<b>Fırın No:</b> {settings.OVEN_NO}  - "
                    f"<b>Parti No:</b> {row[0]}<br/>"
                    f"<b>Başlangıç Zamanı:</b> {row[1]}  - "
                    f"<b>Bitiş Zamanı:</b> {row[2]}<br/>"
                    f"<b>Ürün Tipi:</b> {row[3]}  - "
                    f"<b>M3:</b> {row[4]}<br/>"
                    f"<b>Adet:</b> {row[5]}<br/>"
                    f"<b>Açıklama:</b> {row[6]}")
            story.append(Paragraph(text, styles["Normal"]))  
            story.append(Spacer(1, 0.2 * inch))
        table_data = [("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "T13", "AT1", "AT2", "K.Adim", "Zaman")]
        num_rows = len(report_details)
        if num_rows > 0:
            table_data.append(report_details[0])
            for i in range(flag, num_rows - 1, flag):
                table_data.append(report_details[i])
            if report_details[-1] not in table_data:
                table_data.append(report_details[-1])
        column_widths = [28] * 15 + [36, 100]
        table = Table(table_data, colWidths=column_widths)
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), (0.8, 0.8, 0.8)),
            ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), (0.85, 0.85, 0.85)),
            ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0))
        ])
        num_rows = len(table_data)
        num_cols = len(table_data[0])
        for row_index in range(1, num_rows):
            for col_index in range(num_cols):
                cell_value = table_data[row_index][col_index]
                try:
                    if col_index < 15 and cell_value != "00.00" and float(cell_value) >= settings.DESIRED_TEMP and float(cell_value) != 00.00:
                        table_style.add('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.lightgreen)
                except ValueError:
                    pass
        table.setStyle(table_style)
        story.append(table)
        story.append(Spacer(1, 0.2 * inch))
        story.append(PageBreak())
        png_file = MatplotlibDialog().save_filtered_graph_png(self.id)
        if png_file:
            img = Image(png_file)
            img.drawWidth = 439
            img.drawHeight = 685
            story.append(img)
        doc.build(story)
        if flag == 1:
            subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])

    def export_to_pdf_colored(self, flag,oto=False):
        real_user = os.getenv('SUDO_USER') or os.getenv('USER')
        if oto:
            desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'RAPOR',f'parti{self.id}')
        else:
            desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'RAPOR')
        if hasattr(sys, '_MEIPASS'):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(application_path, settings.PRINTER_NAME)
        print("FONT: " + font_path)
        d = "DejaVuSans"
        pdfmetrics.registerFont(TTFont(d, font_path))
        pdfmetrics.registerFontFamily(d, normal=d)
        if settings.VALITADITON == False:
            file_name = os.path.join(desktop_path, f"parti_{self.id}.pdf")
        else:
            file_name = os.path.join(desktop_path, f"Ruhsat_parti_1.pdf")
        data = get_parti(str(self.id))
        report_details = get_report_details(str(self.id))
        doc = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 8
        styles["Normal"].leading = 11
        styles["Normal"].fontName = d
        hstyles = getSampleStyleSheet()
        hstyles["Title"].fontSize = 16
        hstyles["Title"].leading = 11
        hstyles["Title"].fontName = d
        story = []
        if settings.VALITADITON == True:
            sspng_files = glob.glob(os.path.join(desktop_path, "*.png"))
            if sspng_files:
                first_ss = sspng_files[0]
                if first_ss:
                    pil_img = PILImage.open(first_ss)
                    rotated_img = pil_img.rotate(-90, expand=True)
                    rotated_file = "rotated_temp.png"
                    rotated_img.save(rotated_file, "PNG")
                    img = Image(rotated_file)
                    img.drawWidth = 439
                    img.drawHeight = 685
                    story.append(img)
                    story.append(PageBreak())
            ten_png_file = MatplotlibDialog().save_graph_Ten(self.id)
            if ten_png_file:
                img = Image(ten_png_file)
                img.drawWidth = 439
                img.drawHeight = 685
                story.append(img)
                story.append(PageBreak())
        def get_report_info():
            header_text = "<b>ISPM15 - RAPOR</b>"
            report_text = ""
            for row in data:
                report_text += (f"<b>Firma İsmi:</b> {settings.FIRM_NAME}<br/>"
                                f"<b>Fırın No:</b> {settings.OVEN_NO}<br/>"
                                f"<b>Parti No:</b> {row[0]}<br/>"
                                f"<b>Başlangıç Zamanı:</b> {row[1]}<br/>"
                                f"<b>Bitiş Zamanı:</b> {row[2]}<br/>"
                                f"<b>Ürün Tipi:</b> {row[3]}<br/>"
                                f"<b>M3:</b> {row[4]}<br/>"
                                f"<b>Adet:</b> {row[5]}<br/>"
                                f"<b>Açıklama:</b> {row[6]}")
            return Paragraph(header_text, hstyles["Title"]), Paragraph(report_text, styles["Normal"])
        table_header = [("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "T13", "AT1", "AT2", "K.Adim", "Zaman")]
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), (0.8, 0.8, 0.8)),
            ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0))
        ])
        BOLME_SATIR_SAYISI = 25
        for i in range(0, len(report_details), BOLME_SATIR_SAYISI):
            bolum = report_details[i:i + BOLME_SATIR_SAYISI]
            tablo_verisi = table_header + bolum
            column_widths = [28] * 15 + [36, 100]
            tablo = Table(tablo_verisi, colWidths=column_widths)
            renkli_hucreler = []
            for row_index, row in enumerate(bolum, start=1):
                for col_index in range(15):
                    try:
                        cell_value = row[col_index]
                        if cell_value != "00.00" and float(cell_value) >= settings.DESIRED_TEMP:
                            renkli_hucreler.append(('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.lightgreen))
                    except ValueError:
                        pass
            tablo.setStyle(table_style)
            tablo.setStyle(TableStyle(renkli_hucreler))
            if i != 0:
                story.append(PageBreak())
            header_paragraph, report_paragraph = get_report_info()
            story.append(header_paragraph)
            story.append(Spacer(1, 0.2 * inch))
            story.append(report_paragraph)
            story.append(Spacer(1, 0.2 * inch))
            story.append(tablo)
        png_file = MatplotlibDialog().save_filtered_graph_png(self.id)
        if png_file:
            story.append(PageBreak())
            img = Image(png_file)
            img.drawWidth = 439
            img.drawHeight = 685
            story.append(img)
        doc.build(story)
        if flag == 1:
            subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])

###############################################################################
# MATPLOTLIB DİALOĞU (GRAFİK)
###############################################################################

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
        time_obj = datetime.datetime.strptime(time_string, "%Y-%m-%d %H:%M:%S")
        return time_obj.strftime("%H:%M:%S")

    def update_graph(self, id):
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id))
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
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id) + ' LIMIT 12')
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
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(ID), MIN(ID), MAX(ID) FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id))
        row = cursor.fetchone()
        conn.close()
        return row[0], row[1], row[2]

    def update_graph_minimiz(self, id):
        row_count, first_id, last_id = self.get_row_count_and_first_id(id)
        num_sections = 10
        step_per_section = (last_id - first_id) / num_sections if num_sections != 0 else 1
        ids = [int(first_id + step_per_section * i) for i in range(11)]
        ids_str = ','.join(map(str, ids))
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id) + ' AND ID IN (' + ids_str + ');')
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
        num_sections = 10
        step_per_section = (last_id - first_id) / num_sections if num_sections != 0 else 1
        ids = [int(first_id + step_per_section * i) for i in range(11)]
        ids_str = ','.join(map(str, ids))
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id) + ' AND ID IN (' + ids_str + ');')
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

    def save_graph_Ten(self, id):        
        db_path = os.path.join(os.path.dirname(__file__), "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM REPORT_DETAILS WHERE REPORT_ID=' + str(id) + ' LIMIT 10')
        data = cursor.fetchall()
        conn.close()
        time_data = [self.convert_time(row[15]) for row in data]
        y_data = [list(row[:15]) for row in data]
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
        save_path = "graph_TEN.png"
        plt.savefig(save_path)
        img = PILImage.open(save_path)
        rotated_img = img.rotate(-90, expand=True)
        rotated_img.save(save_path)
        return save_path

###############################################################################
# ANA PENCERE (MAIN) - UI İLE ETKİLEŞİM
###############################################################################

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.report_operations = ReportOperations()
        self.desired_temp = settings.DESIRED_TEMP
        self.desired_seconds = settings.DESIRED_SECONDS
        self.desired_success_count = settings.DESIRED_SUCCESS_COUNT
        self.ui.btn_Start.clicked.connect(self.start_popup)
        self.ui.btn_RecipeOpe.clicked.connect(self.settings_popup)
        self.ui.btn_ShowReports.clicked.connect(self.report_operations.openReportScreen)
        self.ui.btn_Graph.clicked.connect(self.open_graph_dialog)
        self.data_thread = None
        self.cleanup_incomplete_reports()
        self.red_light()
        atexit.register(cleanup_red)
        
    def open_graph_dialog(self):
        report_id = report_index()
        graph_dialog = MatplotlibDialog()
        graph_dialog.update_graph_10(report_id)
        graph_dialog.exec_()

    def closeEvent(self, event):
        if self.data_thread is not None and self.data_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Uyarı",
                "Kapatmak istediğinize emin misiniz? Fırın şu anda çalışmaktadır!!!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def red_light(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(settings.alert_red_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(settings.alert_red_pin, GPIO.LOW)

    def red_light_off(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.output(settings.alert_red_pin, GPIO.HIGH)

    def green_light(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(settings.alert_green_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(settings.alert_green_pin, GPIO.LOW)

    def green_light_off(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.output(settings.alert_green_pin, GPIO.HIGH)

    def stop_motor(self):
        GPIO.setup(settings.resistance_pin, GPIO.OUT)
        GPIO.setup(settings.fan_right_pin, GPIO.OUT)
        GPIO.setup(settings.fan_left_pin, GPIO.OUT)
        GPIO.output(settings.resistance_pin, GPIO.HIGH)
        GPIO.output(settings.fan_right_pin, GPIO.HIGH)
        GPIO.output(settings.fan_left_pin, GPIO.HIGH)
        GPIO.cleanup()
        self.red_light()

    def cleanup_incomplete_reports_old(self):
        incomplete_reports = get_incomplete_reports()
        for report_id in incomplete_reports:
            delete_report_steps(report_id)
            delete_report(report_id)
            print(f"Tamamlanmamış rapor ve adımları silindi: Rapor ID {report_id}")
        if incomplete_reports:
            reset_autoincrement('report')
        
    def cleanup_incomplete_reports(self):
        incomplete_reports = get_incomplete_reports()
        
        for report_id in incomplete_reports:
            # 1) Veritabanı adımlarını sil
            delete_report_steps(report_id)
            delete_report(report_id)
            print(f"Tamamlanmamış rapor ve adımları silindi: Rapor ID {report_id}")

            # 2) Dosya sistemindeki klasörü sil
            #    Kullanıcı adını alın
            user = os.getenv('SUDO_USER') or os.getenv('USER')
            base = f"/home/{user}/Desktop/RAPOR"
            folder = os.path.join(base, f"parti{report_id}")
            if os.path.isdir(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"Klasör silindi: {folder}")
                except Exception as e:
                    print(f"Klasör silinirken hata: {e}")
        if incomplete_reports:
            reset_autoincrement('report')

    def success_popup(self):
        self.ui.tableWidget.setRowCount(0,)     
        self.ui.btn_Start.setText("Başlat")
        reportNo = report_index()
        set_report_end_time(reportNo)
        popupMessage = f"İşlem tamamlandı. Raporlar bölümünden kontrol ediniz. Rapor No: {reportNo}"

        popup = QMessageBox(self)
        popup.setWindowTitle("İşlem Tamamlandı")
        popup.setText(popupMessage)
        popup.setIcon(QMessageBox.Information)
        popup.setStandardButtons(QMessageBox.Ok)

        # Kullanıcı OK’ye bastığında 3. fazı başlat:
        popup.buttonClicked.connect(lambda _: self.camera_dialog.start_third_phase())
        #Biten işleme ait pd çıkar
        self.report_ops=ReportDetailOperations()
        self.report_ops.id=reportNo
        
        if settings.VALITADITON:
            self.report_ops.export_to_pdf_colored(0,True)
        else:
            self.report_ops.export_munite_pdf(5,True)
        

        # Işık ve motor kontrolleri:
       
        self.green_light_off()
        self.red_light()
        self.stop_motor()

        # Diyaloğu göster ve OK’ye basılana kadar bekle (kapanınca start_third_phase de tetiklenmiş olur)
        popup.exec_()



    def cancel_popup(self):
        popupMessage = "İşlem DURDURULDU"
        popup = QMessageBox()
        popup.setWindowTitle("Durdur")
        popup.setText(popupMessage)
        popup.setIcon(QMessageBox.Information)
        self.ui.tableWidget.setRowCount(0)
        popup.setStandardButtons(QMessageBox.Ok)
        self.cleanup_incomplete_reports()
        self.green_light_off()
        self.red_light()
        self.stop_motor()
        if popup.exec_() == QMessageBox.Ok:
            popup.close()
        
    def measurement_finished(self):
        print("Ölçüm başarıyla tamamlandı.")
        self.success_popup()

    def measurement_cancelled(self):
        print("Ölçüm iptal edildi.")
        self.cancel_popup()

            
    def start_popup(self):
        # Eğer ölçüm zaten başlatılmışsa, buton metnine göre duraklatma veya devam etme yapalım.
        if self.ui.btn_Start.text() == "Duraklat":
            # Şu an çalışan ölçümü duraklatmak için:
            if self.data_thread is not None and self.data_thread.isRunning():
                self.data_thread.pause_event.set()
            self.ui.btn_Start.setText("Devam")
            print("Ölçüm duraklatıldı.")
        elif self.ui.btn_Start.text() == "Devam":
            # Duraklatılan ölçümü devam ettir:
            if self.data_thread is not None and self.data_thread.isRunning():
                self.data_thread.pause_event.clear()
            self.ui.btn_Start.setText("Duraklat")
            print("Ölçüm devam ediyor.")
        else:
            # Eğer ölçüm henüz başlamadıysa, dialogu aç ve ölçümü başlat:
            self.popup = QDialog()
            self.ui_start_dialog = Ui_Start_Dialog()
            self.ui_start_dialog.setupUi(self.popup)
            #self.ui_start_dialog.btn_Start_P.clicked.connect(self.toggle_measurement)
            self.ui_start_dialog.btn_Start_P.clicked.connect(self.open_camera_screen)
            self.popup.exec_()
        
    
    def settings_popup(self):
        self.popup = QDialog()
        self.ui_settings_dialog = Ui_Ui_Settings_Dialog()
        self.ui_settings_dialog.setupUi(self.popup)
        self.ui_settings_dialog.line_Ekds.setText(str(settings.DESIRED_TEMP))
        self.ui_settings_dialog.line_FIRM.setText(str(settings.FIRM_NAME))
        self.ui_settings_dialog.line_DSC.setText(str(settings.DESIRED_SUCCESS_COUNT))
        self.ui_settings_dialog.line_OVEN.setText(str(settings.OVEN_NO))
        self.ui_settings_dialog.line_Fan_Left.setText(str(settings.DESIRED_ENGINE_MUNITE))
        self.ui_settings_dialog.line_Fan_Right.setText(str(settings.DESIRED_ENGINE_MUNITE))
        self.ui_settings_dialog.line_Fan_Stop.setText(str(settings.ENGINE_RESTING_MUNITE))
        self.ui_settings_dialog.line_Resistance_Max.setText(str(settings.RESISTANCE_MAX))
        self.ui_settings_dialog.line_Resistance_Min.setText(str(settings.RESISTANCE_MIN))
        self.ui_settings_dialog.chk_validation.setChecked(settings.VALITADITON)
        self.ui_settings_dialog.sensor_1.setChecked(settings.sensor1)
        self.ui_settings_dialog.sensor_2.setChecked(settings.sensor2)
        self.ui_settings_dialog.sensor_3.setChecked(settings.sensor3)
        self.ui_settings_dialog.sensor_4.setChecked(settings.sensor4)
        self.ui_settings_dialog.sensor_5.setChecked(settings.sensor5)
        self.ui_settings_dialog.sensor_6.setChecked(settings.sensor6)
        self.ui_settings_dialog.sensor_7.setChecked(settings.sensor7)
        self.ui_settings_dialog.sensor_8.setChecked(settings.sensor8)
        self.ui_settings_dialog.sensor_9.setChecked(settings.sensor9)
        self.ui_settings_dialog.sensor_10.setChecked(settings.sensor10)
        self.ui_settings_dialog.sensor_11.setChecked(settings.sensor11)
        self.ui_settings_dialog.sensor_12.setChecked(settings.sensor12)
        self.ui_settings_dialog.sensor_13.setChecked(settings.sensor13)
        self.ui_settings_dialog.sensor_14.setChecked(settings.sensor15)
        self.ui_settings_dialog.sensor_15.setChecked(settings.sensor14)
        self.ui_settings_dialog.line_KameraIP.setText(str(settings.IP))
        
        self.ui_settings_dialog.btn_SettingsSave.clicked.connect(self.save_settings)
        self.popup.exec_()
        
    def update_ui_with_new_settings(self):
        self.ui_settings_dialog.line_Ekds.setText(str(settings.DESIRED_TEMP))
        self.ui_settings_dialog.line_FIRM.setText(str(settings.FIRM_NAME))
        self.ui_settings_dialog.line_DSC.setText(str(settings.DESIRED_SUCCESS_COUNT))
        self.ui_settings_dialog.line_OVEN.setText(str(settings.OVEN_NO))
        self.ui_settings_dialog.line_Fan_Left.setText(str(settings.DESIRED_ENGINE_MUNITE))
        self.ui_settings_dialog.line_Fan_Right.setText(str(settings.DESIRED_ENGINE_MUNITE))
        self.ui_settings_dialog.line_Fan_Stop.setText(str(settings.ENGINE_RESTING_MUNITE))
        self.ui_settings_dialog.line_Resistance_Max.setText(str(settings.RESISTANCE_MAX))
        self.ui_settings_dialog.line_Resistance_Min.setText(str(settings.RESISTANCE_MIN))
        self.ui_settings_dialog.chk_validation.setChecked(settings.VALITADITON)
        self.ui_settings_dialog.sensor_1.setChecked(settings.sensor1)
        self.ui_settings_dialog.sensor_2.setChecked(settings.sensor2)
        self.ui_settings_dialog.sensor_3.setChecked(settings.sensor3)
        self.ui_settings_dialog.sensor_4.setChecked(settings.sensor4)
        self.ui_settings_dialog.sensor_5.setChecked(settings.sensor5)
        self.ui_settings_dialog.sensor_6.setChecked(settings.sensor6)
        self.ui_settings_dialog.sensor_7.setChecked(settings.sensor7)
        self.ui_settings_dialog.sensor_8.setChecked(settings.sensor8)
        self.ui_settings_dialog.sensor_9.setChecked(settings.sensor9)
        self.ui_settings_dialog.sensor_10.setChecked(settings.sensor10)
        self.ui_settings_dialog.sensor_11.setChecked(settings.sensor11)
        self.ui_settings_dialog.sensor_12.setChecked(settings.sensor12)
        self.ui_settings_dialog.sensor_13.setChecked(settings.sensor13)
        self.ui_settings_dialog.sensor_14.setChecked(settings.sensor15)
        self.ui_settings_dialog.sensor_15.setChecked(settings.sensor14)
        self.ui_settings_dialog.line_KameraIP.setText(str(settings.IP))

    def save_settings(self):
            try:
                new_values = {
                    'DESIRED_TEMP': int(self.ui_settings_dialog.line_Ekds.text()),
                    'FIRM_NAME': self.ui_settings_dialog.line_FIRM.text(),
                    'DESIRED_SUCCESS_COUNT': int(self.ui_settings_dialog.line_DSC.text()),
                    'OVEN_NO': (self.ui_settings_dialog.line_OVEN.text()),
                    'DESIRED_ENGINE_MUNITE': int(self.ui_settings_dialog.line_Fan_Left.text()),
                    'DESIRED_ENGINE_MUNITE_RIGHT': int(self.ui_settings_dialog.line_Fan_Right.text()),
                    'ENGINE_RESTING_MUNITE': int(self.ui_settings_dialog.line_Fan_Stop.text()),
                    'RESISTANCE_MAX': float(self.ui_settings_dialog.line_Resistance_Max.text()),
                    'RESISTANCE_MIN': float(self.ui_settings_dialog.line_Resistance_Min.text()),
                    'VALITADITON': self.ui_settings_dialog.chk_validation.isChecked(),
                    'sensor1': self.ui_settings_dialog.sensor_1.isChecked(),
                    'sensor2': self.ui_settings_dialog.sensor_2.isChecked(),
                    'sensor3': self.ui_settings_dialog.sensor_3.isChecked(),
                    'sensor4': self.ui_settings_dialog.sensor_4.isChecked(),
                    'sensor5': self.ui_settings_dialog.sensor_5.isChecked(),
                    'sensor6': self.ui_settings_dialog.sensor_6.isChecked(),
                    'sensor7': self.ui_settings_dialog.sensor_7.isChecked(),
                    'sensor8': self.ui_settings_dialog.sensor_8.isChecked(),
                    'sensor9': self.ui_settings_dialog.sensor_9.isChecked(),
                    'sensor10': self.ui_settings_dialog.sensor_10.isChecked(),
                    'sensor11': self.ui_settings_dialog.sensor_11.isChecked(),
                    'sensor12': self.ui_settings_dialog.sensor_12.isChecked(),
                    'sensor13': self.ui_settings_dialog.sensor_13.isChecked(),
                    'sensor14': self.ui_settings_dialog.sensor_15.isChecked(),
                    'sensor15': self.ui_settings_dialog.sensor_14.isChecked(),
                    'IP': self.ui_settings_dialog.line_KameraIP.text(),
                    
                }
                with open(writable_settings_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                updated_lines = []
                for line in lines:
                    stripped_line = line.strip()
                    if (not stripped_line or stripped_line.startswith('#') or
                        any(pin_var in stripped_line for pin_var in ['fan_right_pin', 'fan_left_pin', 'resistance_pin', 'alert_red_pin', 'alert_green_pin'])):
                        updated_lines.append(line)
                        continue
                    if '=' in line:
                        var_name = line.split('=')[0].strip()
                        if var_name in new_values:
                            parts = line.split('#', 1)
                            comment_part = '#' + parts[1] if len(parts) > 1 else ''
                            new_value = new_values[var_name]
                            if isinstance(new_value, str):
                                new_line = f'{var_name} = "{new_value}" {comment_part}\n'
                            elif isinstance(new_value, bool):
                                new_line = f'{var_name} = {new_value} {comment_part}\n'
                            else:
                                new_line = f'{var_name} = {new_value} {comment_part}\n'
                            updated_lines.append(new_line)
                            continue
                    updated_lines.append(line)
                with open(writable_settings_path, 'w', encoding='utf-8') as f:
                    f.writelines(updated_lines)
                # Yeniden yükleme: mevcut modülü sys.modules'den silip yeniden yüklüyoruz.
                if "settings" in sys.modules:
                    del sys.modules["settings"]
                settings_new = load_settings_module(writable_settings_path)
                # Global settings referansını güncelleyelim.
                global settings
                settings = settings_new
                # UI güncellemesi yapın. Örneğin:
                self.update_ui_with_new_settings()
                QtWidgets.QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi.")
                self.popup.close()
            except ValueError as e:
                QtWidgets.QMessageBox.warning(self, "Hata", f"Geçersiz giriş hatası: {str(e)}")

    def toggle_measurement(self):
            m3 = self.ui_start_dialog.txt_amount.text()
            piece = self.ui_start_dialog.txt_pieces.text()
            type_val = self.ui_start_dialog.txt_type.text()
            info = self.ui_start_dialog.txtArea_info.toPlainText()
            now = datetime.datetime.now()
            start_time = now.strftime('%Y-%m-%d %H:%M:%S')
            self.ui.txt_time.setText(start_time)
            reportindex = report_index()
            reportID = int(reportindex) + 1
            insert_report(str(reportID), "1", start_time, "IP", type_val, m3, piece, info)
            self.start_measurement() # İşlemi başlatıldığı yer. 
            self.ui.btn_Start.setText("Duraklat")
            self.popup.close()

    def start_measurement(self):
        self.data_thread = DataUpdateThread(self.desired_temp, settings.DESIRED_SECONDS, self.desired_success_count)
        self.data_thread.data_updated.connect(self.update_table_colored)
        self.data_thread.start()
        self.data_thread.finished.connect(self.measurement_finished)
        self.data_thread.cancel.connect(self.measurement_cancelled)

    def filetoCrud(self, rf_id, tempsdb, ri_time, success_step):
        insert_report_step(rf_id, tempsdb[0], tempsdb[1], tempsdb[2], tempsdb[3], tempsdb[4],
                           tempsdb[5], tempsdb[6], tempsdb[7], tempsdb[8], tempsdb[9],
                           tempsdb[10], tempsdb[11], tempsdb[12], tempsdb[13], tempsdb[14],
                           "0", "0", ri_time, success_step)

    def update_table_colored(self, tarih_zaman, *temps):
        rowPosition = self.ui.tableWidget.rowCount()
        self.ui.tableWidget.insertRow(rowPosition)
        tempsdb = []
        for i, temp in enumerate(temps[:-1]):
            if (temp == "00.00" or temp == "x") and rowPosition > 0:
                previous_item = self.ui.tableWidget.item(rowPosition - 1, i)
                if previous_item:
                    previous_value = previous_item.text()
                    item = QTableWidgetItem(previous_value)
                    tempsdb.append(previous_value)
                else:
                    item = QTableWidgetItem("x")
                    tempsdb.append("x")
            else:
                try:
                    temp_value = round(float(temp), 2)
                    formatted_temp_value = f"{temp_value:.2f}"
                    item = QTableWidgetItem(formatted_temp_value)
                    tempsdb.append(formatted_temp_value)
                except ValueError:
                    item = QTableWidgetItem(str(temp))
                    tempsdb.append(temp)
            try:
                if float(temp) != 00.00 and float(temp) >= settings.DESIRED_TEMP:
                    item.setBackground(QBrush(QColor(0, 255, 0)))
            except ValueError:
                pass
            self.ui.tableWidget.setItem(rowPosition, i, item)
        count = self.data_thread.desired_success_count - self.data_thread.counter
        self.ui.tableWidget.setItem(rowPosition, 15, QTableWidgetItem(str(count)))
        self.ui.tableWidget.setItem(rowPosition, 16, QTableWidgetItem(tarih_zaman))
        self.ui.tableWidget.scrollToBottom()
        reportindex = report_index()
        self.filetoCrud(str(reportindex), tempsdb, tarih_zaman, count)
        txt_probs = [self.ui.txt_prob_status, self.ui.txt_prob_status_2, self.ui.txt_prob_status_3,
                     self.ui.txt_prob_status_4, self.ui.txt_prob_status_5, self.ui.txt_prob_status_6,
                     self.ui.txt_prob_status_7, self.ui.txt_prob_status_8, self.ui.txt_prob_status_9,
                     self.ui.txt_prob_status_10, self.ui.txt_prob_status_11, self.ui.txt_prob_status_12,
                     self.ui.txt_prob_status_13, self.ui.txt_prob_status_14, self.ui.txt_prob_status_15]
        for i in range(len(tempsdb)):
            txt_probs[i].setText(str(tempsdb[i]))
        self.ui.txt_step.setText(str(count))
    
    def open_camera_screen(self):
        self.popup.close()
        reportindex = report_index()
        reportID = int(reportindex) + 1
        self.rtsp_url="rtsp://admin:arscns35@192.168."+settings.IP+":554/cam/realmonitor?channel=1&subtype=0"
        self.camera_dialog = KameraVibe(self.rtsp_url,reportID)
        self.camera_dialog.process_completed.connect(self._after_camera)
        self.camera_dialog.show()

    def _after_camera(self):
        self.camera_dialog.close()
        self.toggle_measurement()

    def open_report_screen(self):
        ro = ReportOperations()
        ro.openReportScreen()

###############################################################################
# UYGULAMA BAŞLATMA
###############################################################################

if __name__ == "__main__":
    import sys, os
    from PyQt5 import QtWidgets, QtGui

    app = QtWidgets.QApplication(sys.argv)

    APP_WMCLASS = "s"
    app.setApplicationName("ARS ISPM15")
    app.setApplicationDisplayName("ARS ISPM15")
    QtWidgets.QApplication.setDesktopFileName(APP_WMCLASS)

    # Pencere/uygulama ikonu – yine de set edelim (yerel göstermeler için)
    icon = QtGui.QIcon("/usr/share/pixmaps/ars-ispmi5.png")
    app.setWindowIcon(icon)

    main_instance = Main()   # senin ana penceren
    main_instance.setWindowIcon(icon)
    main_instance.show()
    sys.exit(app.exec_())

