
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import *
from Report_Dialog import Ui_Report_Dialog
from report_detail_operations import ReportDetailOperations
from sql_operation import insert_firm, delete_firm, update_report, get_report
import settings
from PyQt5.QtGui import QBrush, QColor

class ReportOperations:
    def __init__(self):
        
        self.ui_report_dialog = Ui_Report_Dialog()
        self.report_detail_operations=ReportDetailOperations()
        self.selected_row=0

    def openReportScreen(self):
            self.popup = QDialog()
            self.ui_report_dialog.setupUi(self.popup)
            self.load_data_to_table()
            self.ui_report_dialog.Report_tableWidget.cellClicked.connect(self.on_table_cell_clicked)
        
            self.ui_report_dialog.btn_report_update.clicked.connect(self.update_selected_row)
            self.ui_report_dialog.btn_report_clear.clicked.connect(self.clear_report_screen)
            self.ui_report_dialog.btn_report_detail.clicked.connect(self.showreportdetail) #report_detail_operations
            

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
            column_count = self.ui_report_dialog.Report_tableWidget.columnCount()
            for col in range(column_count):
                cell_item = self.ui_report_dialog.Report_tableWidget.item(selected_row, col)
                if cell_item is not None:
                    cell_data = cell_item.text()
                    row_data.append(cell_data)

        info=self.ui_report_dialog.lineEdit_report_info.text()
        type=self.ui_report_dialog.lineEdit_report_type.text()
        m3=self.ui_report_dialog.lineEdit_report_amount.text()
        pieces=self.ui_report_dialog.lineEdit_report_pieces.text()

        update_report(row_data[0],type,m3,pieces,info)
        self.clear_report_screen()
        self.load_data_to_table()

    def on_table_cell_clicked(self, row, col):
        self.selected_row = row
        self.selected_column = col

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
        print("rx")
        self.report_detail_operations.openReportScreen(cell_data[0])


            
        

       
