import os
import sys
import time
import uuid
import hashlib
import traceback
import re
import urllib.parse
import webbrowser
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import urllib3
import psutil 
import subprocess # Windows/Mac ayırımı için güncellendi

# --- YAPAY ZEKA MODÜLÜ ---
import google.generativeai as genai

# --- GUI İMPORTLARI ---
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QMessageBox, QFileDialog, QStackedWidget,
                             QGridLayout, QFrame, QScrollArea, QAction, QSpinBox,
                             QCheckBox, QDialog, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QCursor
from PyQt5.QtWebEngineWidgets import QWebEngineView

# --- SELENIUM VE SÜRÜCÜ YÖNETİCİSİ ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options  
from webdriver_manager.chrome import ChromeDriverManager

# SSL Uyarılarını Gizle
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# HARİTA MOTORU VE GİZLİ ÇÖKMELERİ ENGELLER
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

try:
    import PyQt5
    plugin_yolu = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms")
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_yolu
except:
    pass

# ==============================================================================
# DOSYA YOLLARI (MAC VE WINDOWS UYUMLU)
# ==============================================================================
def get_data_dir():
    if sys.platform == 'win32':
        path = os.path.join(os.getenv('APPDATA'), "InfoFinder")
    else: # MAC ve LINUX ICIN
        path = os.path.join(os.path.expanduser("~"), ".infofinder")
        
    if not os.path.exists(path):
        os.makedirs(path)
    return path

DATA_DIR = get_data_dir()
LISANS_DOSYASI = os.path.join(DATA_DIR, "InfoFinder_License.txt")
HAFIZA_DOSYASI = os.path.join(DATA_DIR, "InfoFinder_Scanned.txt")
PROGRESS_DOSYASI = os.path.join(DATA_DIR, "InfoFinder_Progress.txt")
GECMIS_DOSYASI = os.path.join(DATA_DIR, "InfoFinder_History.json")

# ==============================================================================
# AYARLAR VE API ANAHTARLARI
# ==============================================================================
SUPABASE_URL = "https://gxtcpctoosuzdqjnboac.supabase.co"
SUPABASE_KEY = "sb_publishable_6eDfUAiL3f4HHi_mNMAqbQ_fGIuKsN1"

GEMINI_API_KEY = "AQ.Ab8RN6J8rTLLIG_OB_LHIhcuOP17VEztnGS-bKbSSHxLQjnmGA" 

MAKSIMUM_SORGULAMA_LIMITI = float('inf')
PAKET_ADI = "Bilinmiyor"

YASAKLI_KELIMELER = [
    "porno", "escort", "eskort", "sex", "seks", "kumar", "bahis", "bet", 
    "iddaa", "kumarhane"
]

OTOMATIK_ILCELER = {
    "İstanbul": ["Kadıköy", "Beşiktaş", "Şişli", "Bakırköy", "Fatih", "Üsküdar", "Maltepe", "Sarıyer", "Pendik", "Ümraniye", "Zeytinburnu", "Küçükçekmece", "Bahçelievler", "Esenyurt", "Avcılar", "Beylikdüzü", "Ataşehir", "Kartal", "Beyoğlu", "Kâğıthane"],
    "Ankara": ["Çankaya", "Keçiören", "Yenimahalle", "Mamak", "Etimesgut", "Sincan", "Altındağ", "Pursaklar", "Gölbaşı", "Polatlı"],
    "İzmir": ["Bornova", "Karşıyaka", "Konak", "Buca", "Karabağlar", "Çiğli", "Bayraklı", "Balçova", "Gaziemir", "Menemen"]
}

def gecmisi_yukle():
    if os.path.exists(GECMIS_DOSYASI):
        with open(GECMIS_DOSYASI, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

def gecmisi_kaydet(sehir, kategori, sonuc_sayisi, veriler):
    gecmis = gecmisi_yukle()
    su_an = datetime.now().strftime("%Y-%m-%d %H:%M")
    gecmis.append({"tarih": su_an, "sehir": sehir, "kategori": kategori, "sonuc": sonuc_sayisi, "isletmeler": veriler})
    with open(GECMIS_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(gecmis, f, ensure_ascii=False, indent=4)

def get_key_progress(key):
    if not key: return 0
    if os.path.exists(PROGRESS_DOSYASI):
        try:
            with open(PROGRESS_DOSYASI, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith(key + ":"):
                        return int(line.strip().split(":")[1])
        except: pass
    return 0

def increment_key_progress(key):
    if not key: return 0
    data = {}
    if os.path.exists(PROGRESS_DOSYASI):
        try:
            with open(PROGRESS_DOSYASI, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.strip().split(":", 1)
                        data[k] = int(v)
        except: pass
    data[key] = data.get(key, 0) + 1
    try:
        with open(PROGRESS_DOSYASI, "w", encoding="utf-8") as f:
            for k, v in data.items(): f.write(f"{k}:{v}\n")
    except: pass
    return data[key]

def get_hwid():
    mac = hex(uuid.getnode()).replace('0x', '').upper().zfill(12)
    return hashlib.sha256(mac.encode()).hexdigest()[:16].lower()

def icerik_guvenli_mi(metin):
    if not metin: return True
    metin_kucuk = str(metin).lower()
    for yasakli in YASAKLI_KELIMELER:
        if yasakli in metin_kucuk: return False
    return True

def eski_suruculeri_temizle():
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] in ['chromedriver.exe', 'chromedriver']:
                try: proc.kill()
                except: pass
    except: pass

def lisans_kontrol_et(girilen_key):
    global MAKSIMUM_SORGULAMA_LIMITI, PAKET_ADI
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}
    try:
        url = f"{SUPABASE_URL}/rest/v1/lisanslar?lisans_anahtari=eq.{girilen_key}&select=*"
        cevap = requests.get(url, headers=headers, timeout=10, verify=False)
        veri = cevap.json()
        
        if not veri or len(veri) == 0: return False, "Geçersiz Lisans! Bu anahtar sistemde bulunamadı."
        lisans_bilgisi = veri[0]
        if lisans_bilgisi.get('durum') == False: return False, "Bu lisans admin tarafından iptal edilmiştir!"
            
        bitis_tarihi_str = lisans_bilgisi.get('bitis_tarihi')
        bitis_tarihi = datetime.fromisoformat(bitis_tarihi_str.replace("Z", "+00:00"))
        su_an = datetime.now(bitis_tarihi.tzinfo)
        
        if su_an > bitis_tarihi: return False, f"Abonelik Süreniz Dolmuştur!\nYenilemek için EC Ajans'a ulaşın."
            
        kendi_hwidim = get_hwid()
        kayitli_hwid = lisans_bilgisi.get('hwid')
        
        if not kayitli_hwid or kayitli_hwid == "":
            requests.patch(f"{SUPABASE_URL}/rest/v1/lisanslar?id=eq.{lisans_bilgisi.get('id')}", headers=headers, json={"hwid": kendi_hwidim}, verify=False)
        elif kayitli_hwid != kendi_hwidim: return False, "Erişim Reddedildi!\nBu lisans anahtarı başka bir bilgisayara aittir."
            
        PAKET_ADI = lisans_bilgisi.get('paket_adi') or "Özel Paket"
        db_limit = lisans_bilgisi.get('arama_limiti')
        if db_limit is None or str(db_limit).strip() == "" or str(db_limit) == "-1": MAKSIMUM_SORGULAMA_LIMITI = float('inf')
        else: MAKSIMUM_SORGULAMA_LIMITI = int(db_limit)
            
        limit_yazisi = str(MAKSIMUM_SORGULAMA_LIMITI) if MAKSIMUM_SORGULAMA_LIMITI != float('inf') else "Sınırsız"
        return True, f"Lisans Doğrulandı! (Hoş Geldin, {lisans_bilgisi.get('musteri_adi')})\nPaket: {PAKET_ADI} [Limit: {limit_yazisi}]"
        
    except Exception as e: return None, f"Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.\nDetay: {str(e)}"

HARITA_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>
        :root { --vurgu-rengi: #8a2be2; }
        body { margin:0; padding:0; background-color: #0f071c; }
        #map { height: 100vh; width: 100%; border-radius: 6px; }
        .leaflet-layer, .leaflet-control-zoom-in, .leaflet-control-zoom-out { filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }
        .unique-marker-icon { background-color: var(--vurgu-rengi); border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map', {zoomControl: false}).setView([41.0082, 28.9784], 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        var customIcon = L.divIcon({ className: 'unique-marker-icon', iconSize: [20, 20], iconAnchor: [10, 10] });
        var marker = L.marker([41.0082, 28.9784], {icon: customIcon}).addTo(map);
        function setVurguRengi(hexColor) { document.documentElement.style.setProperty('--vurgu-rengi', hexColor); }
        function setLocation(ilce_adi, ana_sehir) {
            var cleanName = ilce_adi.replace(/[0-9]/g, '').split(',')[0].trim();
            var query = cleanName + ", " + ana_sehir + ", Turkey";
            fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(query))
            .then(res => res.json())
            .then(data => {
                if(data.length > 0) {
                    map.setView([data[0].lat, data[0].lon], 12);
                    marker.setLatLng([data[0].lat, data[0].lon]);
                    var currentVurgu = getComputedStyle(document.documentElement).getPropertyValue('--vurgu-rengi').trim();
                    marker.bindPopup("<b style='color:" + currentVurgu + ";'>📍 Şu An Taranan Bölge:</b><br><b style='font-size: 14px;'>" + cleanName + "</b>").openPopup();
                }
            });
        }
    </script>
</body>
</html>
"""

class YapayZekaIsci(QThread):
    cevap_geldi = pyqtSignal(str)
    hata_geldi = pyqtSignal(str)
    def __init__(self, mesaj):
        super().__init__()
        self.mesaj = mesaj
    def run(self):
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            uygun_modeller = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if not uygun_modeller:
                self.hata_geldi.emit("Bağlantı Hatası: API Anahtarınızda kullanılabilecek aktif bir dil modeli bulunamadı.")
                return
            model = genai.GenerativeModel(uygun_modeller[0])
            tam_prompt = f"Sen InfoFinder yazılımının yapay zeka asistanısın. Görevin, kullanıcılara buldukları işletmeler (B2B) için satış taktikleri, WhatsApp veya e-posta pazarlama şablonları hazırlamak ve program hakkında tavsiyeler vermektir. Yanıtların profesyonel, kısa ve net olmalı.\n\nKullanıcının Sorusu: {self.mesaj}"
            response = model.generate_content(tam_prompt)
            self.cevap_geldi.emit(response.text)
        except Exception as e:
            self.hata_geldi.emit(f"Sistem Hatası: Lütfen API anahtarınızı veya internet bağlantınızı kontrol edin.\nDetay: {str(e)}")

class YapayZekaAsistani(QDialog):
    def __init__(self, parent=None, tema=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 InfoFinder Akıllı Satış Asistanı")
        self.resize(500, 600)
        self.tema = tema if tema else {"bg": "#0f071c", "panel": "#1e1136", "border": "#4a2b7a", "vurgu": "#8a2be2", "text": "white"}
        self.setStyleSheet(f"background-color: {self.tema['bg']}; color: {self.tema['text']};")
        layout = QVBoxLayout(self)
        self.sohbet_gecmisi = QScrollArea()
        self.sohbet_gecmisi.setWidgetResizable(True)
        self.sohbet_gecmisi.setStyleSheet(f"QScrollArea {{ background-color: {self.tema['panel']}; border: 1px solid {self.tema['border']}; border-radius: 5px; }}")
        self.sohbet_icerik = QWidget()
        self.sohbet_icerik.setStyleSheet("background-color: transparent;")
        self.sohbet_layout = QVBoxLayout(self.sohbet_icerik)
        self.sohbet_layout.setAlignment(Qt.AlignTop)
        self.sohbet_gecmisi.setWidget(self.sohbet_icerik)
        layout.addWidget(self.sohbet_gecmisi)
        girdi_layout = QHBoxLayout()
        self.mesaj_kutusu = QLineEdit()
        self.mesaj_kutusu.setPlaceholderText("Örn: Emlakçılara yazılım satmak için mesaj şablonu yazar mısın?")
        self.mesaj_kutusu.setStyleSheet(f"background-color: {self.tema['bg']}; color: {self.tema['text']}; padding: 10px; border: 1px solid {self.tema['border']}; border-radius: 5px;")
        self.mesaj_kutusu.returnPressed.connect(self.mesaj_gonder)
        self.btn_gonder = QPushButton("Gönder")
        self.btn_gonder.setStyleSheet(f"background-color: {self.tema['vurgu']}; color: white; padding: 10px; border-radius: 5px; font-weight: bold; border: none;")
        self.btn_gonder.clicked.connect(self.mesaj_gonder)
        girdi_layout.addWidget(self.mesaj_kutusu)
        girdi_layout.addWidget(self.btn_gonder)
        layout.addLayout(girdi_layout)
        self.mesaj_ekle("🤖 Asistan", "Merhaba! InfoFinder'a hoş geldin. Çektiğin datalara nasıl satış yapacağın konusunda sana mesaj şablonları veya taktikler hazırlayabilirim. Ne sormak istersin?", is_bot=True)

    def mesaj_ekle(self, gonderen, mesaj, is_bot=False):
        renk = self.tema['vurgu'] if is_bot else "#4CAF50"
        lbl_mesaj = QLabel(f"<b>{gonderen}:</b><br>{mesaj.replace(chr(10), '<br>')}")
        lbl_mesaj.setWordWrap(True)
        lbl_mesaj.setStyleSheet(f"background-color: {self.tema['panel']}; border: 1px solid {renk}; border-radius: 5px; padding: 10px; margin: 5px;")
        lbl_mesaj.setTextInteractionFlags(Qt.TextSelectableByMouse)
        satir_layout = QHBoxLayout()
        if not is_bot: satir_layout.addStretch()
        satir_layout.addWidget(lbl_mesaj)
        if is_bot: satir_layout.addStretch()
        self.sohbet_layout.addLayout(satir_layout)
        QTimer.singleShot(100, lambda: self.sohbet_gecmisi.verticalScrollBar().setValue(self.sohbet_gecmisi.verticalScrollBar().maximum()))

    def mesaj_gonder(self):
        mesaj = self.mesaj_kutusu.text().strip()
        if not mesaj: return
        self.mesaj_kutusu.clear()
        self.mesaj_kutusu.setEnabled(False)
        self.btn_gonder.setEnabled(False)
        self.btn_gonder.setText("⏳ Bekleniyor...")
        self.mesaj_ekle("Sen", mesaj, is_bot=False)
        self.isci = YapayZekaIsci(mesaj)
        self.isci.cevap_geldi.connect(self.cevap_alindi)
        self.isci.hata_geldi.connect(self.hata_alindi)
        self.isci.start()

    def cevap_alindi(self, cevap):
        self.mesaj_ekle("🤖 Asistan", cevap, is_bot=True)
        self.arayuz_sifirla()

    def hata_alindi(self, hata):
        self.mesaj_ekle("⚠️ Sistem", hata, is_bot=True)
        self.arayuz_sifirla()

    def arayuz_sifirla(self):
        self.mesaj_kutusu.setEnabled(True)
        self.btn_gonder.setEnabled(True)
        self.btn_gonder.setText("Gönder")
        self.mesaj_kutusu.setFocus()

class IsletmeKarti(QFrame):
    def __init__(self, index, veri, wp_sablon="", ana_renk="#8a2be2"):
        super().__init__()
        self.veri = veri
        self.is_expanded = False
        self.ana_renk = ana_renk
        self.wp_sablon = wp_sablon
        
        self.setStyleSheet(f"IsletmeKarti {{ background-color: rgba(30, 17, 54, 0.8); border: 1px solid {self.ana_renk}; border-radius: 6px; margin-bottom: 3px; }} IsletmeKarti:hover {{ border: 1px solid #ffffff; }}")
        self.ana_layout = QVBoxLayout(self)
        self.ana_layout.setContentsMargins(8, 6, 8, 6)
        self.ana_layout.setSpacing(4)
        
        self.ust_frame = QWidget()
        self.ust_layout = QHBoxLayout(self.ust_frame)
        self.ust_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_index = QLabel(str(index))
        self.lbl_index.setFixedSize(22, 22)
        self.lbl_index.setAlignment(Qt.AlignCenter)
        self.lbl_index.setStyleSheet(f"background-color: {self.ana_renk}; color: white; border-radius: 11px; font-weight: bold; font-size: 10px;")
        
        self.lbl_isim = QLabel(f"{veri[0]}")
        self.lbl_isim.setFont(QFont("Arial", 10, QFont.Bold))
        self.lbl_isim.setStyleSheet("color: white; border: none;")
        
        self.ust_layout.addWidget(self.lbl_index)
        self.ust_layout.addWidget(self.lbl_isim)
        self.ust_layout.addStretch() 
        
        has_warning = False
        if veri[3] == "-":
            lbl_web = QLabel("🌐 Web Yok")
            lbl_web.setStyleSheet("background-color: #b71c1c; color: white; border-radius: 3px; padding: 2px 4px; font-size: 9px; font-weight: bold;")
            self.ust_layout.addWidget(lbl_web)
            has_warning = True
            
        if len(veri) > 5 and veri[5] == "-":
            lbl_sosyal = QLabel("📱 Sosyal Medya Yok")
            lbl_sosyal.setStyleSheet("background-color: #e65100; color: white; border-radius: 3px; padding: 2px 4px; font-size: 9px; font-weight: bold;")
            self.ust_layout.addWidget(lbl_sosyal)
            has_warning = True
            
        puan_str = str(veri[6]).replace(',', '.')
        try:
            puan_f = float(puan_str)
            if puan_f < 3.8:
                lbl_puan = QLabel("⭐ Düşük Puan")
                lbl_puan.setStyleSheet("background-color: #f57f17; color: white; border-radius: 3px; padding: 2px 4px; font-size: 9px; font-weight: bold;")
                self.ust_layout.addWidget(lbl_puan)
                has_warning = True
        except: pass
        
        if not has_warning:
            lbl_guclu = QLabel("💎 Güçlü Profil")
            lbl_guclu.setStyleSheet("background-color: #1b5e20; color: white; border-radius: 3px; padding: 2px 4px; font-size: 9px; font-weight: bold;")
            self.ust_layout.addWidget(lbl_guclu)
            
        self.lbl_ok = QLabel("▼")
        self.lbl_ok.setStyleSheet(f"color: {self.ana_renk}; font-size: 12px; border: none; margin-left: 5px;")
        self.ust_layout.addWidget(self.lbl_ok)
        self.ana_layout.addWidget(self.ust_frame)
        
        self.detay_frame = QWidget()
        self.detay_layout = QVBoxLayout(self.detay_frame)
        self.detay_layout.setContentsMargins(30, 0, 0, 0)
        self.detay_layout.setSpacing(2)
        
        stil_metin = f"color: {self.ana_renk}; font-size: 10px; text-decoration: none; border: none;"
        self.lbl_adres = QLabel(f"📍 {veri[1]}")
        self.lbl_adres.setStyleSheet("color: #9e9e9e; font-size: 10px; border: none;")
        self.lbl_adres.setWordWrap(True)
        self.detay_layout.addWidget(self.lbl_adres)
        
        if veri[2] != "-":
            tel_temiz = re.sub(r'\D', '', veri[2])
            is_cep = False; wa_no = ""
            if tel_temiz.startswith("905") and len(tel_temiz) == 12: is_cep = True; wa_no = tel_temiz
            elif tel_temiz.startswith("05") and len(tel_temiz) == 11: is_cep = True; wa_no = "90" + tel_temiz[1:]
            elif tel_temiz.startswith("5") and len(tel_temiz) == 10: is_cep = True; wa_no = "90" + tel_temiz
                
            if is_cep:
                if self.wp_sablon and self.wp_sablon.strip() != "":
                    hazir_mesaj = self.wp_sablon.replace("{isim}", veri[0])
                    url_mesaj = urllib.parse.quote(hazir_mesaj)
                    wp_link = f"https://wa.me/{wa_no}?text={url_mesaj}"
                else:
                    wp_link = f"https://wa.me/{wa_no}"
                    
                lbl_tel = QLabel(f'📞 <a href="{wp_link}" style="color: #25d366; text-decoration: none; font-weight: bold;">{veri[2]} [Tıkla ve WP Gönder]</a>')
                lbl_tel.setTextFormat(Qt.RichText)
                lbl_tel.setTextInteractionFlags(Qt.TextBrowserInteraction)
                lbl_tel.setOpenExternalLinks(False)
                lbl_tel.linkActivated.connect(self.guvenli_link_ac)
                lbl_tel.setCursor(QCursor(Qt.PointingHandCursor))
                lbl_tel.setStyleSheet("border: none; font-size: 10px;")
            else:
                lbl_tel = QLabel(f"📞 {veri[2]}")
                lbl_tel.setStyleSheet("color: #ff80ab; font-size: 10px; font-weight: bold; border: none;")
            self.detay_layout.addWidget(lbl_tel)
            
        if veri[3] != "-":
            href = veri[3] if veri[3].startswith('http') else 'http://' + veri[3]
            lbl_web = QLabel(f'🌐 <a href="{href}" style="{stil_metin}">{veri[3]}</a>')
            lbl_web.setTextFormat(Qt.RichText)
            lbl_web.setTextInteractionFlags(Qt.TextBrowserInteraction)
            lbl_web.setOpenExternalLinks(False)
            lbl_web.linkActivated.connect(self.guvenli_link_ac)
            lbl_web.setStyleSheet("border: none;")
            self.detay_layout.addWidget(lbl_web)
            
        if len(veri) > 4 and veri[4] != "-":
            lbl_email = QLabel(f"✉️ {veri[4]}")
            lbl_email.setStyleSheet("color: #ffb74d; font-size: 10px; font-weight: bold; border: none;")
            self.detay_layout.addWidget(lbl_email)
            
        if len(veri) > 5 and veri[5] != "-":
            lbl_sosyal = QLabel(f"📱 {veri[5]}")
            lbl_sosyal.setTextFormat(Qt.RichText)
            lbl_sosyal.setTextInteractionFlags(Qt.TextBrowserInteraction)
            lbl_sosyal.setOpenExternalLinks(False)
            lbl_sosyal.linkActivated.connect(self.guvenli_link_ac)
            lbl_sosyal.setStyleSheet("border: none; font-size: 10px;")
            self.detay_layout.addWidget(lbl_sosyal)
            
        self.ana_layout.addWidget(self.detay_frame)
        self.detay_frame.hide()
        self.ust_frame.mousePressEvent = self.karti_ac_kapat

    def guvenli_link_ac(self, url):
        try: webbrowser.open(url)
        except: pass

    def karti_ac_kapat(self, event):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.detay_frame.show()
            self.lbl_ok.setText("▲")
            self.setStyleSheet(f"IsletmeKarti {{ background-color: rgba(43, 27, 77, 0.9); border: 1px solid {self.ana_renk}; border-radius: 6px; margin-bottom: 3px; }}")
        else:
            self.detay_frame.hide()
            self.lbl_ok.setText("▼")
            self.setStyleSheet(f"IsletmeKarti {{ background-color: rgba(30, 17, 54, 0.8); border: 1px solid {self.ana_renk}; border-radius: 6px; margin-bottom: 3px; }} IsletmeKarti:hover {{ border: 1px solid #ffffff; }}")

class HaritalarBotuIsci(QThread):
    yeni_satir_sinyali = pyqtSignal(list)
    bitti_sinyali = pyqtSignal(str)
    durum_sinyali = pyqtSignal(str)
    konum_sinyali = pyqtSignal(str, str) 

    def __init__(self, sehir, kategori, kullanıcı_limiti, proxy="", ana_il="İstanbul"):
        super().__init__()
        self.ana_sehir_orijinal = ana_il 
        self.kategori = kategori
        self.is_running = True 
        self.hedef_limit = kullanıcı_limiti
        self.proxy = proxy
        
        self.scanned_urls = set()
        if os.path.exists(HAFIZA_DOSYASI):
            try:
                with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f: self.scanned_urls = set(line.strip() for line in f if line.strip())
            except: pass
        
        self.guncel_key = ""
        if os.path.exists(LISANS_DOSYASI):
            try:
                with open(LISANS_DOSYASI, "r") as f: self.guncel_key = f.read().strip()
            except: pass
            
        self.toplam_gecmis_sayisi = get_key_progress(self.guncel_key)

        sehir_kontrol = str(sehir).strip().upper()
        if "İSTANBUL" in sehir_kontrol or "ISTANBUL" in sehir_kontrol: self.aranacak_bolgeler = [f"{ilce}, İstanbul" for ilce in OTOMATIK_ILCELER["İstanbul"]]
        elif "ANKARA" in sehir_kontrol: self.aranacak_bolgeler = [f"{ilce}, Ankara" for ilce in OTOMATIK_ILCELER["Ankara"]]
        elif "İZMİR" in sehir_kontrol or "IZMIR" in sehir_kontrol: self.aranacak_bolgeler = [f"{ilce}, İzmir" for ilce in OTOMATIK_ILCELER["İzmir"]]
        else:
            temiz_sehir = str(sehir).strip()
            self.aranacak_bolgeler = [f"{temiz_sehir}, {ana_il}"] if ana_il.lower() not in temiz_sehir.lower() else [temiz_sehir]
            
        self.toplam_bolge_sayisi = len(self.aranacak_bolgeler)

    def bekle(self, saniye):
        for _ in range(int(saniye * 10)):
            if not self.is_running: break
            time.sleep(0.1)

    def sosyal_ve_email_bul(self, website_url):
        bulunanlar = {"email": "-", "sosyal": "-"}
        if not website_url or website_url == "-": return bulunanlar
        if not website_url.startswith("http"): website_url = "http://" + website_url
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
            cevap = requests.get(website_url, headers=headers, timeout=5.0, verify=False)
            if cevap.status_code == 200:
                soup = BeautifulSoup(cevap.text, 'html.parser')
                tum_linkler = soup.find_all('a', href=True)
                sosyal_linkler, sosyal_adlar = [], []
                
                for l in tum_linkler:
                    link = l.get('href', '')
                    if not link: continue
                    link_kucuk = link.lower()
                    temiz_link = link_kucuk.split('?')[0].strip(' /')
                    yasakli_tam_linkler = ["http://instagram.com", "https://instagram.com", "http://www.instagram.com", "https://www.instagram.com", "http://facebook.com", "https://facebook.com", "http://www.facebook.com", "https://www.facebook.com", "http://twitter.com", "https://twitter.com", "http://www.twitter.com", "https://www.twitter.com", "http://x.com", "https://x.com", "http://www.x.com", "https://www.x.com"]
                    if temiz_link in yasakli_tam_linkler: continue
                    if "share" in link_kucuk or "intent" in link_kucuk or "sharer" in link_kucuk or "tweet?" in link_kucuk: continue 

                    if "instagram.com/" in link_kucuk and "Instagram" not in sosyal_adlar: 
                        sosyal_adlar.append("Instagram"); sosyal_linkler.append(f'<a href="{link}" style="color: #b388ff; text-decoration: none;">Instagram</a>')
                    elif "facebook.com/" in link_kucuk and "Facebook" not in sosyal_adlar: 
                        sosyal_adlar.append("Facebook"); sosyal_linkler.append(f'<a href="{link}" style="color: #b388ff; text-decoration: none;">Facebook</a>')
                    elif ("twitter.com/" in link_kucuk or "x.com/" in link_kucuk) and "Twitter" not in sosyal_adlar:
                        sosyal_adlar.append("Twitter"); sosyal_linkler.append(f'<a href="{link}" style="color: #b388ff; text-decoration: none;">Twitter(X)</a>')
                        
                if sosyal_linkler: bulunanlar["sosyal"] = " | ".join(sosyal_linkler)
                
                emailler = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cevap.text))
                gecerli_emailler = [e for e in emailler if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.css', '.js')) and "sentry" not in e and "wixpress" not in e]
                if gecerli_emailler:
                    bulunanlar["email"] = "; ".join(list(gecerli_emailler)[:2])
        except Exception: pass
        return bulunanlar

    def run(self):
        driver = None
        toplam_cekilen = 0
        try:
            eski_suruculeri_temizle()
            
            if self.toplam_gecmis_sayisi >= MAKSIMUM_SORGULAMA_LIMITI:
                self.bitti_sinyali.emit(f"KOTA_LIMITI: {PAKET_ADI} paketinizin maksimum taratma sınırına ({MAKSIMUM_SORGULAMA_LIMITI}) ulaştınız!")
                return

            options = Options()
            options.add_argument('--headless=new') 
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--lang=tr')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--log-level=3')
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            
            if self.proxy and self.proxy.strip() != "":
                options.add_argument(f'--proxy-server=http://{self.proxy.strip()}')
            
            service = Service(ChromeDriverManager().install())
            
            # --- MAC VE WINDOWS AYRIMI (ÇÖKME ÖNLEYİCİ) ---
            if sys.platform == 'win32':
                try:
                    service.creation_flags = subprocess.CREATE_NO_WINDOW
                except AttributeError:
                    pass
                
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(60)

            for bolge_index, bolge in enumerate(self.aranacak_bolgeler):
                if not self.is_running or toplam_cekilen >= self.hedef_limit: break
                if (self.toplam_gecmis_sayisi + toplam_cekilen) >= MAKSIMUM_SORGULAMA_LIMITI:
                    self.bitti_sinyali.emit(f"KOTA_LIMITI: Tarama esnasında {PAKET_ADI} kotanıza ({MAKSIMUM_SORGULAMA_LIMITI}) ulaşıldı!")
                    self.is_running = False
                    break

                self.konum_sinyali.emit(bolge, self.ana_sehir_orijinal)

                sorgu = f"{bolge} {self.kategori}"
                if self.kategori == "Tümü" or not self.kategori: sorgu = bolge
                bolge_etiketi = f"Bölge {bolge_index + 1}/{self.toplam_bolge_sayisi} ({bolge})"
                self.durum_sinyali.emit(f"Tarama Başlıyor: '{sorgu}'...")
                
                sorgu_encoded = urllib.parse.quote_plus(sorgu)
                driver.get(f"https://www.google.com/maps/search/{sorgu_encoded}?hl=tr")
                self.bekle(3) 
                
                try:
                    cerez_btn = driver.find_elements(By.XPATH, '//button[.//span[contains(text(), "Tümünü reddet") or contains(text(), "Kabul et") or contains(text(), "Accept") or contains(text(), "Reject")]]')
                    if cerez_btn:
                        driver.execute_script("arguments[0].click();", cerez_btn[0])
                        self.bekle(1.5)
                except: pass
                
                try: scrollable_div = driver.find_element(By.XPATH, '//*[@role="feed"]')
                except: continue 

                islenen_linkler = set()
                ardisik_bos_scroll = 0

                while self.is_running and toplam_cekilen < self.hedef_limit:
                    isletmeler = driver.find_elements(By.CLASS_NAME, "hfpxzc")
                    yeni_isletmeler = []
                    for islt in isletmeler:
                        try:
                            href = islt.get_attribute("href")
                            if href and href not in islenen_linkler: yeni_isletmeler.append((islt, href))
                        except: pass
                        
                    if not yeni_isletmeler:
                        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                        self.bekle(2) 
                        ardisik_bos_scroll += 1
                        if ardisik_bos_scroll >= 3: break
                        continue

                    ardisik_bos_scroll = 0 

                    for isletme, href in yeni_isletmeler:
                        if not self.is_running or toplam_cekilen >= self.hedef_limit: break
                        if (self.toplam_gecmis_sayisi + toplam_cekilen) >= MAKSIMUM_SORGULAMA_LIMITI: break
                        if href and href in self.scanned_urls:
                            islenen_linkler.add(href)
                            continue

                        try:
                            isim_garanti = "-"
                            try:
                                isim_garanti = isletme.get_attribute("aria-label")
                                if not isim_garanti: isim_garanti = "-"
                            except: pass

                            try:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", isletme)
                                self.bekle(0.3)
                            except: pass
                            
                            driver.execute_script("arguments[0].click();", isletme)
                            self.bekle(2.5) 
                            
                            puan_degeri = "Puan Yok"
                            try:
                                puan_blok = driver.find_element(By.XPATH, '//div[contains(@class, "F7nice")]').text
                                ilk_satir = puan_blok.split('\n')[0].strip()
                                if re.match(r'^[1-5](?:[,.]\d)?$', ilk_satir): puan_degeri = ilk_satir
                            except: pass
                                
                            try: 
                                isim = driver.find_element(By.XPATH, '//h1[contains(@class, "DUwDvf")]').text
                                if not isim or isim == "": isim = isim_garanti
                            except: isim = isim_garanti

                            try: adres = driver.find_element(By.XPATH, '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]').text
                            except: adres = "-"
                            try: telefon = driver.find_element(By.XPATH, '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]').text
                            except: telefon = "-"
                            try: website = driver.find_element(By.XPATH, '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]').text
                            except: website = "-"
                            
                            harita_linki = href if href else "-"

                            toplam_cekilen += 1
                            islenen_linkler.add(href) 
                            
                            if harita_linki != "-":
                                self.scanned_urls.add(harita_linki)
                                try:
                                    with open(HAFIZA_DOSYASI, "a", encoding="utf-8") as hf: hf.write(harita_linki + "\n")
                                except: pass

                            self.durum_sinyali.emit(f"Genel: {toplam_cekilen}/{self.hedef_limit} | {bolge_etiketi} -> Taranıyor...")
                            ek = self.sosyal_ve_email_bul(website)
                            if self.is_running:
                                self.yeni_satir_sinyali.emit([isim, adres, telefon, website, ek["email"], ek["sosyal"], puan_degeri, harita_linki])
                            if toplam_cekilen >= self.hedef_limit:
                                self.is_running = False
                                break

                        except Exception: 
                            islenen_linkler.add(href) 
                            continue
                            
            if (self.toplam_gecmis_sayisi + toplam_cekilen) >= MAKSIMUM_SORGULAMA_LIMITI:
                self.bitti_sinyali.emit(f"KOTA_LIMITI: {PAKET_ADI}nizin maksimum taratma sınırına ({MAKSIMUM_SORGULAMA_LIMITI}) ulaştınız!")
            elif toplam_cekilen >= self.hedef_limit:
                self.bitti_sinyali.emit(f"Talep ettiğiniz {self.hedef_limit} sonuç başarıyla çıkarıldı ve arama tamamlandı!")
            elif self.is_running:
                self.bitti_sinyali.emit(f"Bütün bölgeler tarandı. Toplam {toplam_cekilen} sonuç çıkarıldı.")
            else:
                self.bitti_sinyali.emit(f"İşlem durduruldu. Toplam {toplam_cekilen} sonuç çıkarıldı.")
            
        except Exception as e:
            if self.is_running: self.bitti_sinyali.emit(f"SİST_HATASI:\n{traceback.format_exc()}")
        finally:
            if driver is not None:
                try: driver.quit()
                except: pass

    def durdur(self):
        self.is_running = False

class InfoFinderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InfoFinder - Professional")
        self.setGeometry(100, 100, 1200, 350)
        self.aktif_tema = {"bg": "#0f071c", "panel": "#1e1136", "border": "#4a2b7a", "vurgu": "#8a2be2", "text": "white"}
        self.secili_kategori = "Avukat"
        self.secili_sehir = "İstanbul"
        self.tum_veriler = []
        self.isci = None

        self.setStyleSheet(f"background-color: {self.aktif_tema['bg']}; color: {self.aktif_tema['text']};")
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.ana_ekrani_olustur()
        self.lisans_ekranini_olustur()

        self.stacked_widget.addWidget(self.lisans_widget)
        self.stacked_widget.addWidget(self.ana_widget)

        if self.lisans_gecerli_mi():
            self.stacked_widget.setCurrentWidget(self.ana_widget)
            self.kalan_hakki_guncelle()
        else:
            self.menuBar().hide()
            self.stacked_widget.setCurrentWidget(self.lisans_widget)

        self.lisans_timer = QTimer(self)
        self.lisans_timer.timeout.connect(self.otomatik_lisans_denetle)
        self.lisans_timer.start(60000)

    def kalan_hakki_guncelle(self):
        global MAKSIMUM_SORGULAMA_LIMITI
        if MAKSIMUM_SORGULAMA_LIMITI == float('inf'):
            self.kalan_hak_lbl.hide()
            return
        guncel_key = ""
        if os.path.exists(LISANS_DOSYASI):
            try:
                with open(LISANS_DOSYASI, "r") as f: guncel_key = f.read().strip()
            except: pass
        tuketilen = get_key_progress(guncel_key)
        kalan = int(max(0, MAKSIMUM_SORGULAMA_LIMITI - tuketilen))
        self.kalan_hak_lbl.setText(f"🎁 Kalan Arama Hakkı: {kalan}")
        self.kalan_hak_lbl.show()

    def lisans_gecerli_mi(self):
        if os.path.exists(LISANS_DOSYASI):
            try:
                with open(LISANS_DOSYASI, "r") as f: kayitli_key = f.read().strip()
                durum, mesaj = lisans_kontrol_et(kayitli_key)
                if durum is True: return True
                if durum is False: 
                    try: os.remove(LISANS_DOSYASI)
                    except: pass
            except: pass
        return False

    def lisans_ekranini_olustur(self):
        self.lisans_widget = QWidget()
        ana_layout = QVBoxLayout(self.lisans_widget)
        ana_layout.setAlignment(Qt.AlignCenter)

        kutu = QFrame()
        kutu.setStyleSheet(f"background-color: {self.aktif_tema['panel']}; border: 1px solid {self.aktif_tema['border']}; border-radius: 10px;")
        kutu.setFixedSize(420, 350)
        
        kutu_layout = QVBoxLayout(kutu)
        kutu_layout.setContentsMargins(30, 30, 30, 30)

        baslik = QLabel("Abonelik Aktivasyonu")
        baslik.setFont(QFont("Arial", 16, QFont.Bold))
        baslik.setAlignment(Qt.AlignCenter)
        baslik.setStyleSheet(f"color: {self.aktif_tema['vurgu']}; border: none;")
        kutu_layout.addWidget(baslik)

        hwid = get_hwid()
        hwid_lbl = QLabel(f"Makine ID'niz:\n{hwid}")
        hwid_lbl.setStyleSheet("color: #ff5252; font-weight: bold; padding: 10px; background-color: #0a0413; border: 1px dashed #ff5252;")
        hwid_lbl.setAlignment(Qt.AlignCenter)
        hwid_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        kutu_layout.addWidget(hwid_lbl)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Lütfen Abonelik Anahtarınızı Girin...")
        self.key_input.setStyleSheet("background-color: #0a0413; border: 1px solid #3d2363; padding: 10px; border-radius: 5px;")
        self.key_input.setAlignment(Qt.AlignCenter)
        kutu_layout.addWidget(self.key_input)

        btn_onayla = QPushButton("Lisansı Doğrula ve Giriş Yap")
        btn_onayla.setStyleSheet(f"background-color: {self.aktif_tema['vurgu']}; padding: 12px; font-weight: bold; border-radius: 5px; border: none;")
        btn_onayla.clicked.connect(self.dogrula_buton_tiklandi)
        kutu_layout.addWidget(btn_onayla)
        ana_layout.addWidget(kutu)

    def dogrula_buton_tiklandi(self):
        girilen = self.key_input.text().strip()
        self.key_input.setText("Buluta Bağlanılıyor, Lütfen Bekleyin...")
        self.key_input.setEnabled(False)
        QApplication.processEvents()
        
        durum, mesaj = lisans_kontrol_et(girilen)
        if durum is True:
            with open(LISANS_DOSYASI, "w") as f: f.write(girilen)
            satirlar = mesaj.split('\n')
            gosterge_metni = f"✅ {satirlar[0]}"
            if len(satirlar) > 1: gosterge_metni += f"  |  {satirlar[1]}"
            self.arama_gosterge.setText(gosterge_metni)
            self.menuBar().show()
            self.stacked_widget.setCurrentWidget(self.ana_widget)
            self.kalan_hakki_guncelle()
        else: 
            self.key_input.setEnabled(True)
            self.key_input.setText(girilen)
            QMessageBox.critical(self, "Hata", mesaj)

    def ana_ekrani_olustur(self):
        self.ana_widget = QWidget()
        self.menuleri_olustur()
        ana_layout = QVBoxLayout(self.ana_widget)
        ana_layout.setContentsMargins(5, 5, 5, 0)
        ana_layout.setSpacing(2)
        
        baslik_layout = QVBoxLayout()
        self.arama_gosterge = QLabel("Bölge seçin ve aramaya başlayın • 0 Sonuç")
        self.arama_gosterge.setFont(QFont("Arial", 12, QFont.Bold))
        self.arama_gosterge.setAlignment(Qt.AlignCenter)
        self.arama_gosterge.setStyleSheet("margin-bottom: 2px; border: none;")
        baslik_layout.addWidget(self.arama_gosterge)
        ana_layout.addLayout(baslik_layout)
        
        self.orta_panel = QFrame()
        self.orta_panel.setMaximumHeight(300)
        orta_layout = QHBoxLayout(self.orta_panel)
        orta_layout.setContentsMargins(2, 2, 2, 2)
        
        sol_kontroller = QVBoxLayout()
        sol_kontroller.setSpacing(2)
        sehir_layout = QHBoxLayout()
        
        self.sehir_combo = QComboBox()
        iller_81 = [
            "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
            "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur",
            "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
            "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul",
            "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale", "Kırklareli", "Kırşehir",
            "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
            "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Şanlıurfa", "Siirt", "Sinop",
            "Sivas", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
        ]
        self.sehir_combo.addItems(iller_81)
        self.sehir_combo.setCurrentText("İstanbul")
        
        self.sehir_input = QLineEdit()
        self.sehir_input.setPlaceholderText("İlçeyi kendiniz yazın (Örn: Kadıköy)...")
        sehir_layout.addWidget(QLabel("Bölge:"), 0)
        sehir_layout.addWidget(self.sehir_combo, 1)
        sehir_layout.addWidget(self.sehir_input, 2)
        sol_kontroller.addLayout(sehir_layout)

        kategori_ozel_layout = QHBoxLayout()
        self.kategori_input = QLineEdit()
        self.kategori_input.setPlaceholderText("Meslek yazın (Örn: İnşaat, Diyetisyen)...")
        self.kategori_input.textChanged.connect(self.ozel_kategori_yazildi)
        kategori_ozel_layout.addWidget(QLabel("Meslek:"), 0)
        kategori_ozel_layout.addWidget(self.kategori_input, 1)
        sol_kontroller.addLayout(kategori_ozel_layout)
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(2)
        kategoriler = [
            ("Avukat", "⚖️"), ("Doktor", "🩺"), ("Diş Hekimi", "🦷"), ("Klinik", "🏥"),
            ("Muhasebeci", "📊"), ("Kuaför", "✂️"), ("Oto Servis", "🔧"), ("Restoran", "🍽️"),
            ("Otel", "🏨"), ("Eczane", "💊"), ("Spor Salonu", "🏋️"), ("Okul", "🏫"),
            ("Güzellik", "💅"), ("Banka", "🏦"), ("Market", "🛒"), ("Tümü", "🔍")
        ]
        self.kategori_butonlari = []
        row, col = 0, 0
        for ad, ikon in kategoriler:
            btn = QPushButton(f"{ikon} {ad}")
            btn.clicked.connect(lambda checked, a=ad: self.kategori_buton_basildi(a))
            grid_layout.addWidget(btn, row, col)
            self.kategori_butonlari.append((ad, btn))
            col += 1
            if col > 3: col = 0; row += 1
        sol_kontroller.addLayout(grid_layout)

        self.filtre_grup = QFrame()
        self.filtre_grup.setMaximumHeight(35)
        filtre_layout = QHBoxLayout(self.filtre_grup)
        filtre_layout.setContentsMargins(10, 0, 10, 0)
        filtre_layout.setSpacing(15)
        
        lbl_filtre = QLabel("🎯 Excel Filtresi:")
        lbl_filtre.setStyleSheet("font-weight: bold; font-size: 11px; border: none;")
        self.chk_tel = QCheckBox("📞 Tel")
        self.chk_tel.stateChanged.connect(self.kartlari_sirala)
        self.chk_wa = QCheckBox("💬 WP")
        self.chk_wa.stateChanged.connect(self.kartlari_sirala)
        self.chk_email = QCheckBox("✉️ E-Posta")
        self.chk_email.stateChanged.connect(self.kartlari_sirala)
        self.chk_sosyal = QCheckBox("📱 Sosyal Medya")
        self.chk_sosyal.stateChanged.connect(self.kartlari_sirala)
        
        filtre_layout.addWidget(lbl_filtre)
        filtre_layout.addWidget(self.chk_tel)
        filtre_layout.addWidget(self.chk_wa)
        filtre_layout.addWidget(self.chk_email)
        filtre_layout.addWidget(self.chk_sosyal)
        filtre_layout.addStretch() 
        sol_kontroller.addWidget(self.filtre_grup)
        
        wp_grup = QFrame()
        wp_grup.setMaximumHeight(35)
        wp_lyt = QHBoxLayout(wp_grup)
        wp_lyt.setContentsMargins(10, 0, 10, 0)
        lbl_wp = QLabel("💬 Özel WP Şablonu:")
        lbl_wp.setStyleSheet("font-weight: bold; font-size: 11px; border: none;")
        self.wp_sablon = QLineEdit()
        self.wp_sablon.setPlaceholderText("Örn: Merhaba {isim}, hizmetlerinizi inceledik...")
        wp_lyt.addWidget(lbl_wp)
        wp_lyt.addWidget(self.wp_sablon)
        sol_kontroller.addWidget(wp_grup)
        orta_layout.addLayout(sol_kontroller, 4)
        
        self.harita_view = QWebEngineView()
        self.harita_view.setHtml(HARITA_HTML)
        self.harita_view.setMinimumWidth(300)
        self.harita_view.setMinimumHeight(150)
        orta_layout.addWidget(self.harita_view, 3)

        sag_kontroller = QVBoxLayout()
        sag_kontroller.setSpacing(2)
        
        limit_layout = QHBoxLayout()
        proxy_lbl = QLabel("🛡️ Proxy (Opsiyonel):")
        proxy_lbl.setStyleSheet("font-weight: bold; color: white;")
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("IP:PORT")
        
        limit_lbl = QLabel("  Limit:")
        limit_lbl.setStyleSheet("font-weight: bold; color: white;")
        self.limit_box = QSpinBox()
        self.limit_box.setRange(1, 10000)
        self.limit_box.setValue(10)
        
        limit_layout.addWidget(proxy_lbl)
        limit_layout.addWidget(self.proxy_input)
        limit_layout.addWidget(limit_lbl)
        limit_layout.addWidget(self.limit_box)
        sag_kontroller.addLayout(limit_layout)

        self.kalan_hak_lbl = QLabel("")
        self.kalan_hak_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        self.kalan_hak_lbl.setAlignment(Qt.AlignCenter)
        self.kalan_hak_lbl.setMaximumHeight(38)
        self.kalan_hak_lbl.hide()
        sag_kontroller.addWidget(self.kalan_hak_lbl)

        self.btn_ara = QPushButton("🚀 YENİ ARAMA BAŞLAT")
        self.btn_ara.setFont(QFont("Arial", 11, QFont.Bold))
        self.btn_ara.clicked.connect(self.botu_baslat)
        
        self.btn_durdur = QPushButton("🛑 ARAMAYI DURDUR")
        self.btn_durdur.setFont(QFont("Arial", 10, QFont.Bold))
        self.btn_durdur.setStyleSheet("background-color: #d32f2f; color: white; padding: 8px; border-radius: 4px;")
        self.btn_durdur.clicked.connect(self.botu_durdur)
        self.btn_durdur.setEnabled(False)
        
        self.siralama_combo = QComboBox()
        self.siralama_combo.addItems(["Filtre: Varsayılan (Sıralı)", "Filtre: Puan (En Yüksek)", "Filtre: Alfabetik (A-Z)"])
        self.siralama_combo.currentIndexChanged.connect(self.kartlari_sirala)
        
        btn_grid = QGridLayout()
        btn_grid.setSpacing(4)
        
        self.btn_excel = QPushButton("📊 Excel Kaydet")
        self.btn_excel.setStyleSheet("background-color: #00a86b; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_excel.clicked.connect(self.excel_kaydet)
        
        self.btn_vcf = QPushButton("📇 Rehber (VCF)")
        self.btn_vcf.setStyleSheet("background-color: #0288d1; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_vcf.clicked.connect(self.vcf_kaydet)

        self.btn_gecmis = QPushButton("🕰️ Geçmiş")
        self.btn_gecmis.setStyleSheet("background-color: #f39c12; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_gecmis.clicked.connect(self.gecmis_penceresini_goster)
        
        self.btn_dashboard = QPushButton("📈 İstatistiklerim")
        self.btn_dashboard.setStyleSheet("background-color: #9c27b0; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_dashboard.clicked.connect(self.dashboard_goster)
        
        self.btn_asistan = QPushButton("🤖 Akıllı Satış Asistanı")
        self.btn_asistan.setStyleSheet("background-color: #00bcd4; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_asistan.clicked.connect(self.asistani_ac)
        
        btn_grid.addWidget(self.btn_excel, 0, 0)
        btn_grid.addWidget(self.btn_vcf, 0, 1)
        btn_grid.addWidget(self.btn_gecmis, 1, 0)
        btn_grid.addWidget(self.btn_dashboard, 1, 1)
        btn_grid.addWidget(self.btn_asistan, 2, 0, 1, 2)

        sag_kontroller.addWidget(self.btn_ara)
        sag_kontroller.addWidget(self.btn_durdur)
        sag_kontroller.addWidget(self.siralama_combo)
        sag_kontroller.addLayout(btn_grid)
        
        orta_layout.addLayout(sag_kontroller, 2)
        ana_layout.addWidget(self.orta_panel)
        
        self.durum_lbl = QLabel("Akıllı Bot Aktif: Belirlediğiniz limite göre işletmeler taranır.")
        self.durum_lbl.setStyleSheet("color: #00e676; font-style: italic; font-size: 10px; margin-top: 1px; margin-bottom: 1px; border: none;")
        ana_layout.addWidget(self.durum_lbl)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("border: none;")
        self.scroll_area.setMinimumHeight(0)
        
        self.kartlar_widget = QWidget()
        self.kartlar_widget.setStyleSheet("background-color: transparent;")
        self.kartlar_layout = QVBoxLayout(self.kartlar_widget)
        self.kartlar_layout.setAlignment(Qt.AlignTop) 
        self.scroll_area.setWidget(self.kartlar_widget)
        ana_layout.addWidget(self.scroll_area)

        self.kategori_buton_basildi("Avukat")
        self.harita_view.loadFinished.connect(lambda: self.harita_view.page().runJavaScript(f"setVurguRengi('{self.aktif_tema['vurgu']}');"))
        self.tema_uygula("Koyu Mor")

    def dashboard_goster(self):
        gecmis = gecmisi_yukle()
        toplam_isletme = sum(item.get("sonuc", 0) for item in gecmis)
        toplam_arama = len(gecmis)
        mesaj = f"""
📊 INFOFINDER SAAS PERFORMANS ÖZETİ
────────────────────────────
🔍 Toplam Gerçekleşen Arama: {toplam_arama}
🏢 Çekilen Toplam Potansiyel Müşteri: {toplam_isletme}

💡 YZ SATIŞ TAVSİYESİ: 
Müşterilerinize ulaşırken "WP Özel Şablonu" kısmını kullanın. Web sitesi veya sosyal medyası eksik (kırmızı etiketli) olan işletmelere doğrudan bu eksikliği giderecek bir teklifle giderseniz satış oranınız 3 kat artacaktır!
        """
        QMessageBox.information(self, "İstatistik Paneli", mesaj)

    def asistani_ac(self):
        self.asistan_penceresi = YapayZekaAsistani(self, tema=self.aktif_tema)
        self.asistan_penceresi.show()

    def gecmis_penceresini_goster(self):
        self.dialog = QDialog(self)
        self.dialog.setWindowTitle("Geçmiş Aramalar (İşletmeleri Görmek İçin Satıra Çift Tıklayın)")
        self.dialog.resize(650, 400)
        layout = QVBoxLayout(self.dialog)

        self.gecmis_tablo = QTableWidget()
        self.gecmis_tablo.setColumnCount(4)
        self.gecmis_tablo.setHorizontalHeaderLabels(["Tarih", "Bölge / Şehir", "Aranan Meslek", "Bulunan Sayısı"])
        self.gecmis_tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.gecmis_tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.gecmis_tablo.setSelectionBehavior(QTableWidget.SelectRows) 

        self.gecmis_veriler = gecmisi_yukle()
        self.gecmis_veriler.reverse() 
        self.gecmis_tablo.setRowCount(len(self.gecmis_veriler))

        for row, item in enumerate(self.gecmis_veriler):
            self.gecmis_tablo.setItem(row, 0, QTableWidgetItem(item.get("tarih", "")))
            self.gecmis_tablo.setItem(row, 1, QTableWidgetItem(item.get("sehir", "")))
            self.gecmis_tablo.setItem(row, 2, QTableWidgetItem(item.get("kategori", "")))
            self.gecmis_tablo.setItem(row, 3, QTableWidgetItem(str(item.get("sonuc", 0))))

        self.gecmis_tablo.cellDoubleClicked.connect(self.gecmis_detay_yukle)
        self.dialog.setStyleSheet(f"background-color: {self.aktif_tema['bg']}; color: {self.aktif_tema['text']};")
        self.gecmis_tablo.setStyleSheet(f"background-color: {self.aktif_tema['panel']}; color: {self.aktif_tema['text']}; gridline-color: {self.aktif_tema['border']}; border: none;")
        self.gecmis_tablo.horizontalHeader().setStyleSheet(f"background-color: {self.aktif_tema['border']}; color: white; font-weight: bold;")
        layout.addWidget(self.gecmis_tablo)

        btn_kapat = QPushButton("Pencereyi Kapat")
        btn_kapat.setStyleSheet(f"background-color: {self.aktif_tema['border']}; color: white; padding: 8px; font-weight: bold; border-radius: 4px;")
        btn_kapat.clicked.connect(self.dialog.accept)
        layout.addWidget(btn_kapat)
        self.dialog.exec_()

    def gecmis_detay_yukle(self, row, col):
        secilen_veri = self.gecmis_veriler[row]
        kayitli_liste = secilen_veri.get("isletmeler", [])
        if not kayitli_liste:
            QMessageBox.warning(self.dialog, "Uyarı", "Bu aramanın detay verisi bulunamadı.")
            return
        self.arayuzu_temizle()
        self.secili_sehir = secilen_veri.get("sehir", "")
        self.secili_kategori = secilen_veri.get("kategori", "")
        self.tum_veriler = kayitli_liste
        self.kartlari_sirala()
        self.arama_gosterge.setText(f"📌 Geçmiş Kayıt: {self.secili_sehir} {self.secili_kategori} • {len(self.tum_veriler)} Sonuç")
        QMessageBox.information(self.dialog, "Başarılı", "Geçmiş veriler ana ekrana yüklendi. Şimdi kontrol edebilir veya Excel'e aktarabilirsiniz!")
        self.dialog.accept()

    def otomatik_lisans_denetle(self):
        if os.path.exists(LISANS_DOSYASI):
            try:
                with open(LISANS_DOSYASI, "r") as f: kayitli_key = f.read().strip()
                durum, mesaj = lisans_kontrol_et(kayitli_key)
                if durum is True: self.kalan_hakki_guncelle()
                elif durum is False: 
                    self.lisans_timer.stop() 
                    if hasattr(self, 'isci') and self.isci.isRunning(): self.isci.durdur() 
                    try: os.remove(LISANS_DOSYASI) 
                    except: pass
                    QMessageBox.critical(self, "Erişim Kapatıldı", f"Güvenlik İhlali veya Süre Sonu!\n\n{mesaj}")
                    sys.exit() 
            except: pass

    def menuleri_olustur(self):
        self.menuBar().clear()
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("background-color: #1a0f2e; color: white; font-weight: bold; border: none;")
        
        dosya_menu = menu_bar.addMenu("📁 Dosya")
        excel_action = QAction("📊 Excel'e Aktar", self)
        excel_action.triggered.connect(self.excel_kaydet)
        dosya_menu.addAction(excel_action)
        hafiza_action = QAction("🧹 Tarama Hafızasını Sıfırla", self)
        hafiza_action.triggered.connect(self.hafizayi_temizle)
        dosya_menu.addAction(hafiza_action)
        cikis_action = QAction("❌ Çıkış", self)
        cikis_action.triggered.connect(self.close)
        dosya_menu.addAction(cikis_action)
        
        gorunum_menu = menu_bar.addMenu("🎨 Görünüm")
        tema_mor = QAction("🟣 Koyu Mor (Varsayılan)", self)
        tema_mor.triggered.connect(lambda: self.tema_uygula("Koyu Mor"))
        gorunum_menu.addAction(tema_mor)
        tema_mavi = QAction("🔵 Gece Mavisi", self)
        tema_mavi.triggered.connect(lambda: self.tema_uygula("Gece Mavisi"))
        gorunum_menu.addAction(tema_mavi)
        tema_yesil = QAction("🟢 Matrix Yeşili", self)
        tema_yesil.triggered.connect(lambda: self.tema_uygula("Matrix Yeşili"))
        gorunum_menu.addAction(tema_yesil)
        tema_kirmizi = QAction("🔴 Yakut Kırmızısı", self)
        tema_kirmizi.triggered.connect(lambda: self.tema_uygula("Yakut Kırmızısı"))
        gorunum_menu.addAction(tema_kirmizi)
        gorunum_menu.addSeparator() 
        tema_charcoal = QAction("🌑 Kömür Siyahı (Minimalist)", self)
        tema_charcoal.triggered.connect(lambda: self.tema_uygula("Kömür Siyahı"))
        gorunum_menu.addAction(tema_charcoal)
        tema_ocean = QAction("🌊 Okyanus Turkuazı", self)
        tema_ocean.triggered.connect(lambda: self.tema_uygula("Okyanus Turkuazı"))
        gorunum_menu.addAction(tema_ocean)
        tema_sunset = QAction("🌅 Gün Batımı (Kehribar)", self)
        tema_sunset.triggered.connect(lambda: self.tema_uygula("Gün Batımı"))
        gorunum_menu.addAction(tema_sunset)
        tema_rose = QAction("🌸 Gül Pembesi (Vibrant)", self)
        tema_rose.triggered.connect(lambda: self.tema_uygula("Gül Pembesi"))
        gorunum_menu.addAction(tema_rose)
        
        yardim_menu = menu_bar.addMenu("ℹ️ Yardım")
        lisans_action = QAction("🔑 Lisans Durumum", self)
        lisans_action.triggered.connect(self.lisans_bilgisi_goster)
        yardim_menu.addAction(lisans_action)

    def hafizayi_temizle(self):
        cevap = QMessageBox.question(self, "Hafızayı Sıfırla", "Daha önce taranmış işletmelerin hafızası silinecektir. Emin misiniz?", QMessageBox.Yes | QMessageBox.No)
        if cevap == QMessageBox.Yes:
            if os.path.exists(HAFIZA_DOSYASI):
                try: os.remove(HAFIZA_DOSYASI)
                except: pass
            self.kalan_hakki_guncelle()
            QMessageBox.information(self, "Başarılı", "Hafıza sıfırlandı!")

    def tema_uygula(self, tema_adi):
        if tema_adi == "Koyu Mor": self.aktif_tema = {"bg": "#0f071c", "panel": "#1e1136", "border": "#4a2b7a", "vurgu": "#8a2be2", "text": "white"}
        elif tema_adi == "Gece Mavisi": self.aktif_tema = {"bg": "#0a1128", "panel": "#14213d", "border": "#1f3b73", "vurgu": "#2196f3", "text": "white"}
        elif tema_adi == "Matrix Yeşili": self.aktif_tema = {"bg": "#051207", "panel": "#0a2411", "border": "#13421e", "vurgu": "#00e676", "text": "white"}
        elif tema_adi == "Yakut Kırmızısı": self.aktif_tema = {"bg": "#1f0508", "panel": "#330b10", "border": "#59141e", "vurgu": "#e53935", "text": "white"}
        elif tema_adi == "Kömür Siyahı": self.aktif_tema = {"bg": "#121212", "panel": "#1e1e1e", "border": "#333333", "vurgu": "#888888", "text": "#E0E0E0"}
        elif tema_adi == "Okyanus Turkuazı": self.aktif_tema = {"bg": "#001f1f", "panel": "#003333", "border": "#004d4d", "vurgu": "#00ffff", "text": "#e0ffff"}
        elif tema_adi == "Gün Batımı": self.aktif_tema = {"bg": "#1f1400", "panel": "#332100", "border": "#4d3200", "vurgu": "#ffbf00", "text": "#fff8e0"}
        elif tema_adi == "Gül Pembesi": self.aktif_tema = {"bg": "#1c000f", "panel": "#33001a", "border": "#4d0026", "vurgu": "#ff007f", "text": "#ffe0ef"}

        t_bg = self.aktif_tema["bg"]; t_panel = self.aktif_tema["panel"]
        t_border = self.aktif_tema["border"]; t_vurgu = self.aktif_tema["vurgu"]; t_txt = self.aktif_tema["text"]

        if hasattr(self, 'harita_view'): self.harita_view.page().runJavaScript(f"setVurguRengi('{t_vurgu}');")
        self.setStyleSheet(f"background-color: {t_bg}; color: {t_txt};")
        if hasattr(self, 'arama_gosterge'): self.arama_gosterge.setStyleSheet(f"color: {t_vurgu}; margin-bottom: 2px; border: none;")
        if hasattr(self, 'harita_view'): self.harita_view.setStyleSheet(f"border-radius: 4px; border: 1px solid {t_border};")
        if hasattr(self, 'orta_panel'): self.orta_panel.setStyleSheet(f"background-color: {t_panel}; border-radius: 6px; border: none;")
        
        input_stil = f"background-color: {t_bg}; color: {t_txt}; padding: 4px; border-radius: 3px; border: 1px solid {t_border};"
        if hasattr(self, 'sehir_combo'): self.sehir_combo.setStyleSheet(input_stil)
        if hasattr(self, 'sehir_input'): self.sehir_input.setStyleSheet(input_stil)
        if hasattr(self, 'kategori_input'): self.kategori_input.setStyleSheet(f"background-color: {t_bg}; color: {t_txt}; padding: 4px; border-radius: 3px; border: 1px solid {t_vurgu};")
        if hasattr(self, 'siralama_combo'): self.siralama_combo.setStyleSheet(f"background-color: {t_bg}; color: #00e676; padding: 4px; border-radius: 3px; border: 1px solid #00e676; font-weight: bold;")
        if hasattr(self, 'limit_box'): self.limit_box.setStyleSheet(f"background-color: {t_bg}; color: white; padding: 2px; border: 1px solid {t_border}; font-weight: bold;")
        if hasattr(self, 'proxy_input'): self.proxy_input.setStyleSheet(f"background-color: {t_bg}; color: white; padding: 2px; border: 1px solid {t_border}; font-weight: bold;")
        if hasattr(self, 'wp_sablon'): self.wp_sablon.setStyleSheet(f"background-color: {t_bg}; color: {t_txt}; padding: 4px; border-radius: 3px; border: 1px solid {t_vurgu};")
        
        if hasattr(self, 'scroll_area'): self.scroll_area.setStyleSheet(f"QScrollArea {{ border: none; background-color: transparent; }} QScrollBar:vertical {{ background: {t_panel}; width: 8px; border-radius: 4px; }} QScrollBar::handle:vertical {{ background: {t_border}; border-radius: 4px; }}")
        if hasattr(self, 'kalan_hak_lbl'): self.kalan_hak_lbl.setStyleSheet(f"background-color: {t_vurgu}; color: white; padding: 10px; border-radius: 4px; border: none;")
        if hasattr(self, 'btn_ara'):
            if self.btn_ara.isEnabled(): self.btn_ara.setStyleSheet(f"background-color: {t_vurgu}; color: white; padding: 10px; border-radius: 4px; border: none;")
            else: self.btn_ara.setStyleSheet(f"background-color: {t_border}; color: white; padding: 10px; border-radius: 4px; border: none;")

        if hasattr(self, 'filtre_grup'):
            self.filtre_grup.setStyleSheet(f"background-color: {t_bg}; border: 1px solid {t_border}; border-radius: 4px;")
            stil_chk = f"""QCheckBox {{ color: {t_txt}; font-weight: bold; font-size: 11px; padding: 0px; margin: 0px; border: none; background: transparent; }} QCheckBox::indicator {{ width: 14px; height: 14px; background-color: transparent; border: 1px solid {t_border}; border-radius: 3px; }} QCheckBox::indicator:checked {{ background-color: {t_vurgu}; border: 1px solid {t_vurgu}; }}"""
            self.chk_tel.setStyleSheet(stil_chk)
            self.chk_wa.setStyleSheet(stil_chk)
            self.chk_email.setStyleSheet(stil_chk)
            self.chk_sosyal.setStyleSheet(stil_chk)
            for child in self.filtre_grup.findChildren(QLabel): child.setStyleSheet(f"color: {t_vurgu}; font-weight: bold; font-size: 11px; border: none; background: transparent;")

        if self.tum_veriler: self.kartlari_sirala()
        self.kategori_buton_basildi(self.secili_kategori)

    def lisans_bilgisi_goster(self):
        if os.path.exists(LISANS_DOSYASI):
            with open(LISANS_DOSYASI, "r") as f: kayitli_key = f.read().strip()
            durum, mesaj = lisans_kontrol_et(kayitli_key)
            hwid = get_hwid()
            QMessageBox.information(self, "Lisans Bilgileri", f"💻 Makine ID'niz:\n{hwid}\n\nℹ️ Abonelik Durumu:\n{mesaj}\n\n✨ Created by EC Ajans")

    def ozel_kategori_yazildi(self):
        metin = self.kategori_input.text().strip()
        if metin:
            self.secili_kategori = metin
            t_bg = self.aktif_tema["bg"]; t_border = self.aktif_tema["border"]
            for ad, btn in self.kategori_butonlari: btn.setStyleSheet(f"background-color: {t_bg}; border: 1px solid {t_border}; padding: 4px; border-radius: 3px; color: #ffffff; font-weight: bold; font-size: 10px;")
            self.arama_metni_guncelle()

    def kategori_buton_basildi(self, kategori_adi):
        self.kategori_input.blockSignals(True)
        self.kategori_input.clear()
        self.kategori_input.blockSignals(False)
        self.secili_kategori = kategori_adi
        t_bg = self.aktif_tema["bg"]; t_border = self.aktif_tema["border"]; t_vurgu = self.aktif_tema["vurgu"]
        for ad, btn in self.kategori_butonlari:
            if ad == kategori_adi: btn.setStyleSheet(f"background-color: {t_vurgu}; border: 1px solid #fff; padding: 4px; border-radius: 3px; color: white; font-weight: bold; font-size: 10px;")
            else: btn.setStyleSheet(f"background-color: {t_bg}; border: 1px solid {t_border}; padding: 4px; border-radius: 3px; color: #ffffff; font-weight: bold; font-size: 10px;")
        self.arama_metni_guncelle()

    def filtrelenmis_verileri_getir(self):
        filtrelenmis_liste = []
        for veri in self.tum_veriler:
            gecerli = True
            if self.chk_tel.isChecked() and veri[2] == "-": gecerli = False
            if self.chk_wa.isChecked():
                if veri[2] == "-": gecerli = False
                else:
                    tel_temiz = re.sub(r'\D', '', veri[2])
                    is_wa = (tel_temiz.startswith("905") and len(tel_temiz) == 12) or (tel_temiz.startswith("05") and len(tel_temiz) == 11) or (tel_temiz.startswith("5") and len(tel_temiz) == 10)
                    if not is_wa: gecerli = False
            if self.chk_email.isChecked() and (len(veri) <= 4 or veri[4] == "-"): gecerli = False
            if self.chk_sosyal.isChecked() and (len(veri) <= 5 or veri[5] == "-"): gecerli = False
            if gecerli: filtrelenmis_liste.append(veri)
        return filtrelenmis_liste

    def arama_metni_guncelle(self):
        sehir = self.sehir_input.text().strip() or self.sehir_combo.currentText()
        meslek = self.kategori_input.text().strip() or self.secili_kategori
        if "✅" not in self.arama_gosterge.text():
            filtrelenmis_sayi = len(self.filtrelenmis_verileri_getir())
            if filtrelenmis_sayi == len(self.tum_veriler): self.arama_gosterge.setText(f"{sehir} {meslek} • {len(self.tum_veriler)} Sonuç")
            else: self.arama_gosterge.setText(f"{sehir} {meslek} • {len(self.tum_veriler)} Sonuç (Filtrelenen: {filtrelenmis_sayi})")

    def arayuzu_temizle(self):
        for i in reversed(range(self.kartlar_layout.count())): 
            w = self.kartlar_layout.itemAt(i).widget()
            self.kartlar_layout.removeWidget(w)
            w.setParent(None)
        self.tum_veriler.clear()

    def kartlari_sirala(self):
        if not hasattr(self, 'tum_veriler') or not self.tum_veriler: return
        for i in reversed(range(self.kartlar_layout.count())): self.kartlar_layout.itemAt(i).widget().setParent(None)
        sirali_liste = self.filtrelenmis_verileri_getir()
        secim = self.siralama_combo.currentText()
        if secim == "Filtre: Puan (En Yüksek)":
            def get_puan(v):
                try: return float(v[6].replace(',', '.'))
                except: return 0.0
            sirali_liste.sort(key=get_puan, reverse=True)
        elif secim == "Filtre: Alfabetik (A-Z)": sirali_liste.sort(key=lambda x: str(x[0]).lower())
            
        wp_icerik = self.wp_sablon.text().strip() if hasattr(self, 'wp_sablon') else ""
        for index, veri in enumerate(sirali_liste): self.kartlar_layout.addWidget(IsletmeKarti(index + 1, veri, wp_icerik, self.aktif_tema["vurgu"]))
        self.arama_metni_guncelle()

    def botu_baslat(self):
        if os.path.exists(LISANS_DOSYASI):
            with open(LISANS_DOSYASI, "r") as f: kayitli_key = f.read().strip()
            durum, mesaj = lisans_kontrol_et(kayitli_key)
            if durum is False: 
                QMessageBox.critical(self, "Erişim Engellendi", mesaj)
                try: os.remove(LISANS_DOSYASI)
                except: pass
                sys.exit() 
            elif durum is None: 
                QMessageBox.warning(self, "Bağlantı Hatası", mesaj)
                return 

        if "✅" in self.arama_gosterge.text(): self.arama_gosterge.setText("")
        if self.height() < 450: self.resize(self.width(), 700)
        manuel_meslek = self.kategori_input.text().strip()
        if manuel_meslek != "": self.secili_kategori = manuel_meslek
        elif not self.secili_kategori: self.secili_kategori = "Tümü"
        manuel_sehir = self.sehir_input.text().strip()
        self.secili_sehir = manuel_sehir if manuel_sehir != "" else self.sehir_combo.currentText()

        self.arama_metni_guncelle()
        if not icerik_guvenli_mi(self.secili_sehir) or not icerik_guvenli_mi(self.secili_kategori):
            QMessageBox.warning(self, "Güvenlik İhlali", "Uygunsuz kelimeler tespit edildi!")
            self.arayuzu_temizle(); self.kategori_input.clear(); self.sehir_input.clear(); self.kategori_buton_basildi("Avukat")
            return

        self.arayuzu_temizle()
        self.siralama_combo.setCurrentIndex(0) 
        self.btn_ara.setEnabled(False)
        self.btn_durdur.setEnabled(True) 
        self.btn_ara.setText("⏳ Arama Yapılıyor...")
        self.btn_ara.setStyleSheet(f"background-color: {self.aktif_tema['border']}; color: white; padding: 10px; border-radius: 4px; border: none;")
        
        aktif_proxy = self.proxy_input.text().strip()
        self.isci = HaritalarBotuIsci(self.secili_sehir, self.secili_kategori, self.limit_box.value(), aktif_proxy, self.sehir_combo.currentText())
        self.isci.yeni_satir_sinyali.connect(self.yeni_kart_ekle)
        self.isci.durum_sinyali.connect(self.durum_lbl.setText)
        self.isci.konum_sinyali.connect(lambda i, s: self.harita_view.page().runJavaScript(f"setLocation('{i}', '{s}');"))
        self.isci.bitti_sinyali.connect(self.bot_bitti)
        self.isci.start()

    def botu_durdur(self):
        if hasattr(self, 'isci') and self.isci.isRunning():
            self.isci.durdur() 
            self.btn_ara.setEnabled(True)
            self.btn_durdur.setEnabled(False)
            self.btn_durdur.setText("🛑 ARAMAYI DURDUR")
            self.btn_ara.setText("🚀 YENİ ARAMA BAŞLAT")
            self.btn_ara.setStyleSheet(f"background-color: {self.aktif_tema['vurgu']}; color: white; padding: 10px; border-radius: 4px; border: none;")
            self.durum_lbl.setText("Arama işlemi durduruluyor, lütfen bekleyin...")

    def yeni_kart_ekle(self, veri_listesi):
        self.tum_veriler.append(veri_listesi)
        guncel_key = ""
        if os.path.exists(LISANS_DOSYASI):
            try:
                with open(LISANS_DOSYASI, "r") as f: guncel_key = f.read().strip()
            except: pass
        if guncel_key: increment_key_progress(guncel_key)
            
        filtreler_aktif_mi = self.chk_tel.isChecked() or self.chk_wa.isChecked() or self.chk_email.isChecked() or self.chk_sosyal.isChecked()
        if self.siralama_combo.currentIndex() == 0 and not filtreler_aktif_mi:
            wp_icerik = self.wp_sablon.text().strip()
            self.kartlar_layout.addWidget(IsletmeKarti(len(self.tum_veriler), veri_listesi, wp_icerik, self.aktif_tema["vurgu"]))
            self.arama_metni_guncelle()
        else: self.kartlari_sirala()
        self.kalan_hakki_guncelle()

    def bot_bitti(self, mesaj):
        self.btn_ara.setEnabled(True)
        self.btn_durdur.setEnabled(False)
        self.btn_durdur.setText("🛑 ARAMAYI DURDUR")
        self.btn_ara.setText("🚀 YENİ ARAMA BAŞLAT")
        self.btn_ara.setStyleSheet(f"background-color: {self.aktif_tema['vurgu']}; color: white; padding: 10px; border-radius: 4px; border: none;")
        if self.siralama_combo.currentIndex() != 0: self.kartlari_sirala()
        
        if len(self.tum_veriler) > 0 and "SİST_HATASI:" not in mesaj: gecmisi_kaydet(self.secili_sehir, self.secili_kategori, len(self.tum_veriler), self.tum_veriler)

        if "SİST_HATASI:" in mesaj: 
            self.durum_lbl.setText("Sistem Hatası Oluştu!")
            QMessageBox.critical(self, "Kritik Tarama Hatası", mesaj[:1000])
        elif "KOTA_LIMITI:" in mesaj:
            self.durum_lbl.setText("Abonelik Kotanız Dolmuştur!")
            QMessageBox.warning(self, "Abonelik Sınırı", mesaj.replace("KOTA_LIMITI: ", ""))
        else:
            self.durum_lbl.setText(mesaj)
            QMessageBox.information(self, "Bilgi", mesaj)
        self.kalan_hakki_guncelle()

    def vcf_kaydet(self):
        kaydedilecek_veriler = self.filtrelenmis_verileri_getir()
        if not kaydedilecek_veriler:
            QMessageBox.warning(self, "Hata", "Kaydedilecek telefon numarası bulunamadı!")
            return
            
        dosya, _ = QFileDialog.getSaveFileName(self, "Rehbere Kaydet (VCF)", f"{self.secili_sehir}_{self.secili_kategori}_Rehber", "vCard Files (*.vcf)")
        if dosya:
            try:
                kisi_sayisi = 0
                with open(dosya, "w", encoding="utf-8") as f:
                    for veri in kaydedilecek_veriler:
                        isim = veri[0].replace(';', ' ')
                        tel = veri[2]
                        if tel != "-":
                            tel_temiz = re.sub(r'\D', '', tel)
                            wa_no = ""
                            if tel_temiz.startswith("905") and len(tel_temiz) == 12: wa_no = "+" + tel_temiz
                            elif tel_temiz.startswith("05") and len(tel_temiz) == 11: wa_no = "+90" + tel_temiz[1:]
                            elif tel_temiz.startswith("5") and len(tel_temiz) == 10: wa_no = "+90" + tel_temiz
                            else: wa_no = tel
                            
                            f.write("BEGIN:VCARD\nVERSION:3.0\n")
                            f.write(f"FN:{isim}\n")
                            f.write(f"TEL;TYPE=CELL:{wa_no}\n")
                            f.write("END:VCARD\n")
                            kisi_sayisi += 1
                if kisi_sayisi > 0: QMessageBox.information(self, "Başarılı", f"Toplam {kisi_sayisi} işletme telefon rehberi (VCF) formatında kaydedildi!\n\nDosyayı telefonunuza atıp tek tıkla tüm numaraları WhatsApp/Rehber'inize ekleyebilirsiniz.")
                else: QMessageBox.warning(self, "Uyarı", "Listedeki işletmelerde geçerli cep telefonu numarası bulunamadı.")
            except Exception as e: QMessageBox.critical(self, "Hata", f"Rehber dosyası oluşturulamadı.\nDetay: {str(e)}")

    def excel_kaydet(self):
        if not self.btn_ara.isEnabled():
            QMessageBox.warning(self, "Hata", "Arama devam ederken kayıt yapılamaz!")
            return
        kaydedilecek_veriler = self.filtrelenmis_verileri_getir()
        if not kaydedilecek_veriler:
            QMessageBox.warning(self, "Hata", "Şu anki filtreleme ayarlarına göre kaydedilecek veri bulunamadı!")
            return
            
        dosya, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", f"{self.secili_sehir}_{self.secili_kategori}_Liste", "Excel (*.xlsx)")
        if dosya:
            try:
                import openpyxl
                import re
                wb = openpyxl.Workbook(); ws = wb.active
                ws.append(["İsim", "Adres", "Telefon", "Website", "Email", "Sosyal Medya", "Puan", "Harita Linki"])
                
                for veri in kaydedilecek_veriler:
                    if len(veri) >= 8:
                        temiz_satir = []
                        for i, hucre in enumerate(veri[:8]):
                            if i == 5 and hucre != "-": 
                                linkler = re.findall(r'href="([^"]+)"', hucre)
                                if linkler: temiz_satir.append(" | ".join(linkler))
                                else: temiz_satir.append(hucre)
                            else: temiz_satir.append("" if hucre == "-" else hucre)
                        ws.append(temiz_satir)
                        
                wb.save(dosya)
                QMessageBox.information(self, "Başarılı", f"Toplam {len(kaydedilecek_veriler)} adet veri Excel dosyasına saf ve temiz bir şekilde kaydedildi!")
            except Exception as e: QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi.\nDetay: {str(e)}")

if __name__ == "__main__":
    if hasattr(Qt, 'AA_ShareOpenGLContexts'): QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ana_uygulama = InfoFinderApp()
    ana_uygulama.show()
    sys.exit(app.exec_())