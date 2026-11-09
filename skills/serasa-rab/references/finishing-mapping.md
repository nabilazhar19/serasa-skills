# Pemetaan material SKP → kode MASTER AHS

Kode di bawah ada di tab `MASTER AHS` template (kolom B kode, C nama, G harga basis). Selalu cek kode di master sebelum dipakai; bila tidak ada, buat analisa di tab Analisa.

## Dinding (tipe finishing di input `walls.parts`)
| Tampak di SKP | tipe | Plester | Aci | Finishing interior | Finishing eksterior |
|---|---|---|---|---|---|
| Abu/semen bertekstur (aci ekspos) | `ekspos` | PD2 | AD2 Aci Ekspos | W6 Coating Klirkote | W6 |
| Tanpa material / putih | `putih` | PD2 | AD1 | W1 Cat Interior | W2 Cat Eksterior Weathershield |
| Bata/terracotta (cat) | `terracotta` | PD2 | AD1 | W76 Cat tekstur terracota | W76 |
| Pola blok / garis nat (aci ekspos pola) | `pola` | PD2 | — (sudah di W7) | W7 Aci Ekspos Pola | W7 |
Lain: W80/W10 kamprot+cat, W1/W19/W34 cat interior, W12/W9 keramik dinding, W75 granit terrazzo, F50/F67 andesit, PW7 GRC, W71 HPL, W53 secondary skin. Override per baris dengan `"finish_code": {"putih": "W19"}` di item `walls`.

## Pasangan
PW1 bata ringan 10 cm (default) · PW2 bata ringan 7,5 · PW3 bata merah · PW6 partisi cement board · PW7 GRC rangka hollow. Roster: W39/W4/W59 roster beton; roster bata merah → analisa (lihat contoh X-08).

## Lantai
F18 granit motif kayu · F19 SPC motif kayu · F28 keramik 60x60 cementous (Niro) · F20/F29 keramik 60x60 · F14/F26 keramik 30x30 · F8 semen ekspos · F66 decking Conwood · F24/F41 decking kayu solid · F73/F50/F51 andesit · F38 grassblock · F39 koral sebar · F53 batu split · F25 lantai kerja (plur) · F36 stepnosing.

## Plafon
C1 gypsum · C2 GRC (area basah/eksterior) · C13 plafon kayu Conwood · C3 kayu ulin · C11 HPL · C12 PVC · C4 cat plafon · C7 shadow line · C6 lis plafon.

## Atap & kanopi
RF1 baja ringan C75 · RF4 baja ringan reng 1 m · RF2 rangka hollow (skylight/kanopi) · RF3 baja konvensional · R32 bitumen + underlayment multipleks (shingle) · R1/R13 genteng keramik · R12/R19 UPVC · R20 spandek · R5 polycarbonate · R27 kaca laminated · R14/R9 insulasi · R10/R16/R21 talang · R6/R24/R25 nok · WP1/WP2 waterproofing.

## MEP (bila tidak dimodelkan → estimasi, tulis "estimasi")
PE1 titik lampu · PE2 titik stopkontak · E5 downlight · E19 outbow · E20 lampu dinding outdoor · E9 sorot · E7 LED strip · E1/E2/E3 stopkontak/saklar · E12 SK AC · E24 SK waterproof · E13 instalasi panel · E14 box panel · E15/E16 MCB.
Plumbing: PL1/PL2/PL3 pipa AW 1/2–1" · PL6/PL8 2–3" · PL13 PVC D 4" · BK1 bak kontrol · ST1 bio septic · SU1–SU3 sumur resapan · TO1–TO3 toren · PJ/PB pompa · SR2 roof drain.
Sanitair: SC3 kloset · SJ1 jet washer · SW2/SW3 wastafel · SS3 shower tiang · SS1/SS4 hand shower · SF1/SF2 floor drain · SI1 sink · SK1 kran.

## Persiapan & tanah
PP3 pembersihan (per bulan; nama di master #N/A → isi Spec manual) · PP1 listrik kerja (per bulan) · AHS: "(c) 1 m2 Pembersihan dan Pengupasan Permukaan Tanah (Striping ) s.d. Tanaman Ø 2cm", "Pasangan 1 m' bouwplank", "Pembuatan 1 m’ pagar sementara seng gelombang rangka baja L.40.40.4 tinggi pagar 1.8 meter", "1 m3 urukan pasir uruk untuk volume s.d 200 m3 tanpa pemadatan secara manual", "(a) 1 m3 Pemadatan pasir setebal 15 cm menggunakan mesin Stamper Kodok secara semi mekanis".
Lanskap AHS: "Penanaman 1 m2 Rumput,Rumput Gajah Mini (Axonopus Compressus)", pohon "Penanaman 1 Buah Pohon Sedang …", semak "Penanaman 1 m2 Semak, …". Nama AHS harus **persis** (VLOOKUP ke kolom A tab AHS).

## Analisa standar (lihat examples/bku_input.json → `analisa`)
X-01 openingan kusen (m1) · X-02 pintu swing alum + HMR/HPL (m²) · X-03 hardware swing (set) · X-04 pintu/jendela kaca alum tempered 8 mm (m²) · X-05 hardware sliding (daun) · X-06 kaca mati (m²) · X-07 louvre (m²) · X-08 roster bata · X-09/X-10 kisi WPC · X-11 lisplang/flashing · X-12 grating · X-13 railing besi · X-14 bangku masif · X-15 olah lahan farm · X-K01..K20 kolam (harga ref. RBL House).
Ganti prefix `X-` dengan kode proyek bila perlu. Harga komponen `"MASTER:PD2"` / `"AHS:<nama persis>"` otomatis jadi rumus lookup.
