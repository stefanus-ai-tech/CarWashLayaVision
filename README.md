# CarWashLayaVision

Dashboard HTML/CSS/JS untuk analisis video cuci mobil. Python menjalankan YOLO + ByteTrack, klasifikasi Laya Vision, dan API lokal.

## Jalankan

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8501
```

Buka [http://127.0.0.1:8501](http://127.0.0.1:8501). Upload video atau pilih video lokal dari `C:\Users\DELL\Videos\CuciMobil`. Untuk folder lain, set variabel lingkungan `CARWASH_VIDEO_DIR` sebelum menjalankan server.

Video tegak dan mendatar ditampilkan menurut rasio aslinya. Video 4K diproses pada sisi terpanjang 1280 piksel tanpa mengubah file sumber. Hasil ada di `outputs/<run>/`: `annotated.mp4`, `events.csv`, `summary.json`, dan crop kendaraan.

Pilih **Saat melewati garis** untuk CCTV pintu masuk. Pilih **Saat terlihat stabil** untuk klip yang mobilnya sudah ada di area cuci pada awal video; kendaraan dihitung setelah terlihat tiga frame berturut-turut. Setiap ID tracker dihitung satu kali, tetapi ID yang berganti karena tertutup objek masih bisa menyebabkan duplikat.

## Laya Vision

Jika library belum tersedia, pasang dengan:

```powershell
.venv\Scripts\python -m pip install "git+https://github.com/r33drichards/laya-vision.git" torchvision
```

Bobot `thaitea/laya-vision` dipakai dari `models/laya-vision/` jika sudah diunduh. Jika belum ada, library mencoba mengambilnya dari Hugging Face. Harga tetap tampil sebagai estimasi untuk prediksi di bawah ambang, dengan status **Perlu cek manual**. Jika model tidak tersedia atau gagal memprediksi, harga baru muncul setelah kelas tarif diisi lewat **Koreksi harga**. Koreksi memperbarui dashboard, `events.csv`, dan `summary.json`. Ambang awal 90% belum dikalibrasi untuk kamera carwash; pada klip contoh, Laya pernah salah mengenali jenis mobil. Cek hasil terhadap label manual sebelum memakai tarifnya untuk tagihan nyata.

Bobot Laya Vision berlisensi CC BY-NC-SA 4.0, sehingga penggunaan komersial memerlukan izin yang sesuai.
