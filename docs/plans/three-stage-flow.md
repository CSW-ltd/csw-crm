# Uch bosqichli jarayon (qizil → sariq → yashil) — kelishuvlar

Foydalanuvchi bilan 2026-10-30 da grill-me savollari orqali kelishildi. PR #12 da qilingan qismlar ✅ bilan, keyingilari ⏳ bilan belgilangan.

## Bosqichlar
| Rang | Holat | Kimda |
|---|---|---|
| 🔴 Qizil | mashina biriktirilmagan | GPS: «Biriktirilmagan arizalar». 72 soat teskari timer, rang to'qlashadi, 72 soatdan keyin qora. Yangi karta tushganda ovozli alert |
| 🟡 Sariq | mashina biriktirilgan, chiqindi olinishi va varaqa qaytishi kutilmoqda | GPS «Biriktirilganlar», legal «Jarayonda», haydovchi «Biriktirilgan murojaatlar». Timer: biriktirilganiga N soat. Legal va haydovchi uchun ham ovozli alert |
| 🟢 Yashil | bajarilgan | legal va haydovchidagi «Bajarilganlar» |

## Qarorlar
- ✅ **Haydovchi paneli** ishlaydi (foto + imzoli dalolatnoma). Planshetda yakunlansa darhol yashil. Planshetsiz haydovchilar uchun buyurtma varaqasi yo'li parallel ishlaydi.
- ✅ **Smena logikasi olib tashlandi.** GPS panelida «Haydovchilar va smenalar» o'rniga «Kunlik ish jadvali» bor: mashina → haydovchi → xizmat turi (yuridik / jismoniy, mahallalar). Haydovchi smenasiz ishlaydi.
- ✅ **Mashina dropdowni.** GPS tumani mashinalari ko'rsatiladi. Bugun yuridik bo'lim uchun ishlayotganlar yuqorida turadi, ichida korxonagacha masofa bo'yicha o'sish va kamayish tartibi bor. Haydovchi jadvaldan olinadi.
- ✅ **Mashina joylashuvi** tashqi GPS-monitoring tizimidan keladi. Hozircha faqat API joyi tayyor: `POST /api/v1/integrations/vehicle-positions`, `GET/PUT /api/v1/integrations/schedule`, `X-Api-Key` = `INTEGRATION_API_KEY`. Haydovchi plansheti ham joylashuv yuboradi.
- ✅ **Korxona maxsus raqami** STIR o'rniga ishlatiladi. Format: 3 ta tasodifiy harf va 2 ta raqam, chiziqchasiz (`KTR47`). O, I va Q harflari yo'q. Raqam doimiy va avtomatik beriladi.
- ✅ ~~STIR takrorlanishi mumkin~~ → PR #13: **STIR unikal** (foydalanuvchi qarori), band bo'lsa «STIRni xato kiritdingiz». STIR orqali Soliq API'dan ma'lumot — keyin.
- ✅ **Buyurtma varaqasi** GPS mashina biriktirganda yaratiladi.
  - Ochiq 7 xonali raqami bor: hamma ko'radi va u bilan qidiradi.
  - Maxfiy 7 belgili tasdiq kodi faqat chop etilgan PDF'da bo'ladi, ikkala qismda ham. Ekranda va API'da kod yo'q, bazada faqat HMAC xeshi saqlanadi.
  - GPS varaqani bir marta chop etadi. Qayta chop etish uchun manager ruxsati kerak va yangi kod beriladi. Chop etishlar jurnalga yoziladi.
  - Kod 3 marta noto'g'ri kiritilsa varaqa bloklanadi va Vaziyat paneliga xabar tushadi. Blokni manager ochadi.
  - Kod faqat qo'lda kiritiladi, QR ishlatilmaydi.
  - Faqat yangi chop etilgan varaqalar ishlatiladi: raqami oldindan bosilgan eski daftarlar ishlatilmaydi.
  - GPS kodni chop etishda ko'rishi mumkin. Bu nazorat bilan qabul qilingan: murojaatni faqat legal yopadi.
- ✅ **Legal yopishi.** Tartib: skan (majburiy) → maxfiy kod → forma avtomatik to'ladi → kub va chiqindi turi (bularsiz forma yopilmaydi) → «Murojaatni yopish» → yashil.
- ⏳ **GPS-monitoring geozonasi:** mashina korxona yonida bo'lmagan bo'lsa murojaat yopilmaydi. Monitoring API ulangach qo'shiladi.
- ✅ **Buxgalter tasdiqlagan yangi shartnoma** bo'yicha murojaat GPS'ga qizil kartada «Yangi shartnoma» pilli bilan tushadi. Bu qaror qabul qilingan, pilli PR #13 da qo'shiladi.

## Keyingi bosqichlar
- ⏳ **PR #13:**
  - legal «Yangi korxonalar» tabi (sariq, timer bilan);
  - shartnoma formasi → «Tekshirish» → qog'oz ko'rinishi → «Buxgalteriyaga yuborish»;
  - buxgalter roli va tasdiqlash;
  - «Qilingan shartnomalar» bo'limi (yashil);
  - GPS'da «Yangi shartnoma» pilli.
- ⏳ **PR #14:**
  - buxgalteriya tizimi (1C'ga o'xshash, o'zimizniki, API bilan);
  - debitor va kreditor, ikki davrni solishtirish;
  - legal «Mening korxonalarim» tabi: jami korxonalar soni va jadval (nom, maxsus raqam, debitor, kreditor, jami kub — bosilganda tartiblanadi);
  - jadvaldagi har bir raqam bosilsa batafsil oyna ochiladi;
  - sariq kartada debitor va kreditor pillari.
- ⏳ Haydovchilar uchun Telegram bot (planshetdagi jarayon bilan bir xil). PR #14 dan keyin.
- ⏳ O'zimizning GPS-monitoring tizimi (GPS paneli ichida) va jismoniy abonentlar bilan ishlash. Yuridik bo'lim qismi tugagach boshlanadi.

## PR #13 qarorlari (2026-10-31)
- «Ariza» → «murojaat», raqamlar `M-`. Admin/manager uchun yagona «Murojaatlar» ro'yxati (4 rang, 12/72/144 soat panellari).
- Operator yangi korxonasi: telefon, STIR, kutib oluvchi → darhol maxsus raqam + SMS (Eskiz.uz); legal navbatiga.
- Debitor/kreditor hozircha tizim ichida (narx × kub, qo'lda to'lovlar) — buxgalteriya tizimi API'si tayyor bo'lgach o'tkaziladi (PR #14).

## PR #16 qarorlari (2026-10-31)
- Yozishma (chat) butunlay olib tashlandi; keyinchalik boshqa formatda qaytishi mumkin.
- Admin/manager «Korxonalar › Statistika»: «Tumanlar kesimida» jadvali yo'q (5 panel + tuman tanlovi qoladi). Debitor/kreditor/kub
  sahifasidan «Orqaga» — kelingan bo'limga (admin/manager: Korxonalar › Statistika; legal/buxgalter: Korxonalar).
- Buxgalteriyaga har bir yashil buyurtma varaqasi tushadi; summa amaldagi shartnoma bo'yicha (kub yoki reys).
- Oyiga bir marta har korxonaga bitta schyot-faktura; narx QQS bilan; oylik shartnomada bitta qator + varaqalar ilova.
- Jo'natish: SMS + PDF havola. E-faktura (Didox/Soliq) — keyin.
- Keyingi: «Yangi shartnoma» to'liq jarayoni (forma → tekshirish → qog'oz → buxgalteriya tasdig'i → yashil ro'yxat + GPS pilli).

## PR #17 qarorlari (2026-10-31)
- Shablon namunalari: Surxondaryo — Didox shartnomasi, Andijon — hujjat.uz «Ommaviy shartnoma». Viloyat bo'yicha avtomatik tanlanadi.
- Imzo: elektron ham, qog'oz ham. Raqam: ichki avtomatik + platforma ID (imzolangach).
- Imzolangandan keyin darrov faol (murojaat ochiladi); buxgalter rad etsa — izoh bilan legalga qaytadi.
- Hisob-kitob faqat buxgalter tasdig'idan keyin.
- Shartnomada yillik hajm va summa jadvali (QQS 12% ichida, summa so'z bilan).
- Keyingi: «Qo'shimcha kelishuv» (hajm/tarif o'zgarishi), Didox / hujjat.uz / my.soliq integratsiyasi.

## PR #18–#20 qarorlari (2026-11-02)
- Varaqa printerdan chiqqani tasdiqlanmaguncha murojaat qizil; tasdiq — printer agenti (PR #20), hozircha agentsiz rejim (tuman bo'yicha).
- Ta'rif: viloyat → tuman/shahar, sanadan; manager o'z tumanlari, admin hammasi va qulf. Hisob — varaqa yopilgan kundagi ta'rif.
- Mavjud shartnomalar: bittalab + Excel; darhol tasdiqlangan.
- PR #19: bir xil STIR — bosh kompaniya; xarita nuqtasi (30 m) va telefon bo'yicha takror; maktab/bog'cha — hududiy boshqarma
  (ochiq manbalardan, tekshirish kerak); takrorlar — buxgalter va manager Vaziyat paneliga.
- PR #20: printer agenti (Windows/Linux, USB va tarmoq printer).
