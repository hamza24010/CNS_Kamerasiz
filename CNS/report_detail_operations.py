from PyQt5.QtWidgets import QDialog, QTableWidgetItem
from PyQt5.QtGui import QColor
from Report_Detail_Dialog import Ui_Report_Details_Dialog
from sql_operation import get_report_details, get_parti
from graph_dialog import MatplotlibDialog
import settings
import os
import sys
import glob
import subprocess
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
        print("Export butonuna basıldı.")
        try:
            if settings.VALITADITON:
                print("Mod: Validation")
                self.export_to_pdf_colored(0)
            elif self.ui_report_detail_dialog.radio_Three.isChecked():
                print("Mod: 3 Dakika")
                self.export_munite_pdf(3)
            elif self.ui_report_detail_dialog.radio_Four.isChecked():
                print("Mod: 4 Dakika")
                self.export_munite_pdf(4)
            elif self.ui_report_detail_dialog.radio_Five.isChecked():
                print("Mod: 5 Dakika")
                self.export_munite_pdf(5)
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
            subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])

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
            subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])
