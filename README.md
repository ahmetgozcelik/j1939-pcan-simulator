# J1939 PCAN Simulator

**TR:** PEAK PCAN USB adaptörü üzerinden J1939 CAN mesajları gönderen masaüstü simülatör.  
**EN:** A desktop J1939 CAN bus simulator that sends configurable messages via PEAK PCAN USB adapter.

---

## 🇹🇷 Türkçe

### Nedir?
PCAN VIEW'da elle hex girmek yerine, J1939 CAN mesajlarını otomatik ve yapılandırılabilir şekilde gönderen bir test aracıdır. Motor sensör verileri, alarm kodları (DM1) ve elektrik sistemlerini simüle edebilirsiniz.

### Özellikler
- PGN/SPN bazlı mesaj tanımlama (dışarıdan yapılandırılabilir)
- Sinyal bazlı scale, offset, byte/bit pozisyonu yapılandırması
- Simülasyon modları: Fixed, Random, Sine, Sawtooth, Ramp (üçgen dalga)
- DM1 özel panel: SPN listesi, random aralık, otomatik lamp döngüsü
- PCAN kanal ve bitrate seçimi (125/250/500 kbps, 1 Mbps)
- JSON konfigürasyon kayıt/yükleme, son kullanılan dosya hafızası
- Karanlık tema arayüz

### Gereksinimler
- Windows 10/11 (64-bit)
- Python 3.11+ ([python.org](https://www.python.org/downloads/) — Windows Store değil)
- PEAK PCAN USB adaptör + sürücü ([peak-system.com](https://www.peak-system.com/Downloads.76.0.html))

### Kurulum
```bash
git clone https://github.com/KULLANICI_ADINIZ/j1939-pcan-simulator.git
cd j1939-pcan-simulator
python -m venv .venv
.venv\Scripts\activate
pip install PyQt5 python-can
python main.py
```

### EXE Oluşturma
Aşağıdaki adımları izleyin:

```bash
pip install pyinstaller
pyinstaller J1939_Simulator.spec
```

EXE dosyası `dist/J1939_Simulator.exe` olarak oluşur.  
`configs` klasörü otomatik olarak EXE içine gömülür, ayrıca kopyalamanıza gerek yoktur.

> ⚠️ PEAK PCAN Basic sürücüsünün kurulu olması gerekir: [peak-system.com](https://www.peak-system.com/Downloads.76.0.html)  
> ⚠️ Windows Defender uyarısı verirse "More info → Run anyway" seçin.

---

## 🇬🇧 English

### What is it?
A desktop simulator that automatically sends configurable J1939 CAN messages — no more manual hex entry in PCAN VIEW. Simulate engine sensors, diagnostic trouble codes (DM1), and electrical systems.

### Features
- PGN/SPN based message definition (fully configurable)
- Per-signal scale, offset, byte/bit position configuration
- Simulation modes: Fixed, Random, Sine, Sawtooth, Ramp (triangle wave)
- DM1 special panel: SPN list mode, random range, auto lamp cycling
- PCAN channel and bitrate selection (125/250/500 kbps, 1 Mbps)
- JSON config save/load with recent files memory
- Dark theme UI

### Requirements
- Windows 10/11 (64-bit)
- Python 3.11+ ([python.org](https://www.python.org/downloads/) — NOT Windows Store)
- PEAK PCAN USB adapter + driver ([peak-system.com](https://www.peak-system.com/Downloads.76.0.html))

### Installation
```bash
git clone https://github.com/KULLANICI_ADINIZ/j1939-pcan-simulator.git
cd j1939-pcan-simulator
python -m venv .venv
.venv\Scripts\activate
pip install PyQt5 python-can
python main.py
```

### Build EXE
Follow these steps:

```bash
pip install pyinstaller
pyinstaller J1939_Simulator.spec
```

EXE will be created at `dist/J1939_Simulator.exe`.  
The `configs` folder is automatically bundled into the EXE.

> ⚠️ PEAK PCAN Basic driver must be installed: [peak-system.com](https://www.peak-system.com/Downloads.76.0.html)  
> ⚠️ If Windows Defender warns you, click "More info → Run anyway".

---

## System Architecture

```
[J1939 PCAN Simulator]
        ↓ USB
[PEAK PCAN USB Adapter]
        ↓ CAN Bus (J1939, 250 kbps default)
[Target Device / ECU / PLC]
```

## License / Lisans
MIT License — free to use, modify and distribute.
