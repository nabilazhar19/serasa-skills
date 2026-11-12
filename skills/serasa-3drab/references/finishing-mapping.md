# Pemetaan pekerjaan SKP → uraian tab AHS (template Nov 2026)

Kolom Spec diisi **uraian AHS persis** (tab `AHS` kolom A). Kode di bawah hanya untuk mencari uraiannya (kolom E tab AHS). Cek di tab AHS live sebelum dipakai; kalau tidak ada padanan yang sesuai dengan model → tipe `audit` (analisa) dan otomatis masuk daftar tab Audit.

## Default template
| Pekerjaan | Kode | Satuan |
|---|---|---|
| Persiapan, pengukuran & bouwplank | PP2 | ls |
| Listrik kerja (volume = jumlah bulan) | PP5 | ls |
| Pembersihan & pengupasan lahan | G12 "(c) 1 m2 Pembersihan …" | m2 |
| Urugan pasir bawah lantai | K85 | m3 |
| Pemadatan pasir | G90 | m3 |
| Lantai kerja (plur) | F112 | m2 |
| Pasangan bata ringan 10 cm mortar instan (default template) | PW11 | m2 |
| Plester 10 mm (default template) / 5 mm | PD1 / PD2 | m2 |
| Aci 5 mm (dinding cat) / aci ekspos | AD1 / AD2 | m2 |

## Dinding (`wall_specs`)
| Tampak di SKP | tipe | Aci | Finishing interior | Finishing eksterior |
|---|---|---|---|---|
| Abu/semen bertekstur | `ekspos` | AD2 | W6 coating Klirkote | W6 |
| Tanpa material / putih | `putih` | AD1 | W1 Catylac | W2 Weathershield (atau W20 TOA) |
| Bata/terracotta | `terracotta` | AD1 | W76 | W76 |
Lain: W37 dinding kayu Taco, C5 WPC Duma (cladding), W53 secondary skin metal cutting, W39 roster beton, PW3 bata merah, PW7 GRC.

## Lantai, tangga, plafon
F20 keramik 60x60 grey · F28 keramik 60x60 cementous · F8 semen ekspos · F66 decking Conwood · F61 WPC decking · F36 stepnosing · F114 koral sebar · F115 batu split · C1 gypsum · C2 GRC · C4 cat plafon · WP1 waterproofing SIKA.
Railing: L1 expanded metal · L2 grip kayu · L3 railing metal (handle saja) · L12 kaca tempered + stainless.

## Atap
RF4 baja ringan C75 · RF2 rangka hollow · RF6 baja konvensional · R20 spandek pasir · R22 spandek transparan · R12/R19 UPVC · R5 polycarbonate · R14 insulasi bubble foil · R10 talang galvalum · R16 talang plat · R24/R25 nok.

## MEP (estimasi bila tidak dimodelkan)
PE1 titik lampu · PE2 titik stop kontak · E5 downlight · E19 outbow · E1/E2/E3 stop kontak/saklar · E12 SK AC · E13 instalasi panel · E14 box panel · E16 MCB 10A.
PL1/PL2/PL3 pipa AW ½–1" · PL6/PL8 2–3" · PL13 PVC D 4" · BK1 bak kontrol · ST1 bio septic · TO1 toren 1200 L · PJ jet pump · SR2 roof drain · SU1–SU3 sumur resapan.
SC3 kloset · SJ1 jet washer · SW3 wastafel · SF1 floor drain · SK1 kran.

## Tidak ada di AHS (pakai `audit`)
- Pembersihan lokasi rutin per bulan (dulu PP3) → `AUD-01`.
- Plester aci openingan kusen per m1 (dulu X-01) → `OPK` (komponen PD2 + AD1 dari AHS + upah tali air).
- Semua kusen/pintu/jendela → kode tipe P/J/PJ dengan analisa di tab Audit bagian B.
- Struktur (pondasi, kolom, balok, pelat) belum dihitung bila model struktur belum ada → baris `note`.
