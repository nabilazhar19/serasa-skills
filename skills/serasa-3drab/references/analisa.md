# Analisa harga non-AHS (tab Audit) — wajib rinci

Dipakai untuk semua pekerjaan yang tidak punya padanan tepat di AHS: kusen/pintu/jendela, roster, grating, railing, paket
khusus. **Tidak wajib menyambung ke AHS.** Satu baris "luas × harga paket" tidak diterima kecuali harganya penawaran
supplier per m² (tulis di `src`).

## Bentuk di input (`audit[]`)
```json
{"code": "P1", "group": "kusen", "sat": "unit",
 "name": "Pintu rangka aluminium 4 inci, kaca tempered 6 mm, 1 daun; 90,0 × 240,0 cm",
 "note": "Ukuran dari model (bbox kusen), daun menghadap Koridor",
 "dimension_recipe": {"kind": "strip", "params": {"panels": 1, "frame": 0.04, "glazed": true}},
 "dimensions": {"w": 0.9, "h": 2.4},
 "components": [
   {"name": "Kusen aluminium powder coat 4 inci; 5,70 m + susut 5%", "name_template": "Kusen aluminium powder coat 4 inci; {frame_m:.2f} m + susut 5%",
    "sat": "m1", "formula": "frame_m*1.05", "koef": 5.98, "price": 69000,
    "src": "Platinum Aluminium • 13-11-2026", "price_status": "market_reference", "url": "https://…"},
   {"name": "Engsel stainless 4 inci, 3 buah per daun", "sat": "buah", "formula": "3*panels", "koef": 3, "price": 85000,
    "src": "Estimasi anggaran • 13-11-2026", "price_status": "estimated"},
   {"name": "Upah pasang kusen + daun", "sat": "m2", "formula": "area", "koef": 2.16, "price": 175000,
    "src": "AHS:Pemasangan … (bila ada) / estimasi", "price_status": "estimated"}
 ]}
```
- `price` angka (Rp, sebelum koefisien IKK — builder mengalikan `$F$file`) atau `"AHS:<uraian AHS persis>"` (VLOOKUP).
- `src` = sumber + tanggal; `url` bila ada (jadi tautan di kolom Sumber). `price_status`: `ahs` | `supplier` | `market_reference` | `estimated`.
- `formula` + `dimension_recipe` → koefisien dihitung ulang otomatis saat ukuran bukaan di SKP berubah (viewport,
  `core/analysis.py`). Parameter: `w h area frame_m seal_m panels leaf_w leaf_h leaf_m glass_w glass_h glass_area glass_m
  bill_glass_area glass_panels infill_area infill_m` (+ `_mm` untuk ukuran). Rumus hanya `+ - * / min max ceil`.
- `kind`: `strip` (pintu/jendela berangka daun; `glazed` = berkaca), `slide` (geser; `overlap`, `leaf_w_override`),
  `fixed` (kaca mati berkusen), `frameless` (kaca tanpa kusen daun).
- Kode sama dipakai banyak bukaan berukuran sama. Bila satu bukaan berubah ukuran, viewport memecahnya jadi kode baru.

## Komponen minimum per jenis
| jenis | komponen (urut) |
|---|---|
| Pintu kayu swing | kusen kayu (m³ atau m1 profil, susut), daun (panel/solid core, m² atau unit), engsel 3/daun, handle+body kunci+silinder /daun, door stop, cat/politur (m²), sekrup & angkur, upah kusen, upah daun |
| Pintu/jendela aluminium swing/casement | kusen aluminium (m1, susut 5%), profil daun (m1), kaca (m², min 0,5 m²/lembar) + gosok tepi, lis/U-channel, karet 2 sisi, engsel/hinge per daun, handle/kunci per daun, sealant (tube), backer rod, sekrup-fisher-angkur (jarak 400 mm), upah |
| Pintu/jendela geser | kusen + rel atas/bawah, profil daun, roda 2/daun, kaca, karet & sikat, kunci geser, sealant, angkur, upah |
| Kaca mati / etalase | kusen, kaca (tebal & jenis), gosok tepi, lis, karet, sealant, angkur, upah |
| Kaca frameless swing | kaca tempered 10–12 mm, floor hinge/patch fitting, handle tarik, kunci lantai, sealant, upah |
| Roster | modul roster (buah = luas ÷ luas modul, susut 5%), adukan, plester/aci tepi bila ada, upah per m² |
| Grating / railing baja | baja (kg dari m² × kg/m² atau m1 × kg/m1), cat dasar + finish, angkur/baut, las & fabrikasi, upah pasang |

Hardware dihitung **per daun / per set**, bukan per m². Bahan yang ikut ukuran memakai `formula`.

## Harga
1. AHS (MASTER AHS → AHS) bila ada padanan per komponen → `"AHS:<uraian>"`.
2. Harga pasar: ≥1 sumber (situs supplier/distributor/marketplace) → `market_reference`, tulis toko + tanggal + url.
3. Tidak ketemu: estimasi wajar → `estimated`, tulis "Estimasi anggaran • tanggal". Laporkan di akhir (daftar komponen estimasi).
4. Spesifikasi yang belum pasti (tebal kaca, seri aluminium, kelas hardware): ambil usulan dari model/kebutuhan tipe, tulis di
   `note`, dan sebut di laporan sebagai keputusan pengguna (dampak biaya).

## Tab Audit
Builder menulis: Kode | Uraian / Komponen | Satuan | Koef | Harga Komponen | Jumlah (=D×E) | Sumber | Harga Satuan (=SUM) |
Dipakai di RAB (rentang baris, mis. `RAB: F512:F530`). Harga satuan di RAB merujuk sel Harga Satuan analisa.
