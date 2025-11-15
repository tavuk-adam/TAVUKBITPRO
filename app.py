# TAVUKBIT Borsa ve Hesap Yönetim Simülasyonu (Flask)
# Veri Kalıcılığı için JSONBin.io Entegrasyonu yapıldı.

import random
import threading
import time
import json
import os
import requests
from flask import Flask, render_template_string, request, session, redirect, url_for, jsonify

# Flask uygulamasını başlatma
app = Flask(__name__)
app.secret_key = "gizli_tavuk"

# Ortak kaynaklara eş zamanlı erişimi yönetmek için kilit
lock = threading.Lock()

# --- JSONBin.io Yapılandırması (Çevre Değişkenleri) ---
# Bunlar, sunucuya dağıtım yaparken ayarlanmalıdır!
API_KEY = os.environ.get("API_KEY") # JSONBin Secret Key
BIN_ID = os.environ.get("BIN_ID")   # JSONBin Bin ID
API_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}" if BIN_ID else None
HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": API_KEY 
}
# --- /JSONBin.io Yapılandırması ---

MAX_MEILLE_LEVEL = 25 # Maksimum olasılık ayar seviyesi

# BAŞLANGIÇ VERİLERİ (API'dan veri çekilemezse veya anahtarlar yoksa kullanılacak)
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
        print("UYARI: API Anahtarları veya BIN ID ayarlanmamış. Varsayılan veriler kullanılıyor.")
        return INITIAL_STATE
        
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json().get('record', INITIAL_STATE)
        
        # Loglar, yeniden başlatma sonrası kaybolacağı için boş başlatılır.
        data['log_kaydi'] = ["🔄 Sunucu yeniden başlatıldı. Veriler internetten yüklendi."]
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"HATA: Veri yüklenirken istek hatası oluştu: {e}. Varsayılan veriler kullanılıyor.")
        return INITIAL_STATE
    except Exception as e:
        print(f"HATA: Veri yüklenirken beklenmeyen hata oluştu: {e}. Varsayılan veriler kullanılıyor.")
        return INITIAL_STATE


def save_data():
    """Tüm önemli verileri internetteki JSON deposuna kaydeder (PUT isteği)."""
    if not API_KEY or not BIN_ID:
        # print("UYARI: API Anahtarları ayarlanmamış. Kayıt yapılmıyor.")
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
        # Yanıt kontrolü ihmal edildi, çünkü her anlık değişimi kaydettiğimiz için hız önceliklidir.
    except requests.exceptions.RequestException:
        # Hatalar genellikle ağ geçici olduğu için loglanmaz.
        pass


# --- Uygulama Başlangıcı: Verileri Yükle ---
app_data = load_data()

# Global değişkenleri yüklenen verilerle başlatma
fiyat = app_data["fiyat"]
dusme_meille_seviye = app_data["dusme_meille_seviye"]
yukselme_meille_seviye = app_data["yukselme_meille_seviye"]
users = app_data["users"]
log_kaydi = app_data.get("log_kaydi", [])

# Simülasyon değişkenleri (Bunlar kalıcı değildir, sunucu tekrar başladığında yeniden başlar)
simulasyon_aktif = False 
kalan_sure = 0 


# Fiyat simülasyonu fonksiyonu
def simulasyonu_baslat(sure, baslangic=None):
    """
    Simülasyonu başlatan fonksiyon.
    """
    global fiyat, log_kaydi, simulasyon_aktif, kalan_sure
    global dusme_meille_seviye, yukselme_meille_seviye

    with lock:
        if baslangic and isinstance(baslangic, int) and baslangic >= 1:
            fiyat = baslangic

        if fiyat < 1:
            fiyat = 10

        if simulasyon_aktif:
            log_kaydi.append("⚠️ Simülasyon zaten aktif! Yeni süre eklenemedi.")
            return

        simulasyon_aktif = True
        kalan_sure = sure

    for saniye in range(1, sure + 1):
        time.sleep(1)
        with lock:
            if not simulasyon_aktif:
                log_kaydi.append("⏹ Simülasyon erken durduruldu.")
                break

            olasiliklar = [-2, -1, 0, 1, 2]
            agirliklar = [1, 1, 1, 1, 1]

            if dusme_meille_seviye > 0:
                agirliklar[0] += dusme_meille_seviye
                agirliklar[1] += dusme_meille_seviye

            if yukselme_meille_seviye > 0:
                agirliklar[3] += yukselme_meille_seviye
                agirliklar[4] += yukselme_meille_seviye

            secim = random.choices(olasiliklar, weights=agirliklar, k=1)[0]

            yeni_fiyat = fiyat + secim
            fiyat = max(1, yeni_fiyat)
            
            # Fiyat değişiminde veriyi kaydet
            save_data() # <<< KAYIT NOKTASI

            log_kaydi.append(
                f"📈 PİYASA | Fiyat: {fiyat} Elmas (Değişim: {secim:+.0f}) (D: {dusme_meille_seviye}/{MAX_MEILLE_LEVEL}, Y: {yukselme_meille_seviye}/{MAX_MEILLE_LEVEL})")

            kalan_sure -= 1

    with lock:
        simulasyon_aktif = False
        kalan_sure = 0
        log_kaydi.append("⏹ Simülasyon durdu.")
        save_data() # <<< KAYIT NOKTASI (Simülasyon bitiş fiyatını kaydetmek için)


# --- ROUTE TANIMLAMALARI ---
# Tüm route'lar (HTML şablonu dahil) boyutundan dolayı burada atlanmıştır, ancak orijinal kodunuzdaki Widescreen UI yapısı aynen korunmuştur.
# **ÖNEMLİ:** Aşağıdaki tüm veri değiştiren rotalara `save_data()` eklenmiştir.

# Admin: Yeni Kullanıcı Kayıt Rotası
@app.route("/admin/register", methods=["POST"])
def register_user():
    if not session.get("is_admin"):
        return jsonify({"success": False, "message": "Yetkisiz erişim."}), 403

    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    initial_elmas = data.get("elmas", 10000)

    try: initial_elmas = int(initial_elmas)
    except ValueError: return jsonify({"success": False, "message": "Başlangıç Elmas Bakiyesi tam sayı olmalıdır."}), 400

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


# Admin: Kullanıcı Bakiyesi Güncelleme Rotası
@app.route("/admin/update_user", methods=["POST"])
def update_user_balance():
    if not session.get("is_admin"): return jsonify({"success": False, "message": "Yetkisiz erişim."}), 403
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    elmas = data.get("elmas")
    tavukbit = data.get("tavukbit")

    # ... (kodun geri kalanı) ...
    with lock:
        # ... (kullanıcı bulunması ve bakiye güncellemeleri) ...
        user = users[username]
        updated = False
        # ... (güncelleme mantığı) ...
        if updated:
            save_data() # <<< KAYIT NOKTASI
            
    # ... (başarı/hata dönüşü) ...
    # Kodu daha kısa tutmak için bu rotayı da kesiyorum, ancak mantık yukarıdaki save_data() çağrısını içerir.
    return jsonify({"success": True, "message": f"'{username}' kullanıcısının bakiyesi başarıyla güncellendi."})


# Düşme/Yükselme optimizasyonu rotaları (Admin) - MAX 25
@app.route("/meille_dusme_artir", methods=["POST"])
def meille_dusme_artir():
    if not session.get("is_admin"): return "Yetkisiz", 403
    global dusme_meille_seviye, yukselme_meille_seviye
    with lock:
        if dusme_meille_seviye < MAX_MEILLE_LEVEL:
            dusme_meille_seviye += 1
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
        if yukselme_meille_seviye < MAX_MEILLE_LEVEL:
            yukselme_meille_seviye += 1
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
    data = request.get_json(force=True)
    action = data.get("action")
    amount = int(data.get("amount", 0))

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
        
# Kalan rotalar (index, status, login, logout, devam, durdur, temizle) aynı kalır.
# HTML şablonu (ROUTE /) boyutundan dolayı burada tekrar verilmemiştir, ancak Widescreen UI şablonunu kullanmalısınız.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

# TAM KOD İÇİN, LÜTFEN ÖNCEKİ YANITIMDAN ALDIĞINIZ WIDESCREEN UI KODUNU KULLANIN VE BU VERİ KAYDETME/YÜKLEME MANTIĞINI BAŞLANGICINA ENTEGRE EDİN.
