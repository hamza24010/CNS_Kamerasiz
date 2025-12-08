#!/usr/bin/env python3
"""
ISPM-15 FINAL RUHSAT SİMÜLASYONU (mainS.py) - V8
- Seçilen sensörler, sistemdeki "En Yavaş 4'lü" olarak davranır.
- Raporlardaki "Isı Şoku" (100°C) ve "Yumuşama" (80°C) eğrileri eklendi.
- Sensörler arası makas (Spread) gerçek raporlardaki gibi daraltıldı.
"""
import os
import sys
import time
import datetime
import threading
import sqlite3
import importlib.util
import shutil
import random
import atexit
import math
import requests # Hava durumu için

# Grafik ve PDF
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar, FigureCanvas
from matplotlib.figure import Figure
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# PyQt5
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QVBoxLayout, QPushButton, QMessageBox, QTableWidgetItem, QLabel, QSpinBox, QHBoxLayout
from PyQt5.QtGui import QBrush, QColor, QGuiApplication

# UI Dosyaları
from Report_Detail_Dialog import Ui_Report_Details_Dialog
from Main_UI import Ui_MainWindow
from SettingsSensor_Interface import Ui_Ui_Settings_Dialog
from Report_Dialog import Ui_Report_Dialog
from Start_Dialog import Ui_Start_Dialog
import glob
import subprocess
from PIL import Image as PILImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from matplotlib.ticker import MaxNLocator

# --- SANAL GPIO ---
class MockGPIO:
    BCM = "BCM"; OUT = "OUT"; IN = "IN"; HIGH = 1; LOW = 0
    @staticmethod
    def setwarnings(flag): pass
    @staticmethod
    def setmode(mode): pass
    @staticmethod
    def setup(pin, mode, initial=0, pull_up_down=None): pass
    @staticmethod
    def output(pin, state):
        state_str = "HIGH" if state == 1 else "LOW"
        print(f"[MOCK GPIO] Pin {pin} -> {state_str}")
    @staticmethod
    def cleanup(): pass
    @staticmethod
    def PUD_UP(self): pass

try:
    import RPi.GPIO as GPIO
    print("Gerçek GPIO Modülü Yüklendi.")
except ImportError:
    print("RPi.GPIO bulunamadı, MockGPIO kullanılıyor.")
    GPIO = MockGPIO()

# --- HAVA DURUMU (Simülasyon Başlangıcı) ---
# --- HAVA DURUMU (Gerçek Veri) ---
def get_online_temperature():
    try:
        print("Konum ve hava durumu alınıyor...")
        # 1. Konum Bul (IP-API)
        loc_resp = requests.get("http://ip-api.com/json/", timeout=2)
        if loc_resp.status_code == 200:
            data = loc_resp.json()
            lat = data['lat']
            lon = data['lon']
            city = data['city']
            print(f"Konum: {city} ({lat}, {lon})")
            
            # 2. Sıcaklık Çek (Open-Meteo)
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            w_resp = requests.get(weather_url, timeout=2)
            if w_resp.status_code == 200:
                w_data = w_resp.json()
                temp = w_data['current_weather']['temperature']
                print(f"İnternetten Çekilen Sıcaklık: {temp}°C")
                return float(temp)
                
        raise Exception("API Hatası")
        
    except Exception as e:
        print(f"Hava durumu alınamadı ({e}). Varsayılan değer kullanılıyor.")
        # Fallback: Ruhsat raporlarına göre 15-20 derece arası ideal başlangıç
        return random.uniform(15.0, 20.0)

# --- GELİŞMİŞ SİMÜLASYON FİZİĞİ ---
class ISPM15Simulator:
    def __init__(self):
        self.start_temp = get_online_temperature()
        print(f"Simülasyon Başlatıldı. Dış Ortam: {self.start_temp:.2f}°C")
        
        # RUHSAT RAPORU SENARYOSU (Egemsoon & Parti 1)
        self.target_shock = 102.0
        self.target_approach = 85.0
        self.target_hold = 78.0
        
        self.firin_set_degeri = self.target_shock
        
        # Dinamik Ortam Isınma Hızı (Dış sıcaklığa bağlı)
        # Yeni Formül (Tuning): Base 1.8, Sensitivity 0.01
        base_rate = 1.8
        temp_factor = 1.0 + (self.start_temp - 20.0) * 0.01
        temp_factor = max(0.5, min(1.5, temp_factor))
        
        self.hava_isinma_hizi = base_rate * temp_factor
        print(f"Dinamik Isınma Hızı: {self.hava_isinma_hizi:.2f} (Dış Sıcaklık: {self.start_temp:.1f}°C)")
        
        # FİZİKSEL MODELLER (Sensör Profilleri)
        # Kullanıcı İsteği: Tüm sensörler (13 adet) başta birbirine yakın olsun (+/- 0.5 fark).
        # Zamanla açılsınlar (Farklı ısınma hızları).
        
        self.sensor_states = []
        
        # Ortam Sensörleri (AT1, AT2)
        self.at_states = [
            {"val": self.start_temp + random.uniform(-0.2, 0.2)}, # AT1
            {"val": self.start_temp + random.uniform(-0.2, 0.2)}  # AT2
        ]
        
        # Takoz Sensörleri (13 Adet)
        for i in range(13):
            # Başlangıç Değeri: Hepsi ortama çok yakın başlar
            start_val = self.start_temp + random.uniform(-0.5, 0.5)
            
            # Isınma Hızı (İletim Katsayısı)
            # Yavaş Grup: 1, 9, 11, 13 (Index: 0, 8, 10, 12)
            # Diğerleri: Hızlı Grup
            if i in [0, 8, 10, 12]:
                # Yavaşlar (Sırasıyla biraz artar)
                iletim = 0.0065 + (i * 0.0005) 
            else:
                # Hızlılar (Daha hızlı artar, makas açılır)
                iletim = 0.0100 + (i * 0.0020)
                
            self.sensor_states.append({
                "val": start_val,
                "iletim": iletim
            })
        
        self.rezistans_aktif = True
        self.sogutma_modu = False
        self.sterilizasyon_basladi = False
        self.phase = "SHOCK" 
        self.virtual_heater_on = True 

    def calculate_step(self, active_sensors_mask, desired_temp):
        # 1. AKTİF SENSÖRLERİ TESPİT ET
        # active_sensors_mask: 15 elemanlı (13 prob + 2 ortam)
        output_values = [0.0] * 15
        current_takoz_vals = []
        
        # 2. SENSÖR HESAPLAMALARI
        for i in range(13):
            if active_sensors_mask[i]:
                # Mevcut değer
                val = self.sensor_states[i]["val"]
                
                # Çözünürlük ve Dalgalanma (Noise)
                noise = random.uniform(-0.03, 0.03)
                val_with_noise = val + noise
                
                output_values[i] = val_with_noise
                
                # Sadece Yavaş Grubun (1, 9, 11, 13) değerlerini kontrol döngüsüne al
                # Çünkü süreci en yavaşlar belirler.
                if i in [0, 8, 10, 12]:
                    current_takoz_vals.append(val_with_noise)

        # Ortam Değerleri
        at1_val = self.at_states[0]["val"]
        at2_val = self.at_states[1]["val"]
        
        # Ortam Noise
        at1_out = at1_val + random.uniform(-0.05, 0.05)
        at2_out = at2_val + random.uniform(-0.05, 0.05)
        
        if active_sensors_mask[13]: output_values[13] = at1_out
        if active_sensors_mask[14]: output_values[14] = at2_out

        # 3. KONTROL VE FAZ MANTIĞI (Sanal Termostat)
        avg_ortam = (at1_val + at2_val) / 2.0
        
        if avg_ortam >= settings.RESISTANCE_MAX:
            self.virtual_heater_on = False
        elif avg_ortam <= settings.RESISTANCE_MIN:
            self.virtual_heater_on = True
            
        effective_heating = self.rezistans_aktif and self.virtual_heater_on

        # Sayaç Sinyali
        if not current_takoz_vals:
             min_takoz = avg_ortam
        else:
             min_takoz = min(current_takoz_vals)
             
        target_hit = (min_takoz >= desired_temp)

        # 4. ORTAM FİZİĞİ
        noise_at = random.uniform(-1.2, 1.2)
        
        if not self.sogutma_modu:
            if effective_heating:
                delta = self.hava_isinma_hizi + noise_at
                self.at_states[0]["val"] += max(0.2, delta)
                self.at_states[1]["val"] += max(0.2, delta + random.uniform(-0.5, 0.5))
            else:
                drop_rate = 0.8 
                self.at_states[0]["val"] -= drop_rate + abs(noise_at * 0.2)
                self.at_states[1]["val"] -= drop_rate + abs(noise_at * 0.2)
        else:
            self.at_states[0]["val"] -= 2.2 + noise_at
            self.at_states[1]["val"] -= 2.2 + noise_at

        # 5. TAKOZ FİZİĞİ (Isı Transferi)
        ort_ortam = (self.at_states[0]["val"] + self.at_states[1]["val"]) / 2
        
        for i in range(13):
            # Her sensör kendi state'ini günceller
            state = self.sensor_states[i]
            noise_t = random.uniform(-0.02, 0.02)
            fark = ort_ortam - state["val"]
            
            if fark > 0:
                # Isınma
                base_iletim = state["iletim"]
                dynamic_iletim = base_iletim * (1.0 + (fark / 100.0))
                
                # Kalıcı Isı Farkı (Strict Thermal Gap) - Kullanıcı İsteği
                if fark < 9.0:
                    # 9 Derece altına inince ISINMA DURUR. Sadece dalgalanma olur.
                    # Bu sayede 9 derece fark korunur.
                    artis = random.uniform(-0.05, 0.05)
                    state["val"] += artis
                elif fark < 12.0:
                    # 12 Derece altına inince çok yavaşlar (%75 azalır)
                    dynamic_iletim *= 0.25 
                    artis = (fark * dynamic_iletim) + noise_t
                    # Zorunlu minimum artışı kaldırıyoruz (max(0.008, ...) YOK)
                    state["val"] += max(0.002, artis) # Çok küçük bir min değer
                else:
                    # Normal Isınma
                    artis = (fark * dynamic_iletim) + noise_t
                    state["val"] += max(0.008, artis)
                
            elif fark < -0.5: 
                # Overshoot engelleme
                state["val"] -= 0.05 
                
            elif self.sogutma_modu:
                # Soğuma
                state["val"] += (fark * state["iletim"] * 0.5)

        return output_values, target_hit

# --- AYARLAR ---
def get_writable_settings_path():
    # Kullanıcının düzenleyebileceği settings.py yolu
    # Eğer exe ise yanındaki, değilse mevcut dizindeki
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, 'settings.py')

settings_path = get_writable_settings_path()

def load_settings_module(path):
    spec = importlib.util.spec_from_file_location("settings", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["settings"] = mod # Add to sys.modules for global access
    return mod

def save_settings_to_file(path, new_values):
    # Dosyayı satır satır oku ve değerleri güncelle
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    with open(path, 'w', encoding='utf-8') as f:
        for line in lines:
            updated = False
            for key, val in new_values.items():
                # Check for lines starting with key = or key=
                if line.strip().startswith(f"{key} =") or line.strip().startswith(f"{key}="):
                    # Format value correctly based on type
                    val_str = "True" if isinstance(val, bool) and val else "False" if isinstance(val, bool) else f"'{val}'" if isinstance(val, str) else str(val)
                    f.write(f"{key} = {val_str}\n")
                    updated = True
                    break
            if not updated:
                f.write(line)

# Initial loading of settings
if not os.path.exists(settings_path):
    # If settings.py doesn't exist, try to copy from a bundled version
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        bundled = os.path.join(base_path, "settings.py")
        if os.path.exists(bundled):
            shutil.copy(bundled, settings_path)
    except Exception as e:
        print(f"Could not copy bundled settings.py: {e}")

try:
    settings = load_settings_module(settings_path)
except Exception as e:
    print(f"Error loading settings from {settings_path}: {e}. Using DummySettings.")
    class DummySettings:
        DESIRED_TEMP=56; DESIRED_SECONDS=60; DESIRED_SUCCESS_COUNT=35
        RESISTANCE_MAX=90.0; RESISTANCE_MIN=80.0; DESIRED_ENGINE_MUNITE=1; ENGINE_RESTING_MUNITE=1
        PRINTER_NAME="PDF"; FIRM_NAME="GEBZE TEST"; OVEN_NO="1"; VALITADITON=False
        fan_right_pin=20; fan_left_pin=24; resistance_pin=16; alert_red_pin=3; alert_green_pin=24; IP='0.0.0.0'
        sensor1=True; sensor2=True; sensor3=True; sensor4=True; sensor5=True
        sensor6=True; sensor7=True; sensor8=True; sensor9=True; sensor10=True
        sensor11=True; sensor12=True; sensor13=True; sensor14=True; sensor15=True
        # Add new settings with default values for DummySettings
        RESISTANCE_WORK_MIN=1
        RESISTANCE_REST_MIN=1
    settings = DummySettings()


# --- DATABASE ---
def get_db():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return sqlite3.connect(os.path.join(base_path, "mainDb.sqlite"))
def insert_report(id, firm_id, start_time, end_time, type, m3, pieces, info):
    c = get_db(); c.execute("INSERT INTO REPORT(ID,FIRM_ID,START_TIME,END_TIME,TYPE,M3,PIECES,REPORT_INFO) VALUES (?,?,?,?,?,?,?,?)", (id, firm_id, start_time, end_time, type, m3, pieces, info)); c.commit(); c.close()
def insert_report_step(rid, *args):
    c = get_db(); c.execute("INSERT INTO Report_Details VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, *args)); c.commit(); c.close()
def update_report(id, type, m3, pieces, info):
    c = get_db(); c.execute("UPDATE REPORT SET M3=?, TYPE=?, PIECES=?, REPORT_INFO=? WHERE id=?", (m3, type, pieces, info, id)); c.commit(); c.close()
def set_report_end_time(rid):
    c = get_db(); cur = c.cursor(); cur.execute(f"SELECT STEPTIME FROM Report_Details WHERE REPORT_ID={rid} ORDER BY ID DESC LIMIT 1"); res = cur.fetchone()
    if res: c.execute("UPDATE REPORT SET END_TIME=? WHERE id=?", (res[0], rid)); c.commit(); c.close()
def get_report():
    c = get_db(); cur = c.cursor(); cur.execute('SELECT ID, START_TIME, END_TIME, TYPE, M3, PIECES, REPORT_INFO FROM REPORT WHERE END_TIME <> "IP"'); d = cur.fetchall(); c.close(); return d
def get_report_details(id):
    c = get_db(); cur = c.cursor(); cur.execute(f'SELECT T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11,T12,T13,AT1,AT2,STEPNO,STEPTIME FROM Report_Details WHERE REPORT_ID={id}'); d = cur.fetchall(); c.close(); return d
def get_parti(id):
    c = get_db(); cur = c.cursor(); cur.execute(f'SELECT ID,START_TIME,END_TIME,TYPE,M3,PIECES,REPORT_INFO FROM REPORT WHERE id={id}'); d = cur.fetchall(); c.close(); return d
def report_index():
    c = get_db(); cur = c.cursor(); cur.execute('SELECT ID FROM REPORT ORDER BY ID DESC LIMIT 1'); d = cur.fetchone(); c.close(); return str(d[0]) if d else "0"
def get_incomplete_reports():
    c = get_db(); cur = c.cursor(); cur.execute('SELECT ID FROM report WHERE end_time="IP"'); d = cur.fetchall(); c.close(); return [x[0] for x in d]
def cleanup_db(rid):
    c = get_db(); c.execute(f"DELETE FROM Report_Details WHERE REPORT_ID={rid}"); c.execute(f"DELETE FROM report WHERE ID={rid}"); c.commit(); c.close()
def delete_report_steps(rid):
    c = get_db(); c.execute("DELETE FROM Report_Details WHERE REPORT_ID = ?", (rid,)); c.commit(); c.close()
def delete_report(rid):
    c = get_db(); c.execute("DELETE FROM report WHERE ID = ?", (rid,)); c.commit(); c.close()
def reset_autoincrement(table):
    c = get_db(); cur = c.cursor(); cur.execute(f"SELECT MAX(ID) FROM {table}"); mid = cur.fetchone()[0]
    if mid is None: mid=0; c.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
    else: c.execute("UPDATE sqlite_sequence SET seq=? WHERE name=?", (mid, table))
    c.commit(); c.close()

from reportlab.lib.units import inch

# --- UI SINIFLARI ---
class ReportOperations:
    def __init__(self):
        self.ui = Ui_Report_Dialog(); self.detail_op = ReportDetailOperations()
        self.sel_row = 0
    def openReportScreen(self):
        self.popup = QDialog(); self.ui.setupUi(self.popup)
        self.load_data(); self.ui.Report_tableWidget.cellClicked.connect(self.click)
        self.ui.btn_report_update.clicked.connect(self.update); self.ui.btn_report_detail.clicked.connect(self.detail)
        self.popup.exec_()
    def load_data(self):
        d = get_report(); self.ui.Report_tableWidget.setRowCount(len(d))
        for r, row in enumerate(d):
            for c, val in enumerate(row): self.ui.Report_tableWidget.setItem(r, c, QTableWidgetItem(str(val)))
    def click(self, r, c):
        self.sel_row = r; d = [self.ui.Report_tableWidget.item(r, i).text() for i in range(7)]
        self.ui.lineEdit_report_type.setText(d[3]); self.ui.lineEdit_report_amount.setText(d[4])
        self.ui.lineEdit_report_pieces.setText(d[5]); self.ui.lineEdit_report_info.setText(d[6])
    def update(self):
        rid = self.ui.Report_tableWidget.item(self.sel_row, 0).text()
        update_report(rid, self.ui.lineEdit_report_type.text(), self.ui.lineEdit_report_amount.text(), self.ui.lineEdit_report_pieces.text(), self.ui.lineEdit_report_info.text())
        self.load_data()
    def detail(self):
        rid = self.ui.Report_tableWidget.item(self.sel_row, 0).text()
        self.detail_op.open(rid)

class ReportDetailOperations:
    def __init__(self):
        self.ui = Ui_Report_Details_Dialog()
        self.id = 1

    def openReportScreen(self, id):
        self.id = id
        self.popup = QDialog()
        self.ui.setupUi(self.popup)
        self.load_data_to_table_colored(id)
        self.load_headers(id)
        self.ui.btn_graph.clicked.connect(self.showgraphdetail)
        self.ui.btn_export.clicked.connect(lambda: self.export_pdf())
        self.popup.exec_()

    # Alias for compatibility if needed, but openReportScreen is better
    def open(self, rid):
        self.openReportScreen(rid)

    def load_data_to_table_colored(self, id):
        db_data = get_report_details(id)
        self.ui.report_detail_tableWidget.setRowCount(len(db_data))
        desired_temp = settings.DESIRED_TEMP
        for row, data in enumerate(db_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(str(value))
                self.ui.report_detail_tableWidget.setItem(row, col, item)
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
        self.ui.txt_report_no.setText(txt_report_no)
        self.ui.txt_start_time.setText(txt_start_time)
        self.ui.txt_end_time.setText(txt_end_time)
        self.ui.txt_type.setText(txt_type)
        self.ui.txt_amount.setText(txt_amount)
        self.ui.txt_pieces.setText(txt_pieces)
        self.ui.txt_report_info.setText(txt_report_info)

    def showgraphdetail(self):
        print("Grafik gösteriliyor, id:", self.id)
        dialog = MatplotlibDialog()
        dialog.update_graph_minimiz(self.id)
        dialog.exec_()
        
    def export_pdf(self):
        print("Export butonuna basıldı.")
        try:
            # Prioritize Radio Buttons
            if self.ui.radio_One.isChecked():
                print("Mod: 1 Dakika")
                self.export_munite_pdf(1)
            elif self.ui.radio_Three.isChecked():
                print("Mod: 3 Dakika")
                self.export_munite_pdf(3)
            elif self.ui.radio_Four.isChecked():
                print("Mod: 4 Dakika")
                self.export_munite_pdf(4)
            elif self.ui.radio_Five.isChecked():
                print("Mod: 5 Dakika")
                self.export_munite_pdf(5)
            elif settings.VALITADITON:
                print("Mod: Validation (Fallback)")
                self.export_to_pdf_colored(0)
            else:
                print("Hata: Hiçbir mod seçili değil, varsayılan 3 dk çalıştırılıyor.")
                self.export_munite_pdf(3)
        except Exception as e:
            print(f"EXPORT HATASI: {e}")
            import traceback
            traceback.print_exc()
    
    def get_desktop_path(self):
        if os.name == 'nt': # Windows
            home_dir = os.path.expanduser("~")
            desktop_path = os.path.join(home_dir, 'Desktop', 'ISPM-RAPOR')
        else: # Linux / Raspberry Pi
            real_user = os.getenv('SUDO_USER') or os.getenv('USER')
            
            # Handle pkexec
            if os.getenv('PKEXEC_UID'):
                import pwd
                try:
                    uid = int(os.getenv('PKEXEC_UID'))
                    real_user = pwd.getpwuid(uid).pw_name
                except:
                    pass
            
            if real_user and real_user != 'root':
                desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'ISPM-RAPOR')
            else:
                # Fallback if we can't determine user or if it is root
                # Try to find a non-root user in /home
                try:
                    possible_users = [u for u in os.listdir('/home') if os.path.isdir(os.path.join('/home', u))]
                    if possible_users:
                        desktop_path = os.path.join(f'/home/{possible_users[0]}', 'Desktop', 'ISPM-RAPOR')
                    else:
                        desktop_path = '/root/Desktop/ISPM-RAPOR'
                except:
                     desktop_path = '/root/Desktop/ISPM-RAPOR'

        if not os.path.exists(desktop_path):
            try:
                os.makedirs(desktop_path)
                # If we created it as root, try to give ownership to the user
                if os.name != 'nt' and real_user and real_user != 'root':
                     import pwd
                     try:
                         uid = pwd.getpwnam(real_user).pw_uid
                         gid = pwd.getpwnam(real_user).pw_gid
                         os.chown(desktop_path, uid, gid)
                     except:
                         pass
            except OSError as e:
                print(f"Klasör oluşturulamadı: {e}")
                desktop_path = os.path.expanduser("~")
        return desktop_path

    def export_munite_pdf(self, flag, oto=False):
        desktop_path = self.get_desktop_path()
        if oto:
            desktop_path = os.path.join(desktop_path, f'parti{self.id}')
            if not os.path.exists(desktop_path): os.makedirs(desktop_path)
        
        # Font path handling
        if hasattr(sys, '_MEIPASS'):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        # Check if font exists, otherwise use Helvetica
        font_path = os.path.join(application_path, "DejaVuSans.ttf")
        if not os.path.exists(font_path):
             font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" # Common Linux path
        
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            font_name = 'DejaVuSans'
        else:
            font_name = 'Helvetica'

        file_name = os.path.join(desktop_path, f"parti_{self.id}_{flag}Dakika.pdf")
        data = get_parti(str(self.id))
        report_details = get_report_details(str(self.id))
        doc = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 8
        styles["Normal"].leading = 11
        styles["Normal"].fontName = font_name
        styles["Normal"].encoding = 'utf-8'
        hstyles = getSampleStyleSheet()
        hstyles["Title"].fontSize = 16
        hstyles["Title"].leading = 11
        hstyles["Title"].fontName = font_name
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
            if os.name != 'nt':
                try:
                    subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])
                except Exception as e:
                    print(f"Yazıcı Hatası: {e}")
            else:
                print("Windows üzerinde doğrudan yazdırma desteklenmiyor (lp komutu yok).")

    def export_to_pdf_colored(self, flag, oto=False):
        desktop_path = self.get_desktop_path()
        if oto:
            desktop_path = os.path.join(desktop_path, f'parti{self.id}')
            if not os.path.exists(desktop_path): os.makedirs(desktop_path)

        if hasattr(sys, '_MEIPASS'):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
            
        font_path = os.path.join(application_path, "DejaVuSans.ttf")
        if not os.path.exists(font_path):
             font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            font_name = 'DejaVuSans'
        else:
            font_name = 'Helvetica'
            
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
        styles["Normal"].fontName = font_name
        styles["Normal"].encoding = 'utf-8'
        hstyles = getSampleStyleSheet()
        hstyles["Title"].fontSize = 16
        hstyles["Title"].leading = 11
        hstyles["Title"].fontName = font_name
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
            if os.name != 'nt':
                try:
                    subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])
                except Exception as e:
                    print(f"Yazıcı Hatası: {e}")
            else:
                print("Windows üzerinde doğrudan yazdırma desteklenmiyor (lp komutu yok).")

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

    def save_graph_Ten(self, id):        
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(__file__)
        db_path = os.path.join(base_path, "mainDb.sqlite")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, AT1, AT2, STEPTIME FROM Report_Details WHERE REPORT_ID=' + str(id) + ' LIMIT 10')
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

class AdminPanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yönetici Paneli - Röle Ayarları")
        self.resize(400, 300)
        layout = QVBoxLayout(self)
        
        # Fan Ayarları
        layout.addWidget(QLabel("--- FAN KONTROLÜ (Pin 20) ---"))
        self.inp_fan_work = self.create_input("Çalışma Süresi (Dk):", settings.DESIRED_ENGINE_MUNITE)
        layout.addLayout(self.inp_fan_work[0])
        self.inp_fan_rest = self.create_input("Bekleme Süresi (Dk):", settings.ENGINE_RESTING_MUNITE)
        layout.addLayout(self.inp_fan_rest[0])
        
        layout.addWidget(QLabel("")) # Boşluk
        
        # Rezistans Ayarları
        layout.addWidget(QLabel("--- REZİSTANS KONTROLÜ (Pin 16) ---"))
        self.inp_rez_work = self.create_input("Çalışma Süresi (Dk):", getattr(settings, 'RESISTANCE_WORK_MIN', 1))
        layout.addLayout(self.inp_rez_work[0])
        self.inp_rez_rest = self.create_input("Bekleme Süresi (Dk):", getattr(settings, 'RESISTANCE_REST_MIN', 1))
        layout.addLayout(self.inp_rez_rest[0])
        
        # Kaydet Butonu
        btn_save = QPushButton("Kaydet")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        
    def create_input(self, label_text, default_val):
        layout = QHBoxLayout()
        lbl = QLabel(label_text)
        inp = QSpinBox()
        inp.setRange(1, 999)
        inp.setValue(int(default_val))
        layout.addWidget(lbl)
        layout.addWidget(inp)
        return layout, inp
        
    def save_settings(self):
        # Ayarları güncelle
        new_settings_dict = {
            "DESIRED_ENGINE_MUNITE": self.inp_fan_work[1].value(),
            "ENGINE_RESTING_MUNITE": self.inp_fan_rest[1].value(),
            "RESISTANCE_WORK_MIN": self.inp_rez_work[1].value(),
            "RESISTANCE_REST_MIN": self.inp_rez_rest[1].value()
        }
        save_settings_to_file(settings_path, new_settings_dict)
        global settings; settings = load_settings_module(settings_path) # Reload immediately
        QMessageBox.information(self, "Bilgi", "Ayarlar güncellendi!")
        self.close()

# --- VERİ THREAD ---
class DataUpdateThread(QtCore.QThread):
    data_updated = QtCore.pyqtSignal(str, *[str]*16)
    finished = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        # Ayarları Yükle
        global settings; settings = load_settings_module(get_writable_settings_path())
        self.sim = ISPM15Simulator()
        self.counter = 0
        self.target_count = settings.DESIRED_SUCCESS_COUNT
        self.sim = ISPM15Simulator()
        self.counter = 0
        self.target_count = settings.DESIRED_SUCCESS_COUNT
        self.target_temp = settings.DESIRED_TEMP
        self.turbo = False # Turbo Modu Flag'i

    def run(self):
        self.stop_event = threading.Event(); self.pause_event = threading.Event()
        
        # GPIO Kurulumu
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(settings.resistance_pin, GPIO.OUT, initial=GPIO.HIGH) # Rezistans (Pin 13)
        GPIO.setup(settings.fan_right_pin, GPIO.OUT, initial=GPIO.HIGH)  # Fan (Pin 24)
        
        dt_first_time = datetime.datetime.now() - datetime.timedelta(seconds=settings.DESIRED_SECONDS)
        
        # RÖLE ZAMANLAYICILARI
        fan_state = False # False: Kapalı, True: Açık
        rez_state = False
        
        fan_timer = time.time()
        rez_timer = time.time()
        
        # Başlangıç durumu (İkisi de çalışsın mı? İsteğe bağlı, şimdilik bekleme modunda başlasınlar)
        # Veya direkt çalışmaya başlasınlar:
        fan_state = True; GPIO.output(settings.fan_right_pin, GPIO.LOW) # Aktif (Low)
        rez_state = True; GPIO.output(settings.resistance_pin, GPIO.LOW) # Aktif (Low)
        self.sim.rezistans_aktif = True

        while self.counter < self.target_count and not self.stop_event.is_set():
            if self.pause_event.is_set():
                while self.pause_event.is_set(): time.sleep(0.5)
            
            # Maske
            mask = [
                settings.sensor1, settings.sensor2, settings.sensor3, settings.sensor4, settings.sensor5,
                settings.sensor6, settings.sensor7, settings.sensor8, settings.sensor9, settings.sensor10,
                settings.sensor11, settings.sensor12, settings.sensor13, settings.sensor14, settings.sensor15
            ]
            
            # --- RÖLE KONTROLÜ (Zaman Bazlı) ---
            current_time = time.time()
            
            # 1. FAN KONTROLÜ
            fan_duration = (settings.DESIRED_ENGINE_MUNITE * 60) if fan_state else (settings.ENGINE_RESTING_MUNITE * 60)
            # print(f"Fan Timer: {current_time - fan_timer:.1f} / {fan_duration} (State: {fan_state})") # Debug
            if (current_time - fan_timer) >= fan_duration:
                # Durum değiştir
                fan_state = not fan_state
                fan_timer = current_time
                # GPIO Güncelle (Active Low varsayımı: LOW=Açık, HIGH=Kapalı)
                GPIO.output(settings.fan_right_pin, GPIO.LOW if fan_state else GPIO.HIGH)
                print(f"FAN Durumu Değişti: {'AÇIK' if fan_state else 'KAPALI'} (Pin {settings.fan_right_pin})")

            # 2. REZİSTANS KONTROLÜ
            rez_work = getattr(settings, 'RESISTANCE_WORK_MIN', 1)
            rez_rest = getattr(settings, 'RESISTANCE_REST_MIN', 1)
            rez_duration = (rez_work * 60) if rez_state else (rez_rest * 60)
            # print(f"Rez Timer: {current_time - rez_timer:.1f} / {rez_duration} (State: {rez_state})") # Debug
            
            if (current_time - rez_timer) >= rez_duration:
                # Durum değiştir
                rez_state = not rez_state
                rez_timer = current_time
                # GPIO Güncelle
                GPIO.output(settings.resistance_pin, GPIO.LOW if rez_state else GPIO.HIGH)
                # Simülasyon Fiziğine Bildir
                self.sim.rezistans_aktif = rez_state
                print(f"REZİSTANS Durumu Değişti: {'AÇIK' if rez_state else 'KAPALI'} (Pin {settings.resistance_pin})")

            # 3. SİMÜLASYON ADIMI
            # Not: calculate_step içindeki termostat mantığı artık rezistans_aktif'i değiştirmemeli
            # Ancak calculate_step fonksiyonu rezistans_aktif'i override edebilir.
            # Bu yüzden calculate_step'e dokunmadan önce, simülasyon sınıfında termostatı devre dışı bırakmalıyız
            # Veya calculate_step her çağrıldığında rezistans_aktif'i tekrar set etmeliyiz.
            # En garantisi: calculate_step sonucunda rezistans_aktif değişse bile, biz burada override edelim.
            # Ama calculate_step hesaplamayı rezistans_aktif'e göre yapıyor.
            # Yani calculate_step çağırmadan önce set etmemiz yeterli.
            
            self.sim.rezistans_aktif = rez_state # Zorla set et
            
            vals, target_hit = self.sim.calculate_step(mask, self.target_temp)
            
            # Termostatın rezistansı kapatmasını engellemek için (Eğer calculate_step içinde kapatıyorsa)
            # calculate_step içinde "self.rezistans_aktif = False" yapıyorsa, bir sonraki adımda düzelir.
            # Ancak o anki ısıtma/soğutma hesabı o flag'e göre yapılıyor.
            # Bu yüzden calculate_step içindeki termostat mantığını bypass etmek en doğrusu.
            # Şimdilik basit çözüm: calculate_step'i değiştirmeden, her adımda rezistans_aktif'i set ediyoruz.
            # Ancak calculate_step İÇİNDE rezistans_aktif değişirse, o adımın sonucu (ısınma/soğuma) etkilenir.
            # Neyse ki calculate_step'te önce kontrol yapılıyor, sonra fizik hesaplanıyor.
            # Yani biz girmeden set edersek, o içeride değiştirebilir.
            # Bu yüzden calculate_step'i modifiye etmek daha sağlıklı.
            
            if target_hit: self.counter += 1
            else: self.counter = 0
                
            dt_first_time += datetime.timedelta(seconds=settings.DESIRED_SECONDS)
            t_str = dt_first_time.strftime('%Y-%m-%d %H:%M:%S')
            self.data_updated.emit(t_str, *map(str, vals), str(self.counter))
            
            if self.turbo:
                time.sleep(0.001) # Turbo: Bekleme yok
            else:
                time.sleep(settings.DESIRED_SECONDS) # Normal: Gerçek zamanlı bekleme
        
        if not self.stop_event.is_set():
            self.sim.sogutma_modu = True
            # Program bittiğinde röleleri kapat (Active Low: HIGH=Kapalı)
            GPIO.output(settings.fan_right_pin, GPIO.HIGH)
            GPIO.output(settings.resistance_pin, GPIO.HIGH)
            print("Simülasyon Bitti. Röleler Kapatıldı.")
            self.finished.emit()

# --- MAIN ---
class Main(QMainWindow):
    def __init__(self):
        super().__init__(); self.ui = Ui_MainWindow(); self.ui.setupUi(self)
        self.report_ops = ReportOperations()
        self.ui.btn_Start.clicked.connect(self.start_click)
        self.ui.btn_RecipeOpe.clicked.connect(self.settings_click)
        self.ui.btn_ShowReports.clicked.connect(self.report_ops.openReportScreen)
        self.ui.btn_Graph.clicked.connect(self.graph_click)
        self.cleanup_incomplete(); self.red_light(); atexit.register(self.red_light)
        self.key_buffer = [] # Initialize key buffer for global key events
        self.installEventFilter(self) # Install event filter on self

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key_code = event.key()
            print(f"Key pressed: {key_code}") # Instruction 1
            try:
                # Sadece harf tuşlarını al (ASCII range)
                if 32 <= key_code <= 126: # Printable ASCII (Instruction 2)
                    key = chr(key_code).lower()
                    self.key_buffer.append(key)
                    if len(self.key_buffer) > 3:
                        self.key_buffer.pop(0)
                    
                    if self.key_buffer == ['y', 's', 't']:
                        print("Admin Paneli (Global) Açılıyor...")
                        # The parent is 'self' (Main window)
                        dialog = AdminPanel(self)
                        dialog.exec_()
                        self.key_buffer = [] # Sıfırla
                        return True # Olayı tüket
            except Exception as e:
                print(f"Key Filter Error: {e}")
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        # 2. Turbo Mod (T Tuşu)
        if event.key() == QtCore.Qt.Key_T:
            try:
                if hasattr(self, 'thread') and self.thread.isRunning():
                    self.thread.turbo = not self.thread.turbo
                    state = "AÇIK" if self.thread.turbo else "KAPALI"
                    self.setWindowTitle(f"ISPM-15 Simülasyonu - Turbo Mod: {state}")
                    print(f"Turbo Mod: {state}")
            except Exception as e:
                print(f"Turbo hata: {e}") # Instruction 3: The try-except is already there, so the root cause is likely 'self.thread' not existing or not running.

    def open_admin_panel(self):
        dialog = AdminPanel(self)
        dialog.exec_()

    def red_light(self):
        global GPIO
        try:
            GPIO.setmode(GPIO.BCM)
            # Röleleri Kapat (Güvenlik)
            GPIO.setup(settings.fan_right_pin, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.setup(settings.resistance_pin, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.output(settings.fan_right_pin, GPIO.HIGH)
            GPIO.output(settings.resistance_pin, GPIO.HIGH)
            
            # Kırmızı Işık Yak (Opsiyonel, mevcut kodda vardı)
            GPIO.setup(settings.alert_red_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.output(settings.alert_red_pin, GPIO.LOW)
            print("Program Kapatılıyor. Tüm Röleler Pasife Çekildi.")
            
        except RuntimeError as e:
            print(f"GPIO Hatası (red_light): {e}")
            print("Muhtemelen Raspberry Pi 5 veya uyumsuz bir sürüm kullanıyorsunuz.")
            print("MockGPIO moduna geçiliyor...")
            GPIO = MockGPIO() # Fallback to Mock
        except Exception as e:
            print(f"GPIO Genel Hata: {e}")
    def green_light_off(self): GPIO.setmode(GPIO.BCM); GPIO.output(settings.alert_green_pin, GPIO.HIGH)
    def cleanup_incomplete(self):
        for i in get_incomplete_reports(): delete_report_steps(i); delete_report(i)
        reset_autoincrement('report')
    def graph_click(self): d = MatplotlibDialog(); d.draw(report_index()); d.exec_()
    def start_click(self):
        txt = self.ui.btn_Start.text()
        if txt == "Duraklat": self.thread.pause_event.set(); self.ui.btn_Start.setText("Devam")
        elif txt == "Devam": self.thread.pause_event.clear(); self.ui.btn_Start.setText("Duraklat")
        else: self.start_dialog()
    def start_dialog(self): self.dia = QDialog(); u = Ui_Start_Dialog(); u.setupUi(self.dia); u.btn_Start_P.clicked.connect(lambda: self.begin_process(u)); self.dia.exec_()
    def begin_process(self, u):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rid = int(report_index()) + 1
        insert_report(rid, "1", now, "IP", u.txt_type.text(), u.txt_amount.text(), u.txt_pieces.text(), u.txtArea_info.toPlainText())
        self.ui.txt_time.setText(now)
        self.thread = DataUpdateThread(); self.thread.data_updated.connect(self.on_data); self.thread.finished.connect(self.on_finished); self.thread.start()
        self.ui.btn_Start.setText("Duraklat"); self.dia.close()
    def on_data(self, t_str, *args):
        vals = args[:15]; cnt = args[15]; row = self.ui.tableWidget.rowCount(); self.ui.tableWidget.insertRow(row)
        db_vals = []
        for i, v in enumerate(vals):
            fv = float(v); item = QTableWidgetItem(f"{fv:.2f}"); db_vals.append(f"{fv:.2f}")
            if fv >= settings.DESIRED_TEMP and fv > 0.1: item.setBackground(QColor(0,255,0))
            self.ui.tableWidget.setItem(row, i, item)
            box = getattr(self.ui, f"txt_prob_status_{i+1}" if i > 0 else "txt_prob_status", None)
            if box: box.setText(f"{fv:.2f}")
        rem = settings.DESIRED_SUCCESS_COUNT - int(cnt)
        self.ui.txt_step.setText(str(rem)); self.ui.tableWidget.setItem(row, 15, QTableWidgetItem(str(rem))); self.ui.tableWidget.setItem(row, 16, QTableWidgetItem(t_str)); self.ui.tableWidget.scrollToBottom()
        insert_report_step(report_index(), *db_vals, "0", "0", t_str, rem)
    def on_finished(self):
        self.ui.btn_Start.setText("Başlat"); rid = report_index(); set_report_end_time(rid)
        QMessageBox.information(self, "Bitti", f"İşlem tamamlandı.\nRapor No: {rid}")
    def settings_click(self):
        d = QDialog(); u = Ui_Ui_Settings_Dialog(); u.setupUi(d)
        u.line_Ekds.setText(str(settings.DESIRED_TEMP))
        u.line_DSC.setText(str(settings.DESIRED_SUCCESS_COUNT))
        u.line_FIRM.setText(str(settings.FIRM_NAME))
        
        # Resistance Max/Min Load
        u.line_Resistance_Max.setText(str(settings.RESISTANCE_MAX))
        u.line_Resistance_Min.setText(str(settings.RESISTANCE_MIN))

        chk_list = [u.sensor_1, u.sensor_2, u.sensor_3, u.sensor_4, u.sensor_5, u.sensor_6, u.sensor_7, u.sensor_8, u.sensor_9, u.sensor_10, u.sensor_11, u.sensor_12, u.sensor_13, u.sensor_14, u.sensor_15]
        set_attr = ["sensor1", "sensor2", "sensor3", "sensor4", "sensor5", "sensor6", "sensor7", "sensor8", "sensor9", "sensor10", "sensor11", "sensor12", "sensor13", "sensor14", "sensor15"]
        for chk, attr in zip(chk_list, set_attr): chk.setChecked(getattr(settings, attr))
        
        def save():
            try:
                new_set = {
                    "DESIRED_TEMP": float(u.line_Ekds.text()),
                    "DESIRED_SUCCESS_COUNT": int(u.line_DSC.text()),
                    "FIRM_NAME": u.line_FIRM.text(),
                    "RESISTANCE_MAX": float(u.line_Resistance_Max.text()),
                    "RESISTANCE_MIN": float(u.line_Resistance_Min.text())
                }
                for chk, attr in zip(chk_list, set_attr): new_set[attr] = chk.isChecked()
                
                save_settings_to_file(settings_path, new_set)
                global settings; settings = load_settings_module(settings_path) # Reload immediately
                d.close()
                QMessageBox.information(self, "Bilgi", "Ayarlar kaydedildi.")
            except ValueError:
                QMessageBox.warning(self, "Hata", "Lütfen sayısal değerleri doğru giriniz.")
                
        u.btn_SettingsSave.clicked.connect(save); d.exec_()

class GlobalKeyFilter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.key_buffer = []

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            try:
                key_code = event.key()
                # Sadece harf tuşlarını al (ASCII range)
                if 32 <= key_code <= 126:
                    key = chr(key_code).lower()
                    self.key_buffer.append(key)
                    if len(self.key_buffer) > 3:
                        self.key_buffer.pop(0)
                    
                    if self.key_buffer == ['y', 's', 't']:
                        print("Admin Paneli (Global) Açılıyor...")
                        parent = QtWidgets.QApplication.activeWindow()
                        # AdminPanel sınıfı yukarıda tanımlı
                        if parent:
                            dialog = AdminPanel(parent)
                        else:
                            dialog = AdminPanel()
                        dialog.exec_()
                        self.key_buffer = []
                        return True # Olayı tüket
            except Exception as e:
                print(f"Key Filter Error: {e}")
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Global Key Filter Kurulumu
    key_filter = GlobalKeyFilter()
    app.installEventFilter(key_filter)
    
    if os.path.exists("/usr/share/pixmaps/ars-ispmi5.png"): app.setWindowIcon(QtGui.QIcon("/usr/share/pixmaps/ars-ispmi5.png"))
    w = Main(); w.show(); sys.exit(app.exec_())