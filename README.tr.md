# Home Assistant için ZhiJinPower MPPT

[English](README.md)

**ZhiJinPower** uygulamasını kullanan Bluetooth LE MPPT solar şarj kontrolcüleri için özel entegrasyon (BLE adı `ZJBE-<MAC>`, BL917 tipi, 12 V). Yerel çalışır, bulut yok.

## Özellikler
- Batarya voltajı, yük akımı, şarj akımı (doğrulanmadı), sıcaklık, toplam üretim
- **Yük aç/kapa anahtarı**
- Ayarlar number olarak: floating şarj voltajı (12,0–14,5 V), deşarj geri dönüş (11,0–13,0 V), deşarj kesme (9,0–11,5 V); sınırlar kılavuzdan
- Batarya tipi, yük modu (menü 5: Manuel / Otomatik / Zamanlı / Doğrudan çıkış) ve sistem voltajı modu (Otomatik / 12 V) isteğe bağlı seçim kutuları olarak, varsayılan kapalı
- Fotovoltaik durumu (gece / gündüz) ve sistem voltajı modu sensörleri
- Yük anahtarı yalnızca manuel (Cot) modda çalışır, diğer modlarda bunu söyler
- Home Assistant Bluetooth adaptörü veya ESP32 Bluetooth proxy ile çalışır
- Bağlantı teşhisi (son güncelleme, art arda hata, son hata, Bluetooth kaynağı, RSSI) ve tek bir Bluetooth adaptörü ya da ESP32 proxy seçme seçeneği
- Tanılama indirme (adres gizlenir), sorgulama aralığı seçeneği (10–600 sn)

## Kurulum
**HACS:** HACS → ⋮ → Özel depolar → `https://github.com/kilingon/zhijinpowerforha` adresini *Integration* olarak ekle → kur → Home Assistant'ı yeniden başlat.

**Elle:** `custom_components/zhijin_mppt` klasörünü `config/custom_components/` içine kopyala ve yeniden başlat.

## Ayarlama
Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → *ZhiJinPower MPPT*.
1. Home Assistant kontrolcüyü Bluetooth ile görüyorsa otomatik önerilir (ya da listeden seç).
2. Görmüyorsa Bluetooth adresini (`AA:BB:CC:DD:EE:FF` ya da `ZJBE-AABBCCDDEEFF`) yaz.

**Önce telefon uygulamasını kapat.** Kontrolcü aynı anda tek bağlantı kabul eder. Home Assistant her sorguda (varsayılan 60 sn) kısa süre bağlanır; uygulama aradaki sürede bağlanabilir.

## Bağlantı ipuçları
Kontrolcü tek bağlantı kabul eder ve kopmaların en yaygın nedeni zayıf sinyaldir. "Sinyal gücü" teşhis sensörüne bak: yaklaşık -75 dBm'den iyi, ideal olarak -70 ve üstü olsun. Bluetooth proxy'yi (ESP32, `active: true` ile `bluetooth_proxy`) ya da adaptörü kontrolcüye yaklaştır. Birden fazla adaptör ya da proxy kontrolcüyü duyuyorsa, entegrasyon seçeneklerinden birini sabitleyebilirsin.

## Bilinen sınırlar
- Yalnızca tek bir 12 V BL917 tipi cihazda denendi. 24 V desteklenmez.
- Şarj akımı ölçeği, şarj aşaması kodları, manuel dışındaki yük modları ve batarya tipi yazma doğrulanmadı.
- Yük modu yazma Home Assistant üzerinden doğrulanmadı. Sistem voltajı modu yalnızca Otomatik ya da 12 V olarak ayarlanabilir; 24–84 V gösterilir ama yazılmaz.
- "Yük çıkışı" sensörü komuttan birkaç saniye geç güncellenir; anahtar komut edilen durumu gösterir.
- Tersine mühendislik ürünü protokol: [docs/protocol.md](docs/protocol.md). Ayar yazmak kendi sorumluluğundadır.

MIT lisanslı. ZhiJinPower ile bağlantısı yoktur.
