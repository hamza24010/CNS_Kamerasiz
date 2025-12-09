from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import *
from Report_Detail_Dialog import Ui_Report_Details_Dialog
from sql_operation import get_report_details,get_parti
from graph_dialog import MatplotlibDialog
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.platypus.flowables import PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer
from reportlab.pdfgen import canvas
from reportlab.platypus import Image
from reportlab.lib import colors
import settings
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QTableWidgetItem
import os
import subprocess
import settings
import shutil

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
        self.ui_report_detail_dialog.btn_export.clicked.connect(lambda: self.export_to_pdf_colored(0))  # 0 değeri gönderiliyor
        self.ui_report_detail_dialog.btn_printer.clicked.connect(lambda: self.export_to_pdf_colored(1))  # 1 değeri gönderiliyor

        self.popup.exec_()

    # Rapor Detayını renkli yapan yer
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
                        if temperature >= desired_temp and temperature!=404.0:
                            item.setBackground(QColor('green'))
                    except ValueError:
                        pass

    def load_headers(self, id):
        self.id = id
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
        print("Grafiği Gösterdim")
        print("grafik id:", self.id)
        self.dialog = MatplotlibDialog()
        self.dialog.update_graph_minimiz(self.id)
        self.dialog.exec_()

    def export_to_pdf_colored(self, flag):

        real_user = os.getenv('SUDO_USER') or os.getenv('USER')

        desktop_path = os.path.join(f'/home/{real_user}', 'Desktop', 'ISPM-RAPOR')

        #desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'ISPM-RAPOR')
        file_name = os.path.join(desktop_path, "parti_" + str(self.id) + ".pdf")
        data = get_parti(str(self.id))
        report_details = get_report_details(str(self.id))

        doc = SimpleDocTemplate(file_name, pagesize=A4)
        styles = getSampleStyleSheet()
        styles["Normal"].fontSize = 8
        styles["Normal"].leading = 11
        hstyles = getSampleStyleSheet()
        hstyles["Title"].fontSize = 16
        hstyles["Title"].leading = 11

        story = []
        header = "<b>RAPOR</b>"
        headerr = Paragraph(header, hstyles["Title"])
        story.append(headerr)
        story.append(Spacer(1, 0.2 * inch))

        for row in data:
            text = f"<b>Parti No:</b> {row[0]}\n <br/> <b>Baslangic Zamani:</b> {row[1]}\n<b>Bitis Zamani:</b> {row[2]}\n <br/> <b>Ürün Tipi: </b>{row[3]}\n<b>M3:</b> {row[4]}\n<b>Adet:</b> {row[5]}\n <br/> <b>Aciklama:</b>{row[6]}\n"
            paragraph = Paragraph(text, styles["Normal"], encoding='utf-8')
            story.append(paragraph)
            story.append(Spacer(1, 0.2 * inch))

        table_data = [tuple(["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11", "T12", "T13", "AT1", "AT2", "K.Adim", "Zaman"])]
        for row in report_details:
            table_data.append(row)

        column_widths = [28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 36, 100]
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
#ayar
        for row_index in range(1, num_rows):
            for col_index in range(num_cols):
                cell_value = table_data[row_index][col_index]
                try:
                    if col_index < 15 and cell_value != "404.0" and float(cell_value) >= settings.DESIRED_TEMP and float(cell_value) !=404.0:
                        table_style.add('BACKGROUND', (col_index, row_index), (col_index, row_index), colors.green)
                except ValueError:
                    pass

        table.setStyle(table_style)
        story.append(table)
        story.append(Spacer(1, 0.2 * inch))
        story.append(PageBreak())

        png_file = MatplotlibDialog().save_filtered_graph_png(self.id)
        if png_file:
            image = Image(png_file)
            image.drawWidth = 439
            image.drawHeight = 685
            story.append(image)

        doc.build(story)

        if flag == 1:
            subprocess.run(["lp", "-d", settings.PRINTER_NAME, file_name])


        #usb_base_path = os.path.join(os.path.expanduser('~'), 'media')
        #usb_path = os.path.join(usb_base_path, 'KKERESTE')  # USB sürücüsünün doğru yolu
        #destination = os.path.join("/media/tunay/KKERESTE", "parti_" + str(self.id) + ".pdf")

        #try:
        #    shutil.copy(file_name, destination)
        #    print(f"{file_name} USB sürücüsüne kopyalandı: {destination}")
        #except Exception as e:
        #    print(f"Dosya kopyalanırken bir hata oluştu: {e}")
    
       







    
