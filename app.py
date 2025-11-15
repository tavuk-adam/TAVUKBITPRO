# TAVUKBIT Borsa ve Hesap Yönetim Simülasyonu (Flask)
# Veri Kalıcılığı için JSONBin.io Entegrasyonu kullanılmıştır.

import random
import threading
import time
import os       
import requests 
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# Flask uygulamasını başlatma
app = Flask(__name__)
app.secret_key = "gizli_tavuk"

# Ortak kaynaklara eş zamanlı erişimi yönetmek için kilit
lock = threading.Lock()

# --- JSONBin.io Yapılandırması (Çevre Değişkenleri) ---
API_KEY = os.environ.get("API_KEY") 
BIN_ID = os.environ.get("BIN_ID")
API_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}" if BIN_ID else None
HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": API_KEY 
}
# --- /JSONBin.io Yapılandırması ---

MAX_MEILLE_LEVEL = 25 

# BAŞLANGIÇ VERİLERİ (Tüm anahtarların listesi)
INITIAL_STATE = {
    "fiyat": 10,
    "dusme_meille_seviye": 0,
    "yukselme_meille_seviye": 0,
    "log_kaydi": ["🔄 Sunucu başlatıldı. Varsayılan veriler kullanıldı."],
    "users": {
        "admin": {'password': 'chicken123', 'elmas': 999999, 'tavukbit': 0, 'is_admin': True},
        "testuser": {'password': '123', 'elmas': 10000, 'tavukbit': 0, 'is_admin': False}
    }
}

# --- Kalıcı Depolama Fonksiyonları (İnternet Üzerinden) ---

def load_data():
    """
    İnternetteki JSON deposundan verileri yükler. 
    API'den gelen veriyi INITIAL_STATE ile birleştirerek eksik anahtar hatalarını önler.
    """
    global INITIAL_STATE
    
    if not API_KEY or not BIN_ID:
        print("UYARI: API Anahtarları ayarlanmamış. Varsayılan veriler kullanılıyor.")
        return INITIAL_STATE.copy()
        
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status() 
        api_record = response.json().get('record', {})
        
        # Ana durumu (INITIAL_STATE) kopyala
        loaded_data = INITIAL_STATE.copy()
        
        # API'den gelen veriyi güvenli bir şekilde ana durumun üzerine yaz
        # Bu, API'den gelen veri eksik olsa bile KeyError vermeyi engeller.
        loaded_data.update(api_record)
        
        # Özellikle 'users' sözlüğünü derinlemesine güncelle (Varsayılan admin/testuser'ı korumak için)
        if 'users' not in loaded_data or not isinstance(loaded_data['users'], dict):
             loaded_data['users'] = {}

        # Başlangıç kullanıcılarını ekle (Üzerine yazılmaz)
        for user_key, user_data in INITIAL_STATE['users'].items():
            if user_key not in loaded_data['users']:
                loaded_data['users'][user_key] = user_data
        
        loaded_data.get('log_kaydi', []).append("🔄 Sunucu yeniden başlatıldı. Veriler internetten yüklendi.")
        
        # Gerekli anahtarların varlığını son kez kontrol et (Bu durumda gerek kalmaz ama sağlamlık için iyidir)
        for key in INITIAL_STATE.keys():
            if key not in loaded_data:
                loaded_data[key] = INITIAL_STATE[key]

        return loaded_data
        
    except requests.exceptions.RequestException as e:
        error_info = f"{e}"
        if 'response' in locals() and hasattr(response, 'status_code'):
             error_info = f"{response.status_code} - {response.text}"
        print(f"HATA: Veri yüklenirken istek hatası oluştu. Varsayılan veriler kullanılıyor. Hata: {error_info}")
        return INITIAL_STATE.copy()
    except Exception as e:
        print(f"HATA: Veri yüklenirken beklenmeyen hata oluştu. Varsayılan veriler kullanılıyor. Hata: {e}")
        return INITIAL_STATE.copy()


def save_data():
    """Tüm önemli verileri internetteki JSON deposuna kaydeder."""
    if not API_KEY or not BIN_ID:
        return

    global fiyat, dusme_meille_seviye, yukselme_meille_seviye, users, log_kaydi
    
    # Logların sadece son 100 kaydını kaydederek depoyu temiz tutma
    data_to_save = {
        "fiyat": fiyat,
        "dusme_meille_seviye": dusme_meille_seviye,
        "yukselme_meille_seviye": yukselme_meille_seviye,
        "users": users,
        "log_kaydi": log_kaydi[-100:] 
    }
    
    try:
        # API'den gelen 401 hatası düzelmediyse, anahtarlarınızı kontrol edin!
        requests.put(API_URL, json=data_to_save, headers=HEADERS, timeout=10)
    except requests.exceptions.RequestException:
        pass

# --- Uygulama Başlangıcı: Verileri Yükle ---
# Hatanın meydana geldiği kısım, şimdi düzeltilmiş load_data ile daha güvenli
app_data = load_data()

# Global değişkenleri yüklenen verilerle başlatma
fiyat = app_data["fiyat"]
dusme_meille_seviye = app_data["dusme_meille_seviye"]
yukselme_meille_seviye = app_data["yukselme_meille_seviye"]
users = app_data["users"]
log_kaydi = app_data.get("log_kaydi", [])

# Logların sadece son 100 tanesini bellekte tut.
log_kaydi = log_kaydi[-100:]

# Simülasyon değişkenleri (Kalıcı değil, memory'de tutulur)
simulasyon_aktif = False 
kalan_sure = 0 


# Fiyat simülasyonu fonksiyonu
def simulasyonu_baslat(sure, baslangic=None):
    """
    Simülasyonu başlatan fonksiyon. Belirtilen süre boyunca her saniye fiyatı tam sayı olarak günceller.
    """
    global fiyat, log_kaydi, simulasyon_aktif, kalan_sure
    global dusme_meille_seviye, yukselme_meille_seviye

    with lock:
        if baslangic and isinstance(baslangic, int) and baslangic >= 1:
            fiyat = baslangic

        if fiyat < 1:
            fiyat = 10

        if simulasyon_aktif:
            log_kaydi.append("⚠️ Simülasyon zaten aktif! Yeni süre eklendi.")
            kalan_sure += sure
            save_data() 
            return

        simulasyon_aktif = True
        kalan_sure = sure

    # Simülasyonu arka planda çalıştır
    threading.Thread(target=_simulasyon_dongusu, args=(sure,), daemon=True).start()

def _simulasyon_dongusu(sure):
    global fiyat, log_kaydi, simulasyon_aktif, kalan_sure
    global dusme_meille_seviye, yukselme_meille_seviye
    
    for saniye in range(1, sure + 1):
        time.sleep(1)
        with lock:
            if not simulasyon_aktif:
                log_kaydi.append("⏹ Simülasyon erken durduruldu.")
                break
                
            # Olasılıklar: -2, -1, 0, 1, 2
            olasiliklar = [-2, -1, 0, 1, 2]
            agirliklar = [1, 1, 1, 1, 1]

            # Olasılık ayar seviyesini ağırlıklara ekle (Max 25)
            if dusme_meille_seviye > 0:
                agirliklar[0] += dusme_meille_seviye
                agirliklar[1] += dusme_meille_seviye

            if yukselme_meille_seviye > 0:
                agirliklar[3] += yukselme_meille_seviye
                agirliklar[4] += yukselme_meille_seviye

            secim = random.choices(olasiliklar, weights=agirliklar, k=1)[0]

            yeni_fiyat = fiyat + secim
            fiyat = max(1, yeni_fiyat)
            
            save_data() # <<< HER TİKTE KAYDET

            log_kaydi.append(
                f"📈 PİYASA | Fiyat: {fiyat} Elmas (Değişim: {secim:+.0f}) (D: {dusme_meille_seviye}/{MAX_MEILLE_LEVEL}, Y: {yukselme_meille_seviye}/{MAX_MEILLE_LEVEL})")

            kalan_sure -= 1

    with lock:
        simulasyon_aktif = False
        kalan_sure = 0
        log_kaydi.append("⏹ Simülasyon durdu.")
        save_data() # <<< SİMÜLASYON DURDUĞUNDA KAYDET

# HTML şablonu (Kullanıcının sağladığı UI)
HTML = '''
<!doctype html>
<html lang="tr" data-bs-theme="auto">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TAVUKBIT Simülasyonu 🚀</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <style>
        /* Dark/Light Mode CSS Değişkenleri */
        :root, [data-bs-theme="light"] {
            --bs-body-bg: #f0f4f8;
            --bs-body-color: #1e293b;
            --card-bg: #ffffff;
            --log-bg: #e9ecef;
        }
        [data-bs-theme="dark"] {
            --bs-body-bg: #0f172a;
            --bs-body-color: #f1f5f9;
            --card-bg: #1e293b;
            --log-bg: #0f172a;
        }
        body { 
            background-color: var(--bs-body-bg); 
            color: var(--bs-body-color); 
            font-family: 'Inter', sans-serif;
            transition: background-color 0.3s;
        }
        .card {
            background-color: var(--card-bg); 
            border: none;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
            transition: background-color 0.3s, box-shadow 0.3s;
        }
        [data-bs-theme="dark"] .card {
             box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        }
        .fiyat { 
            font-size: 3.5rem; 
            font-weight: 800;
            transition: color 0.5s;
            line-height: 1;
        }
        .log-container { 
            background: var(--log-bg); 
            color: var(--bs-body-color); 
            padding: 15px; 
            height: 700px; /* Geniş ekrana uygun yüksek log alanı */
            overflow-y: scroll; 
            font-family: monospace; 
            border-radius: 0.5rem;
            border: 1px solid var(--bs-border-color-translucent);
            font-size: 0.85rem;
        }
        .balance-box {
            background-color: var(--bs-primary);
            color: var(--bs-white);
            padding: 15px;
            border-radius: 0.5rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        [data-bs-theme="dark"] .balance-box {
            background-color: var(--bs-info);
            color: var(--bs-dark);
        }
    </style>
</head>
<body class="container-fluid py-5">

    <div class="d-flex justify-content-between align-items-center mb-4 px-3">
        <h1 class="text-warning mb-0"><i class="bi bi-coin me-2"></i> TAVUKBIT Borsa Simülatörü <i class="bi bi-currency-bitcoin"></i></h1>
        <button id="theme-toggle" class="btn btn-sm btn-outline-secondary">
            <i class="bi bi-sun" id="theme-icon"></i> Tema Değiştir
        </button>
    </div>

    <div class="row justify-content-center">
        <div class="col-12 col-xl-11"> 
            <div class="row g-4">

                <div class="col-lg-6 col-xl-7">

                    {% if not session.get("giris_tavuk") %}
                        <div class="card p-5 shadow-lg border-0">
                            <h4 class="card-title text-center text-primary mb-4"><i class="bi bi-lock me-2"></i> Simülasyona Giriş</h4>
                            <p class="text-center text-muted">Mevcut Fiyat: <span class="fiyat text-success">{{ fiyat }}</span> Elmas</p>
                            <form method="post" action="/login" class="mt-4">
                                <div class="form-floating mb-3">
                                    <input type="text" id="username" name="username" class="form-control" placeholder="Kullanıcı Adı" required>
                                    <label for="username"><i class="bi bi-person me-2"></i> Kullanıcı Adı</label>
                                </div>
                                <div class="form-floating mb-4">
                                    <input type="password" id="password" name="password" class="form-control" placeholder="Şifre" required>
                                    <label for="password"><i class="bi bi-key me-2"></i> Şifre</label>
                                </div>
                                <button type="submit" class="btn btn-primary btn-lg w-100 shadow"><i class="bi bi-box-arrow-in-right me-2"></i> Giriş Yap</button>
                            </form>
                            <p class="text-center text-muted mt-3 mb-0 small">
                                (admin ve testuser hesapları otomatik oluştur)
                            </p>
                        </div>
                    {% else %}

                        <div class="card p-4 mb-4">
                            <div class="d-flex justify-content-between align-items-start mb-3 border-bottom pb-3">
                                <h4 class="card-title text-primary mb-0">
                                    {% if user_data.is_admin %}
                                        👑 YÖNETİCİ PANELİ
                                    {% else %}
                                        <i class="bi bi-speedometer2 me-2"></i> {{ user_data.username | upper }} TİCARET EKRANI
                                    {% endif %}
                                </h4>
                                <a href="/logout" class="btn btn-sm btn-outline-danger"><i class="bi bi-door-open me-1"></i> Çıkış Yap</a>
                            </div>

                            <div class="row align-items-center bg-light-subtle rounded p-3">
                                <div class="col-4 border-end border-secondary">
                                    <p class="mb-0 text-muted small">AKTİF FİYAT:</p>
                                    <div class="fiyat text-success" id="fiyat" data-last-fiyat="{{ fiyat }}">{{ fiyat }}</div>
                                    <p class="text-muted mt-1 mb-0 small">Elmas</p>
                                </div>
                                <div class="col-4 text-center border-end border-secondary">
                                    <p class="mb-1 fw-bold small">Durum:</p>
                                    <h5 class="mb-0" id="durum">{{ durum }}</h5>
                                </div>
                                <div class="col-4 text-center">
                                    <p class="mb-1 fw-bold small">Kalan Süre:</p>
                                    <h5 class="mb-0 text-warning" id="kalan_sure">{{ kalan_sure }} sn</h5>
                                </div>
                            </div>
                        </div>

                        {% if not user_data.is_admin %}
                            <div class="card p-4 mb-4">
                                <h5 class="card-title text-info mb-3"><i class="bi bi-wallet2 me-2"></i> Bakiye Durumu</h5>
                                <div class="row text-center mb-4 g-2">
                                    <div class="col balance-box me-2">
                                        <p class="mb-1 text-light small opacity-75">Elmas (💎)</p>
                                        <h4 class="text-white" id="user_elmas">{{ user_data.elmas }}</h4>
                                    </div>
                                    <div class="col balance-box">
                                        <p class="mb-1 text-light small opacity-75">TAVUKBIT (🐔)</p>
                                        <h4 class="text-white" id="user_tavukbit">{{ user_data.tavukbit }}</h4>
                                    </div>
                                </div>

                                <h5 class="card-title text-info mb-3"><i class="bi bi-graph-up me-2"></i> İşlem Yap</h5>
                                <div class="input-group mb-3">
                                    <span class="input-group-text"><i class="bi bi-hash"></i></span>
                                    <input type="number" id="trade_amount" class="form-control form-control-lg" placeholder="Miktar (Adet)" min="1" value="1">
                                </div>
                                <div class="d-grid gap-2 d-md-flex justify-content-md-start">
                                    <button id="buyBtn" class="btn btn-success btn-lg flex-grow-1 py-2 shadow-sm"><i class="bi bi-arrow-down-left me-2"></i> AL</button>
                                    <button id="sellBtn" class="btn btn-danger btn-lg flex-grow-1 py-2 shadow-sm"><i class="bi bi-arrow-up-right me-2"></i> SAT</button>
                                </div>
                                <div id="trade-message" class="mt-2 text-center fw-bold" style="min-height: 1.5rem;"></div>
                            </div>
                        {% else %}
                            <div class="card p-4 mb-4">
                                <h5 class="card-title text-info mb-3"><i class="bi bi-controller me-2"></i> Simülasyon Kontrolü</h5>
                                <div class="row g-3 mb-4">
                                    <div class="col-md-6">
                                        <label for="sure_input" class="form-label small text-muted">⏳ Simülasyon Süresi (5-120 sn):</label>
                                        <input type="number" id="sure_input" class="form-control" value="20" min="5" max="120">
                                    </div>
                                    <div class="col-md-6">
                                        <label for="baslangic_input" class="form-label small text-muted">💰 Başlangıç Fiyatı (Opsiyonel):</label>
                                        <input type="number" id="baslangic_input" class="form-control" placeholder="Mevcut fiyattan devam" min="1">
                                    </div>
                                </div>

                                <div class="d-grid gap-2 d-md-flex justify-content-md-start mb-4">
                                    <button id="devamBtn" class="btn btn-success btn-lg flex-grow-1 py-2"><i class="bi bi-play-fill me-2"></i> BAŞLAT / DEVAM ET</button>
                                    <button id="durdurBtn" class="btn btn-danger btn-lg flex-grow-1 py-2"><i class="bi bi-stop-fill me-2"></i> DURDUR</button>
                                </div>

                                <hr class="my-3">

                                <h5 class="card-title text-info mb-3"><i class="bi bi-sliders me-2"></i> Meilleştirme Seviyeleri (Max: {{ MAX_MEILLE_LEVEL }})</h5>
                                <div class="row align-items-center mb-3 p-2 rounded border border-warning-subtle">
                                    <div class="col-8">
                                        <span class="text-danger fw-bold"><i class="bi bi-arrow-down me-1"></i> Düşüş Olasılığını Artır:</span>
                                        <span class="meille-level text-danger fw-bold fs-5" id="dusme_seviye">{{ dusme_meille_seviye }}</span> / {{ MAX_MEILLE_LEVEL }}
                                    </div>
                                    <div class="col-4 d-flex justify-content-end">
                                        <button id="dusme_eksi" class="btn btn-sm btn-outline-secondary me-1" title="Azalt"><i class="bi bi-dash"></i></button>
                                        <button id="dusme_arti" class="btn btn-sm btn-danger" title="Artır"><i class="bi bi-plus"></i></button>
                                    </div>
                                </div>
                                <div class="row align-items-center mb-0 p-2 rounded border border-warning-subtle">
                                    <div class="col-8">
                                        <span class="text-success fw-bold"><i class="bi bi-arrow-up me-1"></i> Yükseliş Olasılığını Artır:</span>
                                        <span class="meille-level text-success fw-bold fs-5" id="yukselme_seviye">{{ yukselme_meille_seviye }}</span> / {{ MAX_MEILLE_LEVEL }}
                                    </div>
                                    <div class="col-4 d-flex justify-content-end">
                                        <button id="yukselme_eksi" class="btn btn-sm btn-outline-secondary me-1" title="Azalt"><i class="bi bi-dash"></i></button>
                                        <button id="yukselme_arti" class="btn btn-sm btn-success" title="Artır"><i class="bi bi-plus"></i></button>
                                    </div>
                                </div>
                            </div>

                            <div class="card p-4">
                                <h5 class="card-title text-primary mb-3"><i class="bi bi-person-plus me-2"></i> Yeni Hesap Oluşturma</h5>
                                <form id="register-form" class="row g-3">
                                    <div class="col-md-6">
                                        <label for="reg_username" class="form-label small text-muted">Kullanıcı Adı:</label>
                                        <input type="text" id="reg_username" class="form-control" required>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="reg_password" class="form-label small text-muted">Şifre:</label>
                                        <input type="password" id="reg_password" class="form-control" required>
                                    </div>
                                    <div class="col-12">
                                        <label for="reg_elmas" class="form-label small text-muted">Başlangıç Elmas Bakiyesi:</label>
                                        <input type="number" id="reg_elmas" class="form-control" value="10000" min="1" required>
                                    </div>
                                    <div class="col-12">
                                        <button type="submit" class="btn btn-primary w-100"><i class="bi bi-person-check me-2"></i> Kullanıcı Oluştur</button>
                                    </div>
                                </form>
                                <div id="register-message" class="mt-2 text-center fw-bold" style="min-height: 1.5rem;"></div>

                                <hr class="my-4">

                                <h5 class="card-title text-warning mb-3"><i class="bi bi-tools me-2"></i> Kullanıcı Bakiyesi Güncelleme</h5>
                                <form id="update-user-form">
                                    <div class="mb-3">
                                        <label for="upd_username" class="form-label small text-muted">Kullanıcı Adı:</label>
                                        <input type="text" id="upd_username" class="form-control" list="userlist" required>
                                        <datalist id="userlist">
                                            {% for user in users_list %}
                                                <option value="{{ user }}">
                                            {% endfor %}
                                        </datalist>
                                    </div>
                                    <div class="row mb-3 g-3">
                                        <div class="col-md-6">
                                            <label for="upd_elmas" class="form-label small text-muted">Yeni Elmas Bakiyesi:</label>
                                            <input type="number" id="upd_elmas" class="form-control" placeholder="Örn: 15000" min="0">
                                        </div>
                                        <div class="col-md-6">
                                            <label for="upd_tavukbit" class="form-label small text-muted">Yeni TAVUKBIT Miktarı:</label>
                                            <input type="number" id="upd_tavukbit" class="form-control" placeholder="Örn: 50" min="0">
                                        </div>
                                    </div>
                                    <button type="submit" class="btn btn-warning w-100"><i class="bi bi-arrow-repeat me-2"></i> Bakiyeyi Güncelle</button>
                                </form>
                                <div id="update-message" class="mt-2 text-center fw-bold" style="min-height: 1.5rem;"></div>
                            </div>
                        {% endif %}
                    {% endif %}

                </div>

                <div class="col-lg-6 col-xl-5">
                    <div class="card p-4 h-100">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="card-title text-info mb-0"><i class="bi bi-journal-text me-2"></i> İşlem Günlüğü (Log)</h5>
                            {% if session.get("is_admin") %}
                                <button id="temizleBtn" class="btn btn-sm btn-secondary"><i class="bi bi-eraser me-1"></i> Temizle</button>
                            {% endif %}
                        </div>
                        <pre class="log-container" id="log">{{ log }}</pre>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const MAX_MEILLE_LEVEL = {{ MAX_MEILLE_LEVEL }};

        // Dark/Light Mode Yönetimi
        function setStoredTheme(theme) {
            localStorage.setItem('theme', theme);
            document.documentElement.setAttribute('data-bs-theme', theme);
            updateThemeIcon(theme);
        }

        function getPreferredTheme() {
            const storedTheme = localStorage.getItem('theme');
            if (storedTheme) {
                return storedTheme;
            }
            return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }

        function updateThemeIcon(theme) {
            const icon = document.getElementById('theme-icon');
            if (icon) {
                icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
                icon.parentElement.innerHTML = '<i class="' + icon.className + ' me-1" id="theme-icon"></i> Tema Değiştir';
            }
        }

        // Sayfa yüklendiğinde temayı uygula
        window.addEventListener('DOMContentLoaded', () => {
            const preferredTheme = getPreferredTheme();
            setStoredTheme(preferredTheme);

            document.getElementById('theme-toggle').addEventListener('click', () => {
                const currentTheme = document.documentElement.getAttribute('data-bs-theme');
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                setStoredTheme(newTheme);
            });
        });

        // Hata ve başarı mesajlarını gösteren yardımcı fonksiyon
        function displayMessage(id, message, isError = false) {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = message;
                element.style.color = isError ? '#dc3545' : '#198754';
                setTimeout(() => element.textContent = '', 4000);
            }
        }

        // Her saniye sunucudan güncel verileri getiren fonksiyon
        function update() {
            fetch('/status').then(r => r.json()).then(data => {
                // Ortak Güncellemeler
                if(document.getElementById("fiyat")) {
                    const fiyatElement = document.getElementById("fiyat");
                    const lastFiyat = parseFloat(fiyatElement.dataset.lastFiyat || data.fiyat);
                    fiyatElement.textContent = data.fiyat;

                    // Fiyat rengini güncelle
                    fiyatElement.classList.remove('text-success', 'text-danger', 'text-warning');
                    if(data.fiyat > lastFiyat) {
                        fiyatElement.classList.add('text-success');
                    } else if (data.fiyat < lastFiyat) {
                        fiyatElement.classList.add('text-danger');
                    } else {
                        fiyatElement.classList.add('text-warning'); 
                    }
                    fiyatElement.dataset.lastFiyat = data.fiyat;
                }

                if(document.getElementById("durum")) document.getElementById("durum").textContent = data.durum;
                if(document.getElementById("kalan_sure")) document.getElementById("kalan_sure").textContent = data.kalan_sure + " sn";

                // Log güncellemeleri
                if(document.getElementById("log")) {
                    const logElement = document.getElementById("log");
                    // Eğer log en alttaysa, yeni gelen içeriğe kaydır.
                    const isScrolledToBottom = logElement.scrollHeight - logElement.clientHeight <= logElement.scrollTop + 1;
                    logElement.textContent = data.log;
                    if (isScrolledToBottom || logElement.textContent.trim() === '') {
                        logElement.scrollTop = logElement.scrollHeight;
                    }
                }

                // Admin Güncellemeleri
                if(document.getElementById("dusme_seviye")) document.getElementById("dusme_seviye").textContent = data.dusme_meille_seviye;
                if(document.getElementById("yukselme_seviye")) document.getElementById("yukselme_seviye").textContent = data.yukselme_meille_seviye;

                // Kullanıcı Güncellemeleri
                if(data.user_elmas !== undefined && document.getElementById("user_elmas")) {
                    document.getElementById("user_elmas").textContent = data.user_elmas;
                }
                if(data.user_tavukbit !== undefined && document.getElementById("user_tavukbit")) {
                    document.getElementById("user_tavukbit").textContent = data.user_tavukbit;
                }
            });
        }

        // Güncelleme fonksiyonunu her saniye çağırma
        setInterval(update, 1000);
        update();

        // Admin Simülasyon Kontrol Butonları
        if (document.getElementById("devamBtn")) {
            document.getElementById("devamBtn").onclick = () => {
                const sure = parseInt(document.getElementById("sure_input")?.value) || 20;
                const baslangic = parseInt(document.getElementById("baslangic_input")?.value);
                fetch('/devam', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ sure: sure, baslangic: baslangic })
                });
            };
        }
        if (document.getElementById("durdurBtn")) {
            document.getElementById("durdurBtn").onclick = () => fetch('/durdur', { method: 'POST' });
        }
        if (document.getElementById("temizleBtn")) {
            document.getElementById("temizleBtn").onclick = () => fetch('/temizle', { method: 'POST' });
        }

        // Meilleştirme Butonları (Olasılık Ayarları)
        if(document.getElementById("dusme_arti")) {
            document.getElementById("dusme_arti").onclick = () => fetch('/meille_dusme_artir', { method: 'POST' });
        }
        if(document.getElementById("dusme_eksi")) {
            document.getElementById("dusme_eksi").onclick = () => fetch('/meille_dusme_azalt', { method: 'POST' });
        }
        if(document.getElementById("yukselme_arti")) {
            document.getElementById("yukselme_arti").onclick = () => fetch('/meille_yukselme_artir', { method: 'POST' });
        }
        if(document.getElementById("yukselme_eksi")) {
            document.getElementById("yukselme_eksi").onclick = () => fetch('/meille_yukselme_azalt', { method: 'POST' });
        }

        // Admin Kullanıcı Yönetimi Form İşleyicileri
        function setupAdminForm(formId, url, successMessageId) {
            const form = document.getElementById(formId);
            if (!form) return;

            form.onsubmit = (e) => {
                e.preventDefault();
                const inputs = Array.from(form.elements).filter(el => el.type !== 'submit');
                const data = {};
                inputs.forEach(input => {
                    // ID'den prefix'i temizle ve veriyi hazırla
                    const key = input.id.replace(formId === 'register-form' ? 'reg_' : 'upd_', '');
                    if(input.value.trim() !== '') {
                        data[key] = input.type === 'number' ? parseInt(input.value) : input.value;
                    }
                });

                // Özel durumlar için kontrol
                if (formId === 'update-user-form') {
                    if (!data.elmas && !data.tavukbit) {
                        displayMessage(successMessageId, 'En az bir bakiye değeri güncellenmelidir.', true);
                        return;
                    }
                }

                fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                })
                .then(response => response.json().then(data => ({ status: response.status, body: data })))
                .then(result => {
                    if (result.status >= 200 && result.status < 300) {
                        displayMessage(successMessageId, result.body.message, false);
                        form.reset();
                    } else {
                        displayMessage(successMessageId, result.body.message, true);
                    }
                    update();
                })
                .catch(error => {
                     displayMessage(successMessageId, 'Sunucu hatası oluştu.', true);
                });
            };
        }

        setupAdminForm('register-form', '/admin/register', 'register-message');
        setupAdminForm('update-user-form', '/admin/update_user', 'update-message');


        // Kullanıcı Ticaret Fonksiyonu
        function handleTrade(action) {
            const amountInput = document.getElementById("trade_amount");
            const amount = parseInt(amountInput?.value);

            if (!amount || amount <= 0) {
                displayMessage('trade-message', 'Lütfen geçerli bir miktar girin.', true);
                return;
            }

            fetch('/trade', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ action: action, amount: amount })
            })
            .then(response => response.json().then(data => ({ status: response.status, body: data })))
            .then(result => {
                if (result.status === 200) {
                    displayMessage('trade-message', result.body.message, false);
                    amountInput.value = 1; 
                } else {
                    displayMessage('trade-message', result.body.message, true);
                }
            })
            .catch(error => {
                displayMessage('trade-message', 'İşlem sırasında sunucu hatası oluştu.', true);
                console.error('Trade error:', error);
            });
        }

        // Ticaret Butonları
        if(document.getElementById("buyBtn")) {
            document.getElementById("buyBtn").onclick = () => handleTrade('buy');
        }
        if(document.getElementById("sellBtn")) {
            document.getElementById("sellBtn").onclick = () => handleTrade('sell');
        }
    </script>
</body>
</html>
'''


# --- ROUTE TANIMLAMALARI ---

# Ana sayfa rotası
@app.route("/")
def index():
    user_data = None
    if session.get("username") and session.get("username") in users:
        current_user = users[session["username"]]
        user_data = {
            "elmas": current_user['elmas'],
            "tavukbit": current_user['tavukbit'],
            "is_admin": current_user['is_admin'],
            "username": session["username"]
        }

    users_list = list(users.keys())

    # Logları ters çevirip satır satır ayırarak gönder
    log_display = "\n".join(log_kaydi[::-1])

    return render_template_string(HTML,
                                  fiyat=fiyat, log=log_display,
                                  durum="🟢 AKTİF" if simulasyon_aktif else "🔴 DURDU",
                                  kalan_sure=kalan_sure,
                                  dusme_meille_seviye=dusme_meille_seviye,
                                  yukselme_meille_seviye=yukselme_meille_seviye,
                                  session=session,
                                  user_data=user_data,
                                  users_list=users_list,
                                  MAX_MEILLE_LEVEL=MAX_MEILLE_LEVEL)


# Durum güncelleme rotası (AJAX)
@app.route("/status")
def status():
    # log_kaydi'nı ters çevirip son 50 kaydı gönder
    log_display = "\n".join(log_kaydi[::-1][:50]) 
    
    response_data = {
        "fiyat": fiyat,
        "log": log_display,
        "durum": "🟢 AKTİF" if simulasyon_aktif else "🔴 DURDU",
        "kalan_sure": kalan_sure,
        "simulasyon_aktif": simulasyon_aktif,
        "dusme_meille_seviye": dusme_meille_seviye,
        "yukselme_meille_seviye": yukselme_meille_seviye,
    }

    if session.get("username") and session.get("username") in users:
        current_user = users[session["username"]]
        response_data['user_elmas'] = current_user['elmas']
        response_data['user_tavukbit'] = current_user['tavukbit']

    return jsonify(response_data)


# Giriş yapma rotası
@app.route("/login", methods=["POST"])
def login():
    # Kullanıcının gönderdiği form verisi POST metoduyla işlenir
    sifre = request.form.get("password")
    username_input = request.form.get("username")

    with lock:
        if username_input in users and users[username_input]['password'] == sifre:
            session["giris_tavuk"] = True
            session["username"] = username_input
            session["is_admin"] = users[username_input]['is_admin']
            log_kaydi.append(f"✅ Kullanıcı '{username_input}' giriş yaptı. (Admin: {session['is_admin']})")
        else:
            log_kaydi.append("🚫 Hatalı kullanıcı adı veya şifre denemesi!")
            session.pop("giris_tavuk", None)
            session.pop("username", None)
            session.pop("is_admin", None)
    return redirect(url_for("index"))


# Çıkış yapma rotası
@app.route("/logout")
def logout():
    if session.get("username"):
        log_kaydi.append(f"👋 Kullanıcı '{session['username']}' çıkış yaptı.")
        save_data() 
    session.pop("giris_tavuk", None)
    session.pop("username", None)
    session.pop("is_admin", None)
    return redirect(url_for("index"))


# --- YÖNETİCİ İŞLEMLERİ (ADMIN ONLY) ---

# Admin: Yeni Kullanıcı Kayıt Rotası
@app.route("/admin/register", methods=["POST"])
def register_user():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Yetkisiz erişim."}), 403

    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    initial_elmas = data.get("elmas", 10000)

    try:
        initial_elmas = int(initial_elmas)
    except ValueError:
        return jsonify({"success": False, "message": "Başlangıç Elmas Bakiyesi tam sayı olmalıdır."}), 400

    if not username or not password or initial_elmas < 1:
        return jsonify({"success": False, "message": "Geçersiz kullanıcı adı, şifre veya bakiye."}), 400

    with lock:
        if username in users:
            return jsonify({"success": False, "message": f"Kullanıcı adı '{username}' zaten mevcut."}), 400

        users[username] = {
            'password': password,
            'elmas': initial_elmas,
            'tavukbit': 0,
            'is_admin': False
        }
        log_kaydi.append(f"👤 ADMIN | Yeni kullanıcı '{username}' oluşturuldu. Bakiye: {initial_elmas} Elmas.")
        save_data() 

    return jsonify({"success": True, "message": f"Kullanıcı '{username}' başarıyla oluşturuldu."})


# Admin: Kullanıcı Bakiyesi Güncelleme Rotası
@app.route("/admin/update_user", methods=["POST"])
def update_user_balance():
    """Admin tarafından belirlenen kullanıcının Elmas veya TAVUKBIT bakiyesini günceller."""
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Yetkisiz erişim."}), 403

    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    elmas = data.get("elmas")
    tavukbit = data.get("tavukbit")

    if not username:
        return jsonify({"success": False, "message": "Kullanıcı adı belirtilmelidir."}), 400

    if elmas is None and tavukbit is None:
        return jsonify({"success": False, "message": "En az bir bakiye değeri belirtilmelidir."}), 400

    try:
        if elmas is not None: elmas = int(elmas)
        if tavukbit is not None: tavukbit = int(tavukbit)
    except ValueError:
        return jsonify({"success": False, "message": "Bakiye değerleri tam sayı olmalıdır."}), 400

    with lock:
        if username not in users:
            return jsonify({"success": False, "message": f"Kullanıcı adı '{username}' bulunamadı."}), 404

        user = users[username]
        log_message = f"🛠️ ADMIN | '{username}' kullanıcısının bakiyesini güncelledi: "

        updated = False

        if elmas is not None and elmas >= 0 and user['elmas'] != elmas:
            log_message += f"Elmas: {user['elmas']} -> {elmas}💎, "
            user['elmas'] = elmas
            updated = True

        if tavukbit is not None and tavukbit >= 0 and user['tavukbit'] != tavukbit:
            log_message += f"TAVUKBIT: {user['tavukbit']} -> {tavukbit}🐔, "
            user['tavukbit'] = tavukbit
            updated = True

        if not updated:
            return jsonify({"success": False,
                            "message": "Herhangi bir değişiklik yapılmadı (Yeni değerler mevcut değerlerle aynı). "}), 400

        log_kaydi.append(log_message.strip().rstrip(','))
        save_data() 

        return jsonify({"success": True, "message": f"'{username}' kullanıcısının bakiyesi başarıyla güncellendi."})


# Simülasyon kontrol rotaları (Admin)
@app.route("/devam", methods=["POST"])
def devam():
    if not session.get("is_admin"): return "Yetkisiz", 403
    data = request.get_json(force=True)
    sure = data.get("sure", 20)
    baslangic = data.get("baslangic")

    try:
        sure = int(sure)
        if not (5 <= sure <= 120): sure = 20
        baslangic = int(baslangic) if baslangic is not None else None
        if baslangic is not None and baslangic < 1: baslangic = 1
    except:
        sure = 20
        baslangic = None
        
    # Başlangıç fiyatı belirlenirse bu bir "kaydetme" eylemidir.
    if baslangic:
        with lock:
            global fiyat
            fiyat = baslangic
            save_data()

    threading.Thread(target=simulasyonu_baslat, args=(sure, baslangic)).start()
    return ('', 204)


@app.route("/durdur", methods=["POST"])
def durdur():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global simulasyon_aktif
    with lock: 
        simulasyon_aktif = False
        save_data() 
    return ('', 204)


@app.route("/temizle", methods=["POST"])
def temizle():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global log_kaydi
    with lock:
        log_kaydi.clear()
        log_kaydi.append("🧹 Log temizlendi.")
        save_data() 
    return ('', 204)


# Düşme/Yükselme optimizasyonu rotaları (Admin) - MAX 25
@app.route("/meille_dusme_artir", methods=["POST"])
def meille_dusme_artir():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global dusme_meille_seviye, yukselme_meille_seviye
    with lock:
        if dusme_meille_seviye < MAX_MEILLE_LEVEL:
            dusme_meille_seviye += 1
        if yukselme_meille_seviye != 0: yukselme_meille_seviye = 0
        save_data() 
    return ('', 204)


@app.route("/meille_dusme_azalt", methods=["POST"])
def meille_dusme_azalt():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global dusme_meille_seviye
    with lock:
        if dusme_meille_seviye > 0: dusme_meille_seviye -= 1
        save_data() 
    return ('', 204)


@app.route("/meille_yukselme_artir", methods=["POST"])
def meille_yukselme_artir():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global yukselme_meille_seviye, dusme_meille_seviye
    with lock:
        if yukselme_meille_seviye < MAX_MEILLE_LEVEL:
            yukselme_meille_seviye += 1
        if dusme_meille_seviye != 0: dusme_meille_seviye = 0
        save_data() 
    return ('', 204)


@app.route("/meille_yukselme_azalt", methods=["POST"])
def meille_yukselme_azalt():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global yukselme_meille_seviye
    with lock:
        if yukselme_meille_seviye > 0: yukselme_meille_seviye -= 1
        save_data() 
    return ('', 204)


# --- KULLANICI İŞLEMLERİ (USER ONLY) ---

@app.route("/trade", methods=["POST"])
def trade():
    if not session.get("giris_tavuk") or session.get("is_admin"):
        return jsonify({"success": False, "message": "Ticaret yetkiniz yok."}), 403

    username = session.get("username")
    data = request.get_json(force=True)
    action = data.get("action")

    try:
        amount = int(data.get("amount", 0))
    except ValueError:
        return jsonify({"success": False, "message": "Geçersiz miktar."}), 400

    if amount <= 0:
        return jsonify({"success": False, "message": "Miktar 0'dan büyük olmalıdır."}), 400

    with lock:
        current_price = fiyat
        user = users[username]

        if action == 'buy':
            cost = amount * current_price
            if user['elmas'] >= cost:
                user['elmas'] -= cost
                user['tavukbit'] += amount
                log_kaydi.append(
                    f"➡️ ALIM | {username} {amount} TAVUKBIT aldı. Bakiye: {user['elmas']} Elmas. (Fiyat: {current_price})")
                save_data() 
                return jsonify({"success": True, "message": f"{amount} TAVUKBIT ({cost} Elmas) başarıyla alındı."})
            else:
                return jsonify({"success": False, "message": "Yetersiz Elmas bakiyesi."}), 400

        elif action == 'sell':
            if user['tavukbit'] >= amount:
                revenue = amount * current_price
                user['elmas'] += revenue
                user['tavukbit'] -= amount
                log_kaydi.append(
                    f"⬅️ SATIM | {username} {amount} TAVUKBIT sattı. Bakiye: {user['elmas']} Elmas. (Fiyat: {current_price})")
                save_data() 
                return jsonify({"success": True, "message": f"{amount} TAVUKBIT ({revenue} Elmas) başarıyla satıldı."})
            else:
                return jsonify({"success": False, "message": "Yetersiz TAVUKBIT bakiyesi."}), 400

        return jsonify({"success": False, "message": "Geçersiz işlem tipi."}), 400


# Uygulamayı çalıştırma
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
