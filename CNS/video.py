import sys
import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QMessageBox, QSizePolicy
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
import datetime

# Kamera kayıt ve preview boyutları
RECORD_WIDTH, RECORD_HEIGHT = 1920, 1080
PREVIEW_WIDTH, PREVIEW_HEIGHT = 640, 480


def draw_timestamp(frame, font_scale=1.5, thickness=2, margin=10):
    """
    Verilen frame'in sağ-alt köşesine tarih-saat damgası ekler.
    """
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Metin boyutu ve baseline
    (tw, th), baseline = cv2.getTextSize(ts, font, font_scale, thickness)
    # Sağ-alt köşe
    x = frame.shape[1] - tw - margin
    y = frame.shape[0] - margin
    # Arka plan kutusu
    cv2.rectangle(
        frame,
        (x - margin, y - th - margin),
        (x + tw + margin, y + baseline + margin),
        (0, 0, 0),
        cv2.FILLED
    )
    # Yazıyı bastır (anti-aliasing)
    cv2.putText(
        frame, ts, (x, y), font,
        font_scale, (255, 255, 255), thickness,
        lineType=cv2.LINE_AA
    )
    return frame


class VideoWorker(QThread):
    """
    Video kaydı için ayrı thread.
    """
    finished = pyqtSignal()

    def __init__(self, rtsp_url, parti_no, idx, output_dir, duration=10.0):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.parti_no = parti_no
        self.idx = idx
        self.output_dir = output_dir
        self.duration = duration

    def run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, RECORD_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RECORD_HEIGHT)

        fps = 20.0
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_path = os.path.join(
            self.output_dir,
            f"parti{self.parti_no}_islem{self.idx}_video.mp4"
        )
        writer = cv2.VideoWriter(video_path, fourcc, fps,
                                 (RECORD_WIDTH, RECORD_HEIGHT))

        max_frames = int(self.duration * fps)
        last_frame = np.zeros((RECORD_HEIGHT, RECORD_WIDTH, 3), dtype=np.uint8)

        for _ in range(max_frames):
            ret, frame = cap.read()
            if ret and frame is not None:
                frame = cv2.resize(frame, (RECORD_WIDTH, RECORD_HEIGHT))
                frame = draw_timestamp(frame)
                last_frame = frame.copy()
            else:
                frame = last_frame
            writer.write(frame)

        writer.release()
        cap.release()
        self.finished.emit()


class KameraVibe(QWidget):
    process_completed = pyqtSignal(int)

    def __init__(self, rtsp_url, parti_no):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.parti_no = parti_no
        self.process_idx = 1

        # Çıktı klasörü oluşturma
        # Çıktı klasörü oluşturma
        user = os.getenv('SUDO_USER') or os.getenv('USER')
        
        # Handle pkexec
        if os.getenv('PKEXEC_UID'):
            import pwd
            try:
                uid = int(os.getenv('PKEXEC_UID'))
                user = pwd.getpwuid(uid).pw_name
            except:
                pass
        
        if not user or user == 'root':
             # Fallback
             try:
                possible_users = [u for u in os.listdir('/home') if os.path.isdir(os.path.join('/home', u))]
                if possible_users:
                    user = possible_users[0]
             except:
                pass

        base = f"/home/{user}/Desktop/RAPOR"
        self.output_dir = os.path.join(base, f"parti{self.parti_no}")
        os.makedirs(self.output_dir, exist_ok=True)

        # Pencere ayarları
        self.setWindowTitle("Kayıt")
        self.setGeometry(200, 200, PREVIEW_WIDTH, PREVIEW_HEIGHT + 100)

        # Video preview label
        self.video_label = QLabel(self)
        self.video_label.setFixedSize(PREVIEW_WIDTH, PREVIEW_HEIGHT)

        # Başlat butonu
        self.button = QPushButton("Fırın boş durumda 1. Video Kaydını Başlat")
        btn_font = self.button.font()
        btn_font.setPointSize(14)
        btn_font.setBold(True)
        self.button.setFont(btn_font)
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.button.setStyleSheet(
            "QPushButton { padding: 12px 24px; } QPushButton:focus { outline: none; }"
        )
        self.button.clicked.connect(self.start_process)

        layout = QVBoxLayout(self)
        layout.addWidget(self.video_label)
        layout.addWidget(self.button)

        # Preview capture
        self.preview_cap = cv2.VideoCapture(self.rtsp_url)
        self.preview_cap.set(cv2.CAP_PROP_FRAME_WIDTH, RECORD_WIDTH)
        self.preview_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RECORD_HEIGHT)

        # Timer ile preview güncelleme
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview)
        self.timer.start(30)


    def update_preview(self):
        ret, frame = self.preview_cap.read()
        if ret and frame is not None:
            frame = cv2.resize(frame, (PREVIEW_WIDTH, PREVIEW_HEIGHT))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            self.video_label.setPixmap(QPixmap.fromImage(img))

    def start_process(self):
        # Fotoğraf çek
        ret, frame = self.preview_cap.read()
        if not ret or frame is None:
            QMessageBox.critical(self, "Hata", "Kameradan görüntü alınamadı!")
            return

        frame_resized = cv2.resize(frame, (RECORD_WIDTH, RECORD_HEIGHT))
        frame_ts = draw_timestamp(frame_resized.copy())
        photo_file = os.path.join(
            self.output_dir,
            f"parti{self.parti_no}_islem{self.process_idx}_foto.jpg"
        )
        cv2.imwrite(photo_file, frame_ts)
        print(f"{photo_file} kaydedildi.")

        # Video kaydı
        self.button.setEnabled(False)
        self.worker = VideoWorker(
            self.rtsp_url,
            self.parti_no,
            self.process_idx,
            self.output_dir,
            duration=10.0
        )
        self.worker.finished.connect(self._on_worker_done)
        self.worker.start()

    def _on_worker_done(self):
        if self.process_idx == 1:
            QMessageBox.information(
                self, "Bilgi", "Fırını doldurun ve 2. Video kaydını başlatın."
            )
            self.process_idx = 2
            self.button.setText("Fırın dolduruldu. 2. Kaydı Başlat")
            self.button.setEnabled(True)
        elif self.process_idx==2:
            QMessageBox.information(
                self, "Bilgi", "2. Kayıt tamamlandı. Ölçüm Başlatılıyor."
            )
            
            self.process_completed.emit(self.process_idx)
            self.button.setEnabled(False)

    def start_third_phase(self):
        # Bilgi popup
        self.third_popup = QMessageBox(self)
        self.third_popup.setIcon(QMessageBox.Information)
        self.third_popup.setWindowTitle("Video")
        self.third_popup.setText("Lütfen bekleyiniz. Son video kaydı alınıyor.")
        self.third_popup.setStandardButtons(QMessageBox.NoButton)
        self.third_popup.show()

        # 3. Fotoğraf çek
        cap3 = cv2.VideoCapture(self.rtsp_url)
        cap3.set(cv2.CAP_PROP_FRAME_WIDTH, RECORD_WIDTH)
        cap3.set(cv2.CAP_PROP_FRAME_HEIGHT, RECORD_HEIGHT)
        ret3, frame3 = cap3.read()
        cap3.release()

        if ret3 and frame3 is not None:
            frame3 = cv2.resize(frame3, (RECORD_WIDTH, RECORD_HEIGHT))
            frame3_ts = draw_timestamp(frame3.copy())
            photo3 = os.path.join(
                self.output_dir,
                f"parti{self.parti_no}_islem3_foto.jpg"
            )
            cv2.imwrite(photo3, frame3_ts)
            print(f"{photo3} kaydedildi.")
        else:
            print("Fotoğraf3 alınamadı!")

        # 3. Video kaydı
        self.worker3 = VideoWorker(
            self.rtsp_url,
            self.parti_no,
            3,
            self.output_dir,
            duration=10.0
        )
        self.worker3.finished.connect(lambda: self.third_popup.accept())
        self.worker3.start()

    def closeEvent(self, event):
        self.preview_cap.release()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    rtsp_url = "rtsp://admin:L2F4F47D@192.168.1.9:554/cam/realmonitor?channel=1&subtype=0"
    window = KameraVibe(rtsp_url, parti_no=1)
    window.show()
    sys.exit(app.exec_())
