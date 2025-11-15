# TAVUKBIT Borsa ve Hesap Yönetim Simülasyonu (Flask)
# Veri Kalıcılığı için JSONBin.io Entegrasyonu kullanılmıştır.

import random
import threading
import time
import json
import os
import requests
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# Flask uygulamasını başlatma
app = Flask(__name__)
app.secret_key = "gizli_tavuk" # Oturum güvenliği için kullanılacak
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

# BAŞLANGIÇ VERİLERİ (API erişimi başarısız olursa kullanılır)
INITIAL_STATE = {
    "fiyat": 10,
    "dusme_meille_seviye": 0,
    "yukselme_meille_seviye": 0,
    "users": {
        "admin": {'password': 'chicken123', 'elmas': 999999, 'tavukbit': 0, 'is_admin': True},
        "testuser": {'password': '123', 'elmas': 10000, 'tavukbit': 0, 'is_admin': False}
    }
}

# --- Kalıcı Depolama Fonksiyonları (İnternet Üzerinden) ---

def load_data():
    """İnternetteki JSON deposundan verileri yükler."""
    if not API_KEY or not BIN_ID:
        print("UYARI: API Anahtarları ayarlanmamış. Varsayılan veriler kullanılıyor.")
        return INITIAL_STATE
        
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status() 
        data = response.json().get('record', INITIAL_STATE)
        
        data['log_kaydi'] = ["🔄 Sunucu yeniden başlatıldı. Veriler internetten yüklendi."]
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"HATA: Veri yüklenirken istek hatası oluştu. Varsayılan veriler kullanılıyor. Hata: {e}")
        return INITIAL_STATE
    except Exception as e:
        print(f"HATA: Veri yüklenirken beklenmeyen hata oluştu. Varsayılan veriler kullanılıyor. Hata: {e}")
        return INITIAL_STATE


def save_data():
    """Tüm önemli verileri internetteki JSON deposuna kaydeder."""
    if not API_KEY or not BIN_ID:
        return

    global fiyat, dusme_meille_seviye, yukselme_meille_seviye, users
    
    data_to_save = {
        "fiyat": fiyat,
        "dusme_meille_seviye": dusme_meille_seviye,
        "yukselme_meille_seviye": yukselme_meille_seviye,
        "users": users
    }
    
    try:
        requests.put(API_URL, json=data_to_save, headers=HEADERS, timeout=10)
    except requests.exceptions.RequestException:
        pass


# --- Uygulama Başlangıcı: Verileri Yükle ---
app_data = load_data()

# Global değişkenleri yüklenen verilerle başlatma
fiyat = app_data["fiyat"]
dusme_meille_seviye = app_data["dusme_meille_seviye"]
yukselme_meille_seviye = app_data["yukselme_meille_seviye"]
users = app_data["users"]
log_kaydi = app_data.get("log_kaydi", [])

# Simülasyon değişkenleri
simulasyon_aktif = False 
kalan_sure = 0 

# Fiyat simülasyonu fonksiyonu
def simulasyonu_baslat(sure, baslangic=None):
    global fiyat, log_kaydi, simulasyon_aktif, kalan_sure
    global dusme_meille_seviye, yukselme_meille_seviye

    with lock:
        if baslangic and isinstance(baslangic, int) and baslangic >= 1: fiyat = baslangic
        if fiyat < 1: fiyat = 10
        if simulasyon_aktif:
            log_kaydi.append("⚠️ Simülasyon zaten aktif! Yeni süre eklenemedi.")
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

            olasiliklar = [-2, -1, 0, 1, 2]
            agirliklar = [1 + dusme_meille_seviye, 1 + dusme_meille_seviye, 1, 1 + yukselme_meille_seviye, 1 + yukselme_meille_seviye]

            secim = random.choices(olasiliklar, weights=agirliklar, k=1)[0]
            yeni_fiyat = fiyat + secim
            fiyat = max(1, yeni_fiyat)
            
            save_data() # <<< VERİ KAYDETME NOKTASI

            log_kaydi.append(f"📈 PİYASA | Fiyat: {fiyat} Elmas (Değişim: {secim:+.0f}) (D: {dusme_meille_seviye}/{MAX_MEILLE_LEVEL}, Y: {yukselme_meille_seviye}/{MAX_MEILLE_LEVEL})")
            kalan_sure -= 1

    with lock:
        simulasyon_aktif = False
        kalan_sure = 0
        log_kaydi.append("⏹ Simülasyon durdu.")
        save_data() # <<< VERİ KAYDETME NOKTASI


# --- HTML ŞABLONU (WIDESCREEN UI) ---

HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TAVUKBIT Borsa Simülasyonu</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f2f5; color: #333; margin: 0; padding: 0; display: flex; justify-content: center; align-items: flex-start; min-height: 100vh; }
        .container { display: flex; width: 90%; max-width: 1400px; margin-top: 20px; gap: 20px; }
        .main-panel, .admin-panel, .log-panel { background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); padding: 25px; }
        .main-panel { flex: 2; }
        .admin-panel { flex: 1; min-width: 300px; }
        .log-panel { flex: 1; max-height: 85vh; overflow-y: scroll; display: flex; flex-direction: column-reverse; }
        h1 { color: #5a189a; margin-top: 0; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
        h2 { color: #8e2de2; font-size: 1.5em; margin-top: 20px; border-bottom: 1px solid #f0f0f0; padding-bottom: 5px; }
        .price-box { background: #5a189a; color: #fff; padding: 15px 25px; border-radius: 8px; text-align: center; margin-bottom: 20px; }
        .price-box h1 { color: #fff; font-size: 2.5em; margin: 0; border: none; padding: 0; }
        .price-box p { margin: 5px 0 0; font-size: 1.1em; }
        .balance-info { margin-bottom: 20px; padding: 15px; background: #e9ecef; border-radius: 8px; }
        .balance-info p { margin: 5px 0; font-size: 1.1em; }
        .trade-form, .admin-form { display: flex; flex-direction: column; gap: 10px; margin-bottom: 15px; }
        input[type="number"], input[type="text"], input[type="password"] { padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 1em; }
        button { padding: 10px 15px; border: none; border-radius: 6px; color: #fff; cursor: pointer; font-size: 1em; transition: background-color 0.3s; }
        .btn-primary { background-color: #8e2de2; }
        .btn-primary:hover { background-color: #6a1aae; }
        .btn-secondary { background-color: #555; }
        .btn-secondary:hover { background-color: #333; }
        .btn-success { background-color: #28a745; }
        .btn-success:hover { background-color: #1e7e34; }
        .btn-danger { background-color: #dc3545; }
        .btn-danger:hover { background-color: #bd2130; }
        .btn-warning { background-color: #ffc107; color: #333; }
        .btn-warning:hover { background-color: #e0a800; }
        .log-entry { padding: 8px; border-bottom: 1px dashed #eee; font-size: 0.9em; white-space: pre-wrap; word-break: break-all; }
        .log-entry:last-child { border-bottom: none; }
        .log-entry.market { color: #007bff; }
        .log-entry.trade { color: #28a745; }
        .log-entry.admin { color: #ffc107; }
        .status-box { padding: 10px; border-radius: 6px; font-weight: bold; text-align: center; margin-bottom: 15px; }
        .status-active { background-color: #d4edda; color: #155724; }
        .status-stopped { background-color: #f8d7da; color: #721c24; }
        .meille-control { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
        .meille-control span { font-weight: bold; font-size: 1.1em; }
        .meille-buttons button { width: 40px; }
        .error { color: #dc3545; font-weight: bold; margin-bottom: 10px; }
        .success { color: #28a745; font-weight: bold; margin-bottom: 10px; }
        .admin-section { border: 1px solid #ccc; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .admin-section h3 { margin-top: 0; color: #007bff; }
        .admin-list { max-height: 200px; overflow-y: auto; background: #f9f9f9; padding: 10px; border-radius: 6px; }
        .admin-list div { padding: 5px 0; border-bottom: 1px dotted #e0e0e0; font-size: 0.95em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-panel">
            <h1>TAVUKBIT Simülasyon Borsası</h1>

            <div class="price-box">
                <p>Mevcut TAVUKBIT Fiyatı</p>
                <h1>{{ fiyat }} ELMAS</h1>
            </div>

            {% if session.get('giris_tavuk') and not session.get('is_admin') %}
                <h2>Hesap Özeti ({{ session.get('username') }})</h2>
                <div class="balance-info">
                    <p>Elmas Bakiyesi: **{{ "{:,.0f}".format(user_data['elmas']) }}**</p>
                    <p>TAVUKBIT Bakiyesi: **{{ "{:,.0f}".format(user_data['tavukbit']) }}**</p>
                    <p>Toplam Değer (Tahmini): **{{ "{:,.0f}".format(user_data['elmas'] + user_data['tavukbit'] * fiyat) }}** Elmas</p>
                </div>

                <h2>Al/Sat İşlemi</h2>
                <div id="message" class="error" style="display:none;"></div>
                <form class="trade-form" id="tradeForm">
                    <input type="number" id="tradeAmount" placeholder="TAVUKBIT Miktarı" required min="1">
                    <div style="display:flex; gap:10px;">
                        <button type="submit" class="btn-success" onclick="submitTrade('buy')">AL ({{ fiyat }} Elmas)</button>
                        <button type="submit" class="btn-danger" onclick="submitTrade('sell')">SAT ({{ fiyat }} Elmas)</button>
                    </div>
                </form>
            {% elif session.get('is_admin') %}
                <h2>Admin Yönetim Paneli</h2>
                <p>Hoş geldiniz, **Admin**.</p>
                <div class="balance-info">
                    <p>Toplam Kayıtlı Kullanıcı: **{{ users_list | length }}**</p>
                </div>
                
                <h2>Simülasyon Kontrolü</h2>
                <div id="sim_message" class="error" style="display:none;"></div>
                <div class="status-box {% if durum == '🟢 AKTİF' %}status-active{% else %}status-stopped{% endif %}">
                    Durum: {{ durum }} | Kalan Süre: **{{ kalan_sure }} sn**
                </div>
                <form class="admin-form" id="simControlForm">
                    <div style="display:flex; gap:10px;">
                        <input type="number" id="simTime" placeholder="Süre (saniye)" value="60" min="1" style="flex-grow:1;">
                        <input type="number" id="simStartPrice" placeholder="Başlangıç Fiyatı (Ops.)" style="flex-grow:1;">
                    </div>
                    <div style="display:flex; gap:10px;">
                        <button type="button" class="btn-success" onclick="sendSimCommand('start')">BAŞLAT/SÜRE EKLE</button>
                        <button type="button" class="btn-danger" onclick="sendSimCommand('stop')">DURDUR</button>
                        <button type="button" class="btn-secondary" onclick="sendSimCommand('reset_logs')">Log Temizle</button>
                    </div>
                </form>

                <h2>Piyasa Yönlendirme Kontrolü (Meille)</h2>
                <div class="admin-form">
                    <p>Seviye: {{ MAX_MEILLE_LEVEL }} max</p>
                    <div class="meille-control">
                        <span>Düşüş Olasılığı: Seviye **{{ dusme_meille_seviye }}**</span>
                        <div class="meille-buttons">
                            <button class="btn-danger" onclick="sendMeilleCommand('dusme_azalt')">-</button>
                            <button class="btn-success" onclick="sendMeilleCommand('dusme_artir')">+</button>
                        </div>
                    </div>
                    <div class="meille-control">
                        <span>Yükseliş Olasılığı: Seviye **{{ yukselme_meille_seviye }}**</span>
                        <div class="meille-buttons">
                            <button class="btn-danger" onclick="sendMeilleCommand('yukselme_azalt')">-</button>
                            <button class="btn-success" onclick="sendMeilleCommand('yukselme_artir')">+</button>
                        </div>
                    </div>
                </div>
                
                <div class="admin-section">
                    <h3>Kullanıcı Hesap Yönetimi</h3>
                    <form class="admin-form" id="registerForm">
                        <input type="text" name="username" placeholder="Yeni Kullanıcı Adı" required>
                        <input type="password" name="password" placeholder="Şifre" required>
                        <input type="number" name="elmas" placeholder="Başlangıç Elmas (örn: 10000)" value="10000" required min="1">
                        <button type="submit" class="btn-primary">Kullanıcı Kaydet</button>
                    </form>
                    <div id="register_message" class="error" style="display:none;"></div>
                    
                    <h4 style="margin-top:15px;">Mevcut Kullanıcılar</h4>
                    <div class="admin-list">
                        {% for username in users_list %}
                            <div>{{ username }}</div>
                        {% endfor %}
                    </div>
                </div>

            {% else %}
                <h2>Giriş Yap / Kayıt Ol</h2>
                <div id="login_message" class="error" style="display:none;"></div>
                <form class="admin-form" id="loginForm">
                    <input type="text" name="username" placeholder="Kullanıcı Adı" required>
                    <input type="password" name="password" placeholder="Şifre" required>
                    <button type="submit" class="btn-primary">Giriş Yap</button>
                </form>
                <p style="font-size:0.9em; color:#777;">*Kayıt admin tarafından yapılmaktadır.</p>
            {% endif %}

            {% if session.get('giris_tavuk') %}
                <hr style="margin-top:20px;">
                <form action="/logout" method="post">
                    <button type="submit" class="btn-secondary" style="width:100%;">Çıkış Yap ({{ session.get('username') }})</button>
                </form>
            {% endif %}

        </div>

        <div class="log-panel">
            <h2>Simülasyon Olay Günlüğü</h2>
            {% for entry in log %}
                <div class="log-entry">{{ entry }}</div>
            {% endfor %}
        </div>
    </div>

    <script>
        const tradeForm = document.getElementById('tradeForm');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const messageBox = document.getElementById('message');
        const simMessageBox = document.getElementById('sim_message');
        const registerMessageBox = document.getElementById('register_message');

        function displayMessage(box, text, isSuccess) {
            box.style.display = 'block';
            box.innerText = text;
            box.className = isSuccess ? 'success' : 'error';
            setTimeout(() => { box.style.display = 'none'; }, 5000);
        }

        // Ticaret İşlemi
        function submitTrade(action) {
            event.preventDefault();
            const amount = document.getElementById('tradeAmount').value;
            if (amount < 1) {
                displayMessage(messageBox, "Miktar 1'den büyük olmalıdır.", false);
                return;
            }

            fetch('/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action, amount: parseInt(amount) })
            })
            .then(response => response.json())
            .then(data => {
                displayMessage(messageBox, data.message, data.success);
                if (data.success) {
                    setTimeout(() => window.location.reload(), 1500); // Başarılıysa sayfayı yenile
                }
            })
            .catch(error => {
                displayMessage(messageBox, 'İşlem sırasında bir hata oluştu.', false);
            });
        }

        // Simülasyon Kontrolü
        function sendSimCommand(command) {
            const time = document.getElementById('simTime').value;
            const startPrice = document.getElementById('simStartPrice').value;
            let url = '';
            let body = {};
            let isPost = true;

            if (command === 'start') {
                if (time < 1) {
                    displayMessage(simMessageBox, "Süre 1 saniyeden az olamaz.", false);
                    return;
                }
                url = '/simulasyon_baslat';
                body = { sure: parseInt(time) };
                if (startPrice && startPrice >= 1) { body.baslangic = parseInt(startPrice); }
            } else if (command === 'stop') {
                url = '/simulasyon_durdur';
                isPost = false;
            } else if (command === 'reset_logs') {
                url = '/log_temizle';
                isPost = false;
            } else {
                return;
            }

            fetch(url, {
                method: isPost ? 'POST' : 'GET',
                headers: isPost ? { 'Content-Type': 'application/json' } : {},
                body: isPost ? JSON.stringify(body) : null
            })
            .then(response => {
                if(response.status === 204 || response.ok) { // 204 No Content veya 200 OK
                    displayMessage(simMessageBox, (command === 'start' ? 'Simülasyon başladı/süre eklendi.' : (command === 'stop' ? 'Simülasyon durduruldu.' : 'Loglar temizlendi.')), true);
                    setTimeout(() => window.location.reload(), 1500);
                } else {
                    displayMessage(simMessageBox, 'İşlem başarısız.', false);
                }
            })
            .catch(error => {
                displayMessage(simMessageBox, 'İstek gönderilirken hata oluştu.', false);
            });
        }
        
        // Meille Kontrolü
        function sendMeilleCommand(action) {
            fetch(`/meille_${action}`, { method: 'POST' })
            .then(response => {
                if(response.status === 204) {
                    setTimeout(() => window.location.reload(), 100);
                } else {
                    displayMessage(simMessageBox, 'Meille kontrol hatası.', false);
                }
            });
        }


        // Kullanıcı Girişi
        if (loginForm) {
            loginForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(loginForm);
                const data = Object.fromEntries(formData.entries());

                fetch('/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(response => response.json())
                .then(data => {
                    displayMessage(document.getElementById('login_message'), data.message, data.success);
                    if (data.success) {
                        setTimeout(() => window.location.reload(), 1500);
                    }
                });
            });
        }
        
        // Yeni Kullanıcı Kaydı (Admin)
        if (registerForm) {
            registerForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(registerForm);
                const data = Object.fromEntries(formData.entries());

                fetch('/admin/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(response => response.json())
                .then(data => {
                    displayMessage(registerMessageBox, data.message, data.success);
                    if (data.success) {
                        registerForm.reset();
                        setTimeout(() => window.location.reload(), 1500);
                    }
                });
            });
        }

    </script>
</body>
</html>
"""


# --- FLASK ROTATALARI ---

# Ana Sayfa ve Kullanıcı Durumu
@app.route("/")
def index():
    user_data = None
    if session.get('giris_tavuk'):
        username = session['username']
        with lock:
            user_data = users.get(username, {})
    
    users_list = list(users.keys())

    return render_template_string(HTML,
                                  fiyat=fiyat, log=log_kaydi,
                                  durum="🟢 AKTİF" if simulasyon_aktif else "🔴 DURDU",
                                  kalan_sure=kalan_sure,
                                  dusme_meille_seviye=dusme_meille_seviye,
                                  yukselme_meille_seviye=yukselme_meille_seviye,
                                  session=session,
                                  user_data=user_data,
                                  users_list=users_list,
                                  MAX_MEILLE_LEVEL=MAX_MEILLE_LEVEL)


# Giriş
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")

    with lock:
        user = users.get(username)

        if user and user['password'] == password:
            session['giris_tavuk'] = True
            session['username'] = username
            session['is_admin'] = user.get('is_admin', False)
            return jsonify({"success": True, "message": f"Hoş geldiniz, {username}!"})
        else:
            return jsonify({"success": False, "message": "Geçersiz kullanıcı adı veya şifre."}), 401

# Çıkış
@app.route("/logout", methods=["POST"])
def logout():
    session.pop('giris_tavuk', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('index'))

# Simülasyon Başlat/Süre Ekle (Admin)
@app.route("/simulasyon_baslat", methods=["POST"])
def simulasyon_baslat_route():
    if not session.get("is_admin"): return "Yetkisiz", 403
    
    data = request.get_json()
    sure = data.get("sure", 60)
    baslangic = data.get("baslangic")

    if simulasyon_aktif:
        with lock:
            global kalan_sure
            kalan_sure += sure
            return ('', 204) # Süre eklendi

    else:
        # Yeni bir thread başlat
        simulasyonu_baslat(sure, baslangic)
        return ('', 204)

# Simülasyon Durdur (Admin)
@app.route("/simulasyon_durdur")
def simulasyon_durdur_route():
    if not session.get("is_admin"): return "Yetkisiz", 403
    
    with lock:
        global simulasyon_aktif
        simulasyon_aktif = False
        return ('', 204)

# Log Temizle (Admin)
@app.route("/log_temizle")
def log_temizle():
    if not session.get("is_admin"): return "Yetkisiz", 403
    
    with lock:
        global log_kaydi
        log_kaydi = ["Loglar admin tarafından temizlendi."]
        return ('', 204)

# Düşme/Yükselme optimizasyonu rotaları (Admin)
@app.route("/meille_dusme_artir", methods=["POST"])
def meille_dusme_artir():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global dusme_meille_seviye, yukselme_meille_seviye
    with lock:
        if dusme_meille_seviye < MAX_MEILLE_LEVEL: dusme_meille_seviye += 1
        if yukselme_meille_seviye != 0: yukselme_meille_seviye = 0
        save_data() # <<< KAYIT NOKTASI
    return ('', 204)

@app.route("/meille_dusme_azalt", methods=["POST"])
def meille_dusme_azalt():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global dusme_meille_seviye
    with lock:
        if dusme_meille_seviye > 0: dusme_meille_seviye -= 1
        save_data() # <<< KAYIT NOKTASI
    return ('', 204)

@app.route("/meille_yukselme_artir", methods=["POST"])
def meille_yukselme_artir():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global yukselme_meille_seviye, dusme_meille_seviye
    with lock:
        if yukselme_meille_seviye < MAX_MEILLE_LEVEL: yukselme_meille_seviye += 1
        if dusme_meille_seviye != 0: dusme_meille_seviye = 0
        save_data() # <<< KAYIT NOKTASI
    return ('', 204)

@app.route("/meille_yukselme_azalt", methods=["POST"])
def meille_yukselme_azalt():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global yukselme_meille_seviye
    with lock:
        if yukselme_meille_seviye > 0: yukselme_meille_seviye -= 1
        save_data() # <<< KAYIT NOKTASI
    return ('', 204)

# Kullanıcı Ticaret Rotası
@app.route("/trade", methods=["POST"])
def trade():
    if not session.get("giris_tavuk") or session.get("is_admin"):
        return jsonify({"success": False, "message": "Ticaret yetkiniz yok."}), 403

    username = session.get("username")
    data = request.get_json()
    action = data.get("action")
    try:
        amount = int(data.get("amount", 0))
    except ValueError:
        return jsonify({"success": False, "message": "Geçersiz miktar."}), 400

    if amount <= 0: return jsonify({"success": False, "message": "Miktar 0'dan büyük olmalıdır."}), 400

    with lock:
        current_price = fiyat
        user = users[username]

        if action == 'buy':
            cost = amount * current_price
            if user['elmas'] >= cost:
                user['elmas'] -= cost
                user['tavukbit'] += amount
                save_data() # <<< KAYIT NOKTASI
                log_kaydi.append(f"➡️ ALIM | {username} {amount} TAVUKBIT aldı. Bakiye: {user['elmas']} Elmas. (Fiyat: {current_price})")
                return jsonify({"success": True, "message": f"{amount} TAVUKBIT ({cost} Elmas) başarıyla alındı."})
            else:
                return jsonify({"success": False, "message": "Yetersiz Elmas bakiyesi."}), 400

        elif action == 'sell':
            if user['tavukbit'] >= amount:
                revenue = amount * current_price
                user['elmas'] += revenue
                user['tavukbit'] -= amount
                save_data() # <<< KAYIT NOKTASI
                log_kaydi.append(f"⬅️ SATIM | {username} {amount} TAVUKBIT sattı. Bakiye: {user['elmas']} Elmas. (Fiyat: {current_price})")
                return jsonify({"success": True, "message": f"{amount} TAVUKBIT ({revenue} Elmas) başarıyla satıldı."})
            else:
                return jsonify({"success": False, "message": "Yetersiz TAVUKBIT bakiyesi."}), 400

        return jsonify({"success": False, "message": "Geçersiz işlem tipi."}), 400

# Admin: Yeni Kullanıcı Kayıt Rotası
@app.route("/admin/register", methods=["POST"])
def register_user():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Yetkisiz erişim."}), 403

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    try:
        initial_elmas = int(data.get("elmas", 10000))
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
        save_data() # <<< KAYIT NOKTASI

    return jsonify({"success": True, "message": f"Kullanıcı '{username}' başarıyla oluşturuldu."})


if __name__ == "__main__":
    # Gunicorn ile çalışırken bu kısım çalışmaz, sadece yerel test içindir.
    simulasyonu_baslat(300) # 5 dakikalık başlangıç simülasyonu
    app.run(host="0.0.0.0", port=5000, debug=False)
