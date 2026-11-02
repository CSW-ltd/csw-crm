"""Shartnoma shablonlari (viloyat bo'yicha). Matn namunalardan olingan; tomonlar, summa va sanalar formadan qo'yiladi.

Blok turlari (PDF va DOCX bir xil chiqariladi — app.services.contract_doc):
  ("title", matn)            — markazda, qalin, katta
  ("pair", chap, o'ng)        — bir qatorda chapda va o'ngda (joy / sana)
  ("h", matn)                 — bo'lim sarlavhasi (markazda, qalin)
  ("p", matn)                 — oddiy xatboshi (eni bo'yicha tekislangan)
  ("table", {"head": [...], "rows": [[...]], "foot": [...]})
  ("req", {"left_title", "right_title", "left": [(nom, qiymat)], "right": [...]})
  ("sign",)                   — qog'oz imzo bo'lsa imzo/muhr joylari

Kontekst kalitlari: app.services.contracts.context() da tuziladi. Bo'sh qiymatlar o'rniga «______».
"""
MXIK = "09904002001000000"
MXIK_NAME = "Qattiq maishiy chiqindilarni (QMCh) olib ketish xizmati"


# --- Surxondaryo (Didox) va standart shablon ---
def didox(c: dict) -> list:
    return [
        ("title", "Шартнома"),
        ("title", f"Шартнома №{c['number']}"),
        ("pair", f"{c['place']}\n(шартнома тузиш жойи)", f"{c['date']}\n(шартнома тузиш сана)\n{c['valid_to']}\n(шартнома шу вақтгача амал қилади)"),
        ("p", f"{c['provider_name']} (бундан буён - \"Бажарувчи\" деб аталади) номидан ҳаракат қилувчи директор {c['provider_director']}, бир "
              f"томондан, ва {c['customer_name']} (бундан буён – \"Буюртмачи\" деб аталади) номидан ҳаракат қилувчи директор "
              f"{c['customer_director']}, иккинчи томондан, биргаликда “Тарафлар”, алоҳида эса “Тараф” деб аталувчилар мазкур шартномани "
              f"қуйидагилар ҳақида туздилар:"),
        ("h", "1. MAZKUR SHARTNOMADA QO‘LLANILGAN ASOSIY TUSHUNCHALAR"),
        ("p", "Ушбу шартномага биноан, Мижоз тўлайди ва қабул қилади ва Ижрочи қуйидаги шартлар асосида товарларни (хизматларни) етказиб беради:"),
        ("table", {
            "head": ["№", "Маҳсулот номи (хизматлар)", "Товар (хизмат)лар Ягона электрон миллий каталоги бўйича идентификация коди ва номи",
                     "Ўлчов бирлиги", "Миқдори", "Нарх", "Етказиб бериш қиймати", "ҚҚС ставка", "ҚҚС сумма", "Етказиш баҳоси ҚҚС билан"],
            "rows": [["1", "QMChlarni chiqarish", f"{MXIK} - {MXIK_NAME}", c["unit"], c["qty"], c["unit_net"], c["net"], "12 %", c["vat"], c["total"]]],
            "foot": ["", "Жами", "", "", "", "", c["net"], "", c["vat"], c["total"]],
            "widths": [5, 14, 30, 10, 10, 13, 15, 8, 13, 15],
        }),
        ("p", f"Шартноманинг умумий миқдори {c['total_words']} (сумма сўзлар билан), ({c['total']})"),
        ("p", "qattiq maishiy chiqindilar – jismoniy shaxslarning hayoti va faoliyati hamda yuridik shaxslarning faoliyati natijasida hosil bo‘luvchi "
              "organik va noorganik chiqindilar, shuningdek, ular hududida va obodonlashtirish obyektlaridagi tabiiy jarayonlar natijasida hosil "
              "bo‘luvchi chiqindilar (oziq-ovqat va o‘simlik chiqindilari, to‘qimachilik mahsulotlari, o‘rash-joylash (qadoqlash) materiallari, shisha, "
              "rezina, qog‘oz, plastmassa, yog‘och chiqindilari, o‘zining foydalanish xususiyatlarini yo‘qotgan uy-ro‘zg‘or buyumlari, supurindi, "
              "shuningdek, qattiq yoqilg‘ida ishlovchi maishiy pechkalar va isitish bug‘ qozonlaridan foydalanish natijasida hosil bo‘luvchi chiqindilar);"),
        ("p", "suyuq maishiy chiqindilar – jismoniy shaxslarning hayoti va faoliyati hamda yuridik shaxslarning faoliyati natijasida hosil bo‘luvchi "
              "chiqindilar (oqova suvlar, chiqindi to‘kiladigan o‘ralar va septiklarda yig‘ilgan turli xil suyuq chiqindilar, ishlab chiqarish "
              "jarayonida hosil bo‘ladigan yuvindi chiqindilari, markazlashtirilmagan kanalizatsiyaning najas chiqindilari);"),
        ("p", "qurilish chiqindilari – uylar, ma’muriy bino, ko‘p kvartirali uy kvartiralarini qurishda, rekonstruksiya qilishda, ta’mirlashda va "
              "buzishda hosil bo‘ladigan chiqindilar;"),
        ("p", "“signal” usuli – chiqindi tashish texnikasi bilan aholi yashash punktlarini aylanib chiqib, signal berish yo‘li bilan Iste’molchilarni "
              "xabardor qilish orqali yakka tartibdagi turar joy sektoridagi qattiq maishiy chiqindilarni to‘plash va olib chiqib ketish."),
        ("h", "2. SHARTNOMA PREDMETI"),
        ("p", "2. Ijrochi Iste’molchiga tegishli maishiy chiqindilarni vaqtinchalik to‘plash va saqlash joylariga joylashtirilgan konteynerlarga, "
              "shuningdek, umumfoydalaniladigan chiqindi to‘plash shoxobchalariga joylashtirilgan chiqindilarni olib chiqib ketadi, Iste’molchi esa "
              "ushbu xizmatlar uchun mazkur shartnomada belgilangan miqdorda va tartibda haq to‘laydi."),
        ("h", "3. IJROCHI TOMONIDAN KO‘RSATILADIGAN XIZMATLAR VA XIZMAT KO‘RSATISH TARTIBI"),
        ("p", "3.1. Ijrochi tomonidan yuridik shaxs va YATTlarga quyidagi xizmatlar ko‘rsatiladi:\n"
              "a) qattiq maishiy chiqindilar (bundan keyingi o‘rinlarda – QMCh)ni to‘plash, olib chiqib ketish;\n"
              "b) suyuq maishiy chiqindilarni to‘plash va olib chiqib ketish xizmatlari ko‘rsatiladi."),
        ("p", "3.2. Qo‘shimcha xizmat turlari:\n"
              "a) Qurilish chiqindilar (qum, tosh, beton, tuproq, shifer siniqlari va boshqalar) tomonlarning o‘zaro kelishuviga binoan qo‘shimcha haq "
              "to‘lash asosida amalga oshiriladi.\n"
              "b) Agrotexnik ishlardan chiqadigan chiqindilar (shox-shabbalar, butalar va boshqalar) tomonlarning o‘zaro kelishuviga binoan qo‘shimcha "
              "haq to‘lash asosida amalga oshiriladi."),
        ("p", "3.3. Xizmat ko‘rsatish shakllari:\n"
              "a) “Maishiy chiqindilarni vaqtinchalik to‘plash va saqlash” joylariga, shu jumladan konteynerlarga ega bo‘lmagan Iste’molchi "
              "umumfoydalaniladigan chiqindi to‘plash shoxobchalariga chiqindilarni joylashtiradi, Ijrochi mazkur QMChni olib chiqib ketilishini signal "
              "usulida amalga oshiradi.\n"
              "b) Iste’molchiga tegishli “Maishiy chiqindilarni vaqtinchalik to‘plash va saqlash” joylariga joylashtirilgan konteynerlardan "
              "chiqindilarni tashib chiqib ketish yuzasidan xizmatlar faqatgina Ijrochining dispetcherlik xizmati (1348 qisqa raqamli murojaatlar "
              "markazi)ga kelib tushgan buyurtmanomalar orqali amalga oshiriladi."),
        ("h", "4. SHARTNOMA BAHOSI VA HISOB KITOB QILISH TARTIBI"),
        ("p", f"4.1. Shartnomaning 2.1-bandi “a” kichik bandi yuzasidan ko‘rsatilgan xizmatlar narxi bir kubga QQS bilan {c['price']} "
              f"({c['price_words']}) so‘mni tashkil qiladi. Bunda Buyurtmachi har oyning 10 sanasiga qadar 100 foiz miqdorda to‘lovni amalga oshiradi."),
        ("p", "4.2. Iste’molchiga tegishli “Maishiy chiqindilarni vaqtinchalik to‘plash va saqlash” joylariga joylashtirilgan konteynerlardan "
              "chiqindilarni tashib chiqib ketish narxi quyidagi jadvalga asosan belgilanadi. Bunda Iste’molchi hisobot oyining 10-sanasiga qadar har "
              "oylik to‘lovni 100 foiz miqdorida oldindan amalga oshirib boradi."),
        ("p", "4.3. Amalga oshirilgan xizmatlar bo‘yicha kechiktirilgan qarzdorlik yuzaga kelgan taqdirda “O‘zbekiston Respublikasida naqd pulsiz "
              "hisob-kitoblar to‘g‘risida”gi Nizom talablariga ko‘ra Ijrochi Iste’molchiga xizmat ko‘rsatuvchi bankga (Iste’molchining to‘lov "
              "talabnomasida ko‘rsatilgan mablag‘ni tan olish haqidagi xati yoki solishtirma dalolatnomani ilova qilgan holda) mazkur qarzdorlikni "
              "akseptsiz ushlab qolish haqida talabnoma yuborish orqali qarzdorlikni bartaraf etish choralarini ko‘rib boradi. Bunday bank operatsiyasi "
              "Iste’molchini oldindan ogohlantirishsiz, to‘lov muddati kelgan sanada va undan keyingi har qanday sanada amalga oshirilishi mumkin hamda "
              "amalga oshirilgan bu turdagi bank operatsiyasi haqida Iste’molchiga alohida xabarnoma yuborilmaydi."),
        ("p", "4.4. Qattiq va suyuq maishiy chiqindilarni olib chiqib ketish bo‘yicha ko‘rsatilayotgan xizmatlar uchun to‘lovni hisoblash tegishli "
              "davrlarda amalda bo‘lgan tariflar bo‘yicha amalga oshiriladi. Mazkur tariflar o‘zgargan taqdirda, to‘lovlar amaldagi yangi tarif "
              "bo‘yicha amalga oshiriladi, bunda shartnomaga o‘zgartirish kiritish talab etilmaydi. Tariflar o‘zgargan kundan e’tiboran 5 (besh) ish "
              "kuni ichida Ijrochi Iste’molchini OAV orqali yoki yozma ravishda xabardor qiladi. Mazkur xabar Iste’molchidan o‘zgargan tarif bo‘yicha "
              "to‘lovlarni undirishga asos bo‘ladi."),
        ("p", "4.5. Qattiq va suyuq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar uchun to‘lovlar majburiy hisoblanadi."),
        ("p", "4.6. Shartnomaning 4.1 va 4.2-bandida ko‘rsatilgan mablag‘dan ortiqcha bajarilgan ish hajmining mablag‘ini to‘lab berish "
              "Iste’molchining zimmasiga yuklanadi."),
        ("h", "5. TARAFLARNING HUQUQ VA MAJBURIYATLARI"),
        ("p", "5.1. Ijrochi quyidagi huquqlarga ega:\n"
              "a) QMChni olib chiqib ketish bo‘yicha Iste’molchilarga ko‘rsatilgan xizmatlar uchun to‘lovlarni qonun hujjatlarida belgilangan tartibda, "
              "o‘z vaqtida va to‘liq hajmda olish;\n"
              "b) yirik gabaritli, qurilish chiqindilari, shox-shabbalar, butalar va boshqa chiqindilarni alohida to‘lov evaziga olib chiqish bo‘yicha "
              "qo‘shimcha xizmatlar ko‘rsatish;\n"
              "c) Iste’molchi tomonidan shartnoma shartlari bajarilmaganligi uchun javobgarlikka tortish choralarini ko‘rish. Shartnoma shartlari "
              "bajarilmaganligi natijasida kelib chiqqan zararlarni undirish;\n"
              "d) Shartnomaning 4.1, 4.2 bandlarida ko‘rsatilgan tarif miqdori o‘zgargan taqdirda xizmatlar ko‘rsatishni yangi tarif bo‘yicha amalga "
              "oshirish;\n"
              "e) Iste’molchi tomonidan dispetcherlik xizmati (1348 qisqa raqamli murojaatlar markazi) orqali berilmagan har qanday buyurtmalar "
              "yuzasidan xizmatlar ko‘rsatilmaydi;\n"
              "f) Ijrochi qonun hujjatlariga muvofiq boshqa huquqlarga ham ega bo‘lishi mumkin."),
        ("p", "5.2. Ijrochi quyidagilarga majbur:\n"
              "a) o‘ziga biriktirilgan hududda fuqarolarning o‘zini o‘zi boshqarish organlari bilan kelishilgan jadvalga muvofiq belgilangan tartibda "
              "QMChning muntazam olib chiqib ketilishini amalga oshirish (konteynerlarga ega bo‘lmagan Iste’molchilarga ta’luqli);\n"
              "b) QMChni olib chiqib ketish bo‘yicha xizmatlar uchun elektron tizimini tatbiq etish va real vaqt rejimida shaxsiy hisob varaqlarning "
              "holatini kuzatib borish;\n"
              "c) QMChni olib chiqib ketish xizmatlarining amalga oshiriladigan rejimi vazifasi bo‘yicha Iste’molchining murojaatlari (arizalari, "
              "takliflari, shikoyatlari) shuningdek ularning ijrosini hisobini olib borish;\n"
              "d) Chiqindi yig‘iladigan maskanlarni va konteynerlarni tegishli holatda bo‘lishini nazorat qilish;\n"
              "e) Olib chiqib ketilgan chiqindilar hisobini yuritish;\n"
              "f) Iste’molchiga chiqindini olib chiqib ketish uchun ko‘rsatilgan xizmat uchun to‘lovlar amalga oshirilganligi haqidagi ma’lumotlarni "
              "bepul taqdim etish, shuningdek qarzdorligi mavjud emasligi haqidagi ma’lumotnoma berish (qarzdorligi mavjud bo‘lgan hollar bundan "
              "mustasno);\n"
              "g) Iste’molchi tomonidan QMChni olib chiqib ketish yuzasidan Ijrochining dispetcherlik xizmati (1348 qisqa raqamli murojaatlar "
              "markazi)ga kelib tushgan buyurtmanomalarni operativ tartibda, biroq buyurtmanoma kelib tushgan kundan boshlab uch ish kunidan "
              "kechiktirmay bajarishi shart."),
        ("p", "5.3. Iste’molchi quyidagi huquqlarga ega:\n"
              "a) Ijrochidan qattiq va suyuq maishiy chiqindilarni olib chiqib ketish xizmatlarining hajmi va sifati, ularning ko‘rsatilishi shartlari, "
              "xizmatlar uchun to‘lov miqdorlarining o‘zgargani va to‘lov tartibi to‘g‘risidagi axborotlarni olish, xizmatlar uchun elektron to‘lov "
              "tizimi orqali to‘lash va real vaqt rejimida shaxsiy hisob varaqalarning holatini kuzatib borish;\n"
              "b) QMChni o‘z vaqtida tashib chiqib ketilishini doimiy nazorat qilish, xizmat ko‘rsatish muddatlari buzilgan hollarda Ijrochiga yozma "
              "ravishda xabar berish;\n"
              "c) o‘n ikki oydan ortiq bo‘lmagan davr uchun oldindan haq to‘lash;\n"
              "d) Iste’molchi qonun hujjatlariga muvofiq boshqa huquqlarga ham ega bo‘lishi mumkin."),
        ("p", "5.4. Iste’molchi quyidagilarga majbur:\n"
              "a) qattiq va suyuq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha ko‘rsatilgan xizmatlar uchun to‘lovlarni ushbu shartnomada "
              "belgilangan muddatlarda va to‘liq miqdorda to‘lash;\n"
              "b) QMChni ko‘chalarga, suv yo‘llariga, ariq va QMChni to‘plash va ko‘mib tashlash uchun ajratilmagan joylarga, shuningdek, harakatdagi "
              "avtotransport vositasidan yo‘laklar va ko‘chalarning transport yuradigan qismiga tashlamaslik, chiqindilarni korxona hududida va ruxsat "
              "etilmagan joylarda ko‘mib tashlashga yo‘l qo‘ymaslik;\n"
              "c) QMChni ularni joylashtirish obyektlarida (idishlar, yer o‘ralari va hokazolar), tashkilot hududida, dalalarda va aholi yashash "
              "punktlarida yoqmaslik;\n"
              "d) qattiq va suyuq maishiy chiqindilarni maxsus avtotransport vositasiga ortish uchun Ijrochining ortish joyiga bemalol o‘tishini "
              "ta’minlash;\n"
              "e) QMCh yig‘ilishi va saqlanishi uchun maxsus konteynerlarni sotib olish yoki ijaraga olish. Bunda: Konteynerlarni chiqindi tashish "
              "mashinalariga bo‘shatish uchun ular (xavfli maishiy chiqindilar uchun maxsus konteynerlar bundan mustasno) to‘rtta g‘ildirakchalar bilan "
              "jihozlangan va mustahkam old devoriga, shuningdek, maxsus avtotransport vositasining manipulyatori bilan ishlashi uchun moslamaga ega "
              "bo‘lishi lozim;\n"
              "f) QMChni olib chiqib ketish muddatiga binoan kerakli miqdorda chiqindilarni belgilangan joyda yig‘ish;\n"
              "g) QMChni toifalarga ajratilgan holda tashlash;\n"
              "h) QMChni saqlash uchun belgilangan joylarga yong‘in chiqaradigan cho‘g‘, ko‘mir, kul va boshqa alanga oluvchi vositalarni "
              "tashlamaslik;\n"
              "i) QMChni yig‘ish va saqlash joylariga qurilish chiqindilarini tashlamaslik;\n"
              "j) QMChni yig‘ish uchun belgilangan joyiga yirik gabaritli, qurilish chiqindilari, shox-shabbalar, butalar va boshqa chiqindilarni "
              "joylashtirmaslik, aksincha ularni maxsus joyga yig‘ish hamda bu chiqindilarni tashib ketish uchun alohida buyurtma berish va qo‘shimcha "
              "to‘lovlarni amalga oshirish;\n"
              "k) hosil bo‘lgan chiqindilarni olib ketish uchun maxsus chiqindi avtomashinalariga qulay joyga yig‘ish va uning erkin harakatlanishini "
              "ta’minlash;\n"
              "l) “Chiqindilar to‘g‘risida”gi qonun va boshqa chiqindi sohasidagi normativ-huquqiy hujjatlarga zid faoliyat yuritmaslik.\n"
              "m) Maishiy chiqindilarni vaqtinchalik to‘plash va saqlash joylariga, shu jumladan konteynerlarga ega bo‘lmagan Iste’molchi hosil bo‘lgan "
              "maishiy chiqindilarni _____________ tuman (shahar), _____________ ko‘chasida joylashgan chiqindi yig‘ish maydonchalari va maxsus "
              "konteynerlarga joylashtirishi lozim.\n"
              "n) Chiqindilarni olib chiqib ketish yuzasidan buyurtmalarni Ijrochining dispetcherlik xizmati – 1348 qisqa raqamli murojaatlar markazi "
              "orqali berish.\n"
              "o) Buyurtmanoma orqali amalga oshirilgan xizmatlar yuzasidan Ijrochi tomonidan taqdim qilingan avtonaryad (buyurtmalar varaqasi)ni qabul "
              "qilish, avtonaryadni muntazam ravishda to‘liq (chiqindi hajmini aniq ko‘rsatgan holda) tasdiqlashi (to‘ldirishi) hamda uning bir "
              "nusxasini Ijrochining xizmat ko‘rsatuvchi xodimiga taqdim qilishi shart. Mazkur vazifalarni amalga oshirish uchun Iste’molchi tomonidan "
              "mas’ul xodim tayinlanadi hamda u haqidagi ma’lumot (F.I.SH., lavozimi, telefon raqami)lar Ijrochiga taqdim etiladi."),
        ("p", "Iste’molchi avtonaryadni lozim darajada tasdiqlamagan (to‘ldirmagan) yoki tasdiqlashdan (to‘ldirishdan) bosh tortgan holatlarda Ijrochi "
              "mustaqil ravishda (ikki nafar xolis ishtirokida) dalolatnoma rasmiylashtiradi hamda mazkur dalolatnomaga asosan to‘lovlarni talab qiladi."),
        ("h", "6. TOMONLARNING JAVOBGARLIKLARI"),
        ("p", "6.1. Ijrochi quyidagi hollarda javobgar bo‘ladi:\na) xizmat ko‘rsatish muddati buzilganda;\n"
              "b) shartnoma bo‘yicha lozim darajada xizmat ko‘rsatilmaganda."),
        ("p", "6.2. Iste’molchi quyidagi hollarda javobgar bo‘ladi:\n"
              "- Iste’molchi to‘lovlarni to‘lashni shartnomada ko‘rsatilgan muddatdan kechiktirgan taqdirda kechiktirilgan har bir kun uchun belgilangan "
              "muddatda to‘lanmagan summaning 0,4% miqdorida, lekin kechiktirilgan to‘lovning 50% dan oshmagan miqdorda penya to‘laydi;\n"
              "- To‘lov talabnomasi akseptini asossiz ravishda butunlay yoki qisman rad etganlik, shuningdek hisob-kitobning boshqa shakllarida "
              "xizmatlar haqini to‘lashdan bosh tortganlik (bank muassasasiga to‘lov topshiriqnomasini taqdim etmaganlik, chek bermaganlik, akkreditivni "
              "taqdim etmaganlik va hokazo) uchun Iste’molchi Ijrochiga o‘zi to‘lashni rad etgan yoki bosh tortgan summaning 15 foizi miqdorida jarima "
              "to‘laydi;\n"
              "- mazkur shartnomaning 5.4-bandida nazarda tutilgan majburiyatlar lozim darajada bajarilmagan taqdirda, Iste’molchi Ijrochiga yetkazilgan "
              "zararni to‘liq hajmda qoplab beradi."),
        ("p", "6.3. Iste’molchi tomonidan QMChni yashirish, hosil bo‘lgan chiqindini taqdim etmaslik yoki QMChga boshqa toifadagi chiqindilarni "
              "aralashtirish holatlari aniqlangan taqdirda, bu haqda Ijrochi dalolatnoma (bildirgi) tuzadi va uni viloyat Ekologiya va atrof muhitni "
              "muhofaza qilish boshqarmasining hududiy bo‘limlariga taqdim etadi. Ushbu dalolatnoma (bildirgi) ish to‘liq bajarildi deb hisoblanishiga "
              "va to‘liq miqdorda to‘lov amalga oshirilishiga asos bo‘ladi."),
        ("p", "6.4. Iste’molchi O‘zbekiston Respublikasi Vazirlar Mahkamasining 2018 yil 2 oktabrdagi №787-sonli qarori talabiga binoan chiqindi "
              "tashish mashinalariga bo‘shatish uchun to‘rtta g‘ildirakchalar bilan jihozlangan va mustahkam old devoriga, shuningdek, maxsus "
              "avtotransport vositasining manipulyatori bilan ishlashi uchun moslamaga ega bo‘lgan konteynerlarni chiqindixonalariga joylashtirgan "
              "bo‘lishi shart, agar ushbu konteynerlar chiqindixonalariga joylashtirilmagan bo‘lsa va chiqindixonaga maxsus avtotransport vositasining "
              "kirishiga bir qator to‘siqlar mavjud bo‘lganda, ishchilarning qo‘l kuchi bilan bajariladigan ishlarga o‘zaro kelishuvga binoan alohida "
              "xizmat haqi hisoblanadi."),
        ("p", "6.5. Buyurtmachi mazkur shartnomaning 3-bandiga muvofiq taraflar o‘zaro ixtiyoriy ravishda kelishgan summani to‘lamagan taqdirda "
              "San Pin Ruz № 0297-11 normasiga va Xalq deputatlari Surxondaryo viloyati Kengashining 2026 yil 03 fevraldagi “Viloyat hududida qattiq va "
              "suyuq maishiy chiqindilarni to‘plash hamda olib chiqib ketish xizmatlari tariflarini tasdiqlash to‘g‘risida”gi №VII-17-14-8-0-K/26-son "
              "qaroriga asosan har oyda ilovaga muvofiq qayd etilgan qat’iy summani to‘laydi."),
        ("p", "6.6. Muddatini o‘tkazib yuborish yoki shartnoma majburiyatlarini o‘zgacha tarzda lozim darajada bajarmaslik hollari uchun belgilangan "
              "neustoykani (jarimani, penyani) to‘lash hamda shartnoma majburiyatlarini lozim darajada bajarmaslik oqibatida yetkazilgan zararning "
              "o‘rnini qoplash, taraflarni majburiyatni asl holida bajarishdan ozod etmaydi."),
        ("h", "7. NIZOLARNI HAL QILISH TARTIBI"),
        ("p", "7.1. Shartnomani bajarish paytida yuzaga kelgan muammolar tomonlarning o‘zaro muzokaralari orqali hal qilinadi. Taraflar o‘rtasida "
              "shartnomani tuzish, ijro qilish, o‘zgartirish, bekor qilish, shuningdek, yetkazilgan zararni undirish yuzasidan nizolar kelib chiqqan "
              "taqdirda “XUMO-QALQONI” МЧЖ ҳузуридаги доимий фаолият кўрсатувчи Термиз туманлараро Ҳакамлик судига murojaat qilinadi."),
        ("p", "7.2. “XUMO-QALQONI” МЧЖ ҳузуридаги доимий фаолият кўрсатувчи Термиз туманлараро Ҳакамлик судига topshirilishida bitim talab "
              "qilinmaydi va mazkur shartnoma bir vaqtning o‘zida bitim kuchiga egadir, hakamlik muhokamasi taraflarining ishtirokisiz ko‘riladi va "
              "hakamlik sudiga taqdim etilgan hujjatlar asosida hal etiladi hamda hakamlik sudi taraflarni xabardor qilmaydi."),
        ("p", "7.3. Shartnoma yuzasidan kelib chiqadigan qarzdorlik bo‘yicha (qarzdorliklarini) to‘lashdan qochish yoki bo‘yin tovlash ikki "
              "tomonlama solishtirma dalolatnomaga imzo chekib muhr bosib tasdiqlanmasa mazkur shartnoma bir vaqtning o‘zida bajarilgan ishlar "
              "yuzasidan bir tomonlama solishtirma dalolatnomaga binoan undirishga qaratilgan xizmatlardan biri bo‘lib xizmat qiladi."),
        ("h", "8. KORRUPSIYAGA QARSHI KURASHISH QOIDALARI"),
        ("p", "8.1. Taraflar shartnoma bo‘yicha o‘z majburiyatlarini bajarayotganda O‘zbekiston Respublikasining Korrupsiyaga qarshi kurashish "
              "to‘g‘risidagi qonun hujjatlarining talablariga zid keladigan har qanday harakatlarni amalga oshirmaydilar, shu jumladan pora berishni "
              "taklif qilmaydi, tovlamachilik qilmaydi, bevosita yoki bilvosita pora olishga rozilik bermaydi yoki pora ya’ni xodimi o‘z xizmat "
              "majburiyatlaridan foydalangan holda pora bergan shaxsning manfaatlarini ko‘zlab muayyan harakatlarni sodir etishi yoki sodir etmasligi "
              "shartligi uchun moddiy qimmatliklarni yoki mulkiy naf olmaydi. Taraflar ushbu harakatlarga yo‘l qo‘ymaslik bo‘yicha choralar "
              "ko‘rilishiga kafolat beradi."),
        ("h", "9. SHARTNOMANI O‘ZGARTIRISH YOKI BEKOR QILISH TARTIBI"),
        ("p", "9.1. Ushbu shartnomaga barcha o‘zgartirish va qo‘shimchalar qo‘shimcha kelishuvlar tuzish orqali yozma shaklda rasmiylashtiriladi. "
              "Bunda, Qattiq va suyuq maishiy chiqindilarni olib chiqib ketish bo‘yicha ko‘rsatilayotgan xizmatlar uchun belgilangan tariflar o‘zgargan "
              "taqdirda, shartnomaga o‘zgartirish kiritish talab etilmaydi."),
        ("p", "9.2. Bir tomonlama shartnomani bekor qilishga to‘lov shartlari bajarilmaganligi asos bo‘ladi."),
        ("p", "9.3. Shartnoma predmetiga doir O‘zbekiston Respublikasi qonunchiligiga o‘zgartirish kiritilgan taqdirda, Taraflar qo‘shimcha "
              "shartnoma tuzgan holda tegishli o‘zgartirish va qo‘shimchalarni kiritishadi."),
        ("h", "10. FORS-MAJOR"),
        ("p", "10.1. Tomonlar ushbu shartnoma bo‘yicha biron-bir majburiyatning bajarilmasligi yoki lozim bo‘lmagan darajada bajarilganligi uchun, "
              "agar ushbu shartnoma kuchga kirganidan keyin bunday majburiyatlarning bajarilmasligini yoki lozim bo‘lmagan darajada bajarilganligini "
              "yengib bo‘lmaydigan kuchlar (fors-major) holatlari keltirib chiqargan taqdirda, javob bermaydilar."),
        ("p", "10.2. Tomonlar darhol (yoki boshlangan sanadan boshlab uch kalendar kunidan kechikmay) fors-major holatining boshlanish sanasi va "
              "tavsifini aniqlashtiruvchi yozma ravishda bevosita topshirish, aloqa vositalari (telefon, ijtimoiy tarmoqdagi profillar va rasmiy "
              "sahifalar) yoki pochta aloqasi orqali xabarnoma yuborish bilan xabar beradi."),
        ("p", "10.3. Yengib bo‘lmaydigan kuchlar (fors-major) holatlari vujudga kelgan taqdirda, Tomonlar darhol yuzaga kelgan vaziyatdan chiqish "
              "yo‘llarini qidirish uchun muzokaralar olib boradilar va bunday holatlarning oqibatlarini kamaytirish uchun barcha vositalarni qo‘llaydilar."),
        ("p", "10.4. Ushbu shartnoma bo‘yicha ishlarning yengib bo‘lmaydigan kuchlar (fors-major) holatlari tufayli to‘liq yoki qisman "
              "to‘xtatilishida, mazkur ishlarni olib borish davri yengib bo‘lmaydigan kuchlar (fors-major) holatlarining amal qilish muddatiga "
              "uzaytiriladi va yengib bo‘lmaydigan kuchlar (fors-major) holatlari tugagan vaqtdan boshlab davom ettiriladi."),
        ("h", "11. QO‘SHIMCHA SHARTLAR"),
        ("p", "11.1. Mahalliy hokimiyat vakilligi organi tomonidan chiqindilar uchun ko‘rsatiladigan xizmat narxlari o‘zgargan taqdirda Ijrochi "
              "belgilangan tartibda bir tomonlama xizmat narxlarini o‘zgartirishga haqlidir. Bu haqda Iste’molchiga OAV orqali ma’lum qilinadi yoki "
              "yozma ravishda xabar yuboriladi."),
        ("p", "11.2. Tomonlarning manzili, korxona nomi, hisob raqami o‘zgargan taqdirda hamda QMCh hajmi o‘zgarishiga ta’sir etuvchi omillar "
              "paydo bo‘lganda bir tomon ikkinchi tomonga 10 kun ichida yozma ma’lumot berishi shart."),
        ("p", "11.3. QMCh grafik asosida «signal» usuli bo‘yicha olinganda konteynerlar yuzasidan shartnoma tuzish istisno qilinadi. Bunda "
              "tashkilotlarga QMChni yig‘ish va saqlash uchun jamoat joylariga qo‘yilgan konteynerlardan foydalanishiga ruxsat etiladi."),
        ("p", "11.4. Grafik asosida xizmat ko‘rsatilganda Ijrochi tomonidan ish to‘liq bajarilgan deb e’tirof etiladi."),
        ("p", f"11.5. Xizmatlar {c['object_address']} manzilida joylashgan" + (f", kadastr raqami: {c['cadastre']} bo‘lgan" if c["cadastre"] != "______" else "")
              + f" ko‘chmas mulk obyekti uchun ko‘rsatiladi. Ushbu obyekt Buyurtmachiga {c['ownership_text']}."),
        ("h", "12. SHARTNOMANING AMAL QILISH MUDDATI"),
        ("p", f"12.1. Ushbu shartnomaning amal qilish muddati “{c['vf_d']}” {c['vf_m']} {c['vf_y']} yildan “{c['vt_d']}”.{c['vt_m']}.{c['vt_y']} "
              f"yilgacha belgilanadi. (Izoh bunda byudjet tashkilotlari bilan tuzilgan shartnomalarning kuchga kirish sanasi tuman G‘aznachilik "
              f"bo‘linmasida majburiy ro‘yxatga olingan kundan boshlab hisoblanadi)."),
        ("p", "12.2. Shartnomani muddatidan oldin to‘xtatmoqchi bo‘lgan tomon ikkinchi tomonni bu haqida bir oy oldin yozma ravishda ogohlantiradi."),
        ("p", "12.3. Iste’molchi Shartnoma muddati tugagandan so‘ng, shartnomani bekor qilish yuzasidan yozma ravishda munosabat bildirmasa, "
              "shuningdek Ijrochi tomonidan ko‘rsatilgan xizmatlarni qabul qilishni davom ettirgan taqdirda shartnoma o‘z kuchini yo‘qotmagan hamda "
              "yana 1 (bir) yil muddatga uzaytirilgan deb hisoblanadi. Byudjetdan mablag‘ oluvchilar bilan tuzilgan shartnomalar bundan mustasno."),
        ("p", "12.4. Ushbu shartnoma bir xil yuridik kuchga ega bo‘lgan 2 nusxada (byudjet tashkilotlari uchun 3 nusxada) tuzilib, bir nusxasi "
              "Iste’molchida ikkinchi nusxasi Ijrochida (byudjet tashkilotlari uchun uchinchi nusxasi yuqori turuvchi tashkilot hisoblagan "
              "_____________________________ da) saqlanadi."),
        ("h", "13. Томонларни юридик манзиллари ва реквизитлари"),
        ("req", {
            "left_title": "Бажарувчи", "right_title": "Буюртмачи",
            "left": [("Номи", c["provider_name"]), ("Манзил", c["provider_address"]), ("Телефон", c["provider_phone"]), ("Факс", ""),
                     ("СТИР", c["provider_inn"]), ("IFUT (OKED)", c["provider_oked"]), ("Х/Р", c["provider_account"]),
                     ("Банк", c["provider_bank"]), ("МФО", c["provider_mfo"])],
            "right": [("Номи", c["customer_name"]), ("Манзил", c["customer_address"]), ("Телефон", c["customer_phone"]), ("Факс", ""),
                      ("СТИР", c["customer_stir"]), ("IFUT (OKED)", c["customer_oked"]), ("Х/Р", c["customer_account"]),
                      ("Банк", c["customer_bank"]), ("МФО", c["customer_mfo"])],
        }),
        ("sign",),
    ]


# --- Andijon (hujjat.uz / my.soliq) — «Ommaviy shartnoma» ---
def ommaviy(c: dict) -> list:
    return [
        ("title", f"OMMAVIY SHARTNOMA № {c['number']}"),
        ("pair", c["place"], f"{c['date']}-y."),
        ("p", f"O‘zbekiston Respublikasining “Chiqindilar to‘g‘risida”gi Qonuni, O‘zbekiston Respublikasi Prezidentining “Chiqindilarni boshqarish "
              f"tizimini takomillashtirish va ularning ekologik vaziyatga salbiy ta’sirini kamaytirish bo‘yicha chora-tadbirlar to‘g‘risida” 2024-yil "
              f"4-yanvardagi PF-5-son Farmoni hamda Vazirlar Mahkamasining 2019-yil 6-fevraldagi 95-son qarori bilan tasdiqlangan “Qattiq va suyuq "
              f"maishiy chiqindilarni to‘plash va olib chiqib ketish bo‘yicha xizmatlar ko‘rsatish qoidalari” talablaridan kelib chiqqan holda Ustav "
              f"asosida faoliyat yurituvchi {c['provider_name']} (kelgusida “Xizmat ko‘rsatuvchi” deb yuritiladi) direktori {c['provider_director']} "
              f"bir tomondan hamda {c['customer_name']} direktor {c['customer_director']} (kelgusida “Iste’molchi” deb yuritiladi) ikkinchi tomondan "
              f"(birgalikda “Tomonlar/Taraflar” deb yuritiladi) quyidagilar haqida shartnoma tuzdilar:"),
        ("h", "1. Atamalar va tariflar"),
        ("p", "1.1. Shartnomada quyidagi ta’riflarni o‘zida ifodalovchi asosiy atamalar qo‘llanadi:"),
        ("p", "Xizmat ko‘rsatuvchi – o‘ziga biriktirilgan hududda iste’molchilarga qattiq va suyuq maishiy chiqindilarni to‘plash va olib chiqib "
              "ketish bo‘yicha xizmatlar ko‘rsatuvchi, chiqindilar bilan bog‘liq ishlarni amalga oshirish sohasida xizmat ko‘rsatishga ixtisoslashgan "
              "tashkilot;"),
        ("p", "iste’molchi – xizmat ko‘rsatuvchi tashkilotga biriktirilgan hududda xizmat ko‘rsatuvchi tashkilot bilan maishiy chiqindilarni "
              "to‘plash va olib chiqib ketish bo‘yicha xizmatlar ko‘rsatishga shartnoma tuzgan alohida ko‘chmas mulkdan foydalanadigan yuridik shaxs "
              "yoki yakka tartibdagi tadbirkor."),
        ("p", "qattiq maishiy chiqindilar – jismoniy shaxslarning hayoti va faoliyati hamda yuridik shaxslarning faoliyati natijasida hosil bo‘luvchi "
              "organik va noorganik chiqindilar, shuningdek, ular hududida va obodonlashtirish obyektlaridagi tabiiy jarayonlar natijasida hosil "
              "bo‘luvchi chiqindilar (oziq-ovqat va o‘simlik chiqindilari, to‘qimachilik mahsulotlari, o‘rash-joylash (qadoqlash) materiallari, shisha, "
              "rezina, qog‘oz, plastmassa, yog‘och chiqindilari, o‘zining foydalanish xususiyatlarini yo‘qotgan uy-ro‘zg‘or buyumlari, supurindi, "
              "shuningdek, qattiq yoqilg‘ida ishlovchi maishiy pechkalar va isitish bug‘ qozonlaridan foydalanish natijasida hosil bo‘luvchi chiqindilar);"),
        ("p", "xizmat ko‘rsatish zonasi – mahalliy davlat hokimiyati organlari tomonidan maishiy chiqindilarni to‘plash va olib chiqib ketish "
              "xizmatlari ko‘rsatish uchun tegishli xizmat ko‘rsatuvchi tashkilotga belgilangan tartibda biriktirilgan tuman (shahar) hududi."),
        ("p", "Platforma operatori — platforma faoliyatini tashkil etuvchi yuridik shaxs (“Wisesoft It Group” MChJ);"),
        ("p", "Tomon yoki Taraf — mazmunga qarab Xizmat ko‘rsatuvchi yoki Iste’molchi;"),
        ("p", "Platforma ishtirokchisi — Xizmat ko‘rsatuvchi va iste’molchi;"),
        ("p", "Maxsus platforma — Sanitar korxonalar va iste’molchilar o‘rtasidagi ushbu shartnomada hamda “Xizmat ko‘rsatuvchi” va platforma "
              "operatori o‘rtasida tuziladigan shartnomalar bilan tartibga solinadigan munosabatlarni raqamlashtirishga qaratilgan maxsus platforma."),
        ("p", "1.2. Shartnomaning 1.1 bandida keltirilgan atamalar va ta’riflar mazkur shartnoma bo‘yicha tuziladigan qo‘shimcha shartnomalarda ham "
              "aynan shu mazmun va ta’rifda qo‘llanadi."),
        ("table", {
            "head": ["№", "MXIK kodi va nomi", "Mahsulot yoki xizmatga izoh", "O‘ram turi", "Miqdori", "Narxi", "Yetkazib berish bahosi",
                     "QQS stavkasi, %", "QQS summasi, so‘m", "Yetkazib berishning QQSni hisobga olgan holda qiymati"],
            "rows": [["1", f"{MXIK} - {MXIK_NAME}", "Xizmat uchun narx haqiqatda ko‘rsatilgan xizmat hajmidan kelib chiqib ta’rif asosida "
                      "hisob-kitob qilinadi", c["unit"], c["qty"], c["unit_net"], c["net"], "12%", c["vat"], c["total"]]],
            "foot": ["", "", "", "", "", "jami:", c["net"], "", c["vat"], c["total"]],
            "widths": [5, 24, 22, 9, 9, 11, 14, 8, 12, 16],
        }),
        ("p", f"Shartnomaning umumiy qiymati: {c['total_words']}"),
        ("h", "2. Shartnoma predmeti"),
        ("p", "2.1. Mazkur shartnoma bo‘yicha “Xizmat ko‘rsatuvchi” “Iste’molchi”ga qattiq maishiy chiqindilarni to‘plash va olib chiqib ketish "
              "(keyingi o‘rinlarda “Xizmatlar” deb yuritiladi) xizmatini ko‘rsatish, “Iste’molchi” esa ularni qabul qilish va xizmat haqqini to‘lash "
              "majburiyatini o‘z zimmasiga oladi."),
        ("p", "2.2. “Xizmatlar”ning aniq turlari, ularning narxi, mazkur shartnomaning 1.2 bandidagi jadvalda keltiriladi."),
        ("p", "2.3. Xizmat ko‘rsatuvchi tashkilot tomonidan quyidagi chiqindilarni olib chiqib ketish kelishilgan narxlarda alohida to‘lov evaziga "
              "amalga oshiriladi:\n- sanoat chiqindilari;\n- suyuq maishiy chiqindilar;\n- yirik hajmli maishiy chiqindilar;\n"
              "- qurilish chiqindilari va tuproq;\n- tibbiyot chiqindilari;\n- zaharli-kimyoviy chiqindilar."),
        ("h", "3. Iste’molchining huquq va majburiyatlari"),
        ("p", "3.1. Iste’molchi quyidagi huquqlarga ega:\n"
              "- Shartnomaga muvofiq zarur ko‘lamda, belgilangan sifatda, uning hayoti va salomatligi uchun xavfsiz bo‘lgan, mulkiga zarar "
              "yetkazmaydigan xizmatlardan foydalanish;\n"
              "- Xizmat ko‘rsatuvchi tashkilot tomonidan qattiq maishiy chiqindilarni olib chiqishning minimal davriyligiga rioya etilishini talab "
              "qilish yoki o‘zi xizmat ko‘rsatish muddatini belgilash bo‘yicha taklif berish;\n"
              "- o‘n ikki oydan ortiq bo‘lmagan davr uchun oldindan haq to‘lash, keyinchalik tegishli tariflar oshganda qaytadan hisob-kitob qilmaslik "
              "(qo‘shilgan qiymat solig‘i bundan mustasno);\n"
              "- Xizmat ko‘rsatuvchi tashkilot tomonidan qattiq maishiy chiqindilarni olib chiqib ketish jadvaliga rioya qilinmagan hollarda Xizmat "
              "ko‘rsatuvchi tashkilotning operativ tartibda qattiq maishiy chiqindilarni olib chiqib ketish choralarini ko‘rishi lozim bo‘lgan "
              "dispetcherlik xizmatiga buyurtmanoma berish;\n"
              "- Xizmat ko‘rsatuvchi tashkilot tomonidan shartnoma majburiyatlari sifatsiz bajarilgan hollarda Xizmat ko‘rsatuvchiga yozma, elektron "
              "yoki og‘zaki shaklda shikoyat qilish va Xizmat ko‘rsatuvchidan xizmatlar to‘liq ko‘rsatilmaganligi yoki tegishlicha bo‘lmagan sifatdagi "
              "xizmatlar ko‘rsatilganligi holatini tasdiqlovchi dalolatnomani tuzishni, shuningdek, aniqlangan kamchiliklarning belgilangan "
              "muddatlarda bartaraf etilishini talab qilish;\n"
              "- xizmatlar ko‘rsatilayotganda Xizmat ko‘rsatuvchi aybi bilan yuzaga kelgan kamchiliklarning bepul bartaraf etilishini talab qilish;\n"
              "- yuridik shaxs faoliyatini vaqtincha yoki butunlay to‘xtatganligi bo‘yicha Xizmat ko‘rsatuvchi tashkilotga yozma ravishda xabardor "
              "qilish hamda shartnomada belgilangan tartibda xizmatlar ko‘rsatilmagan davr uchun qattiq maishiy chiqindilarni to‘plash va olib chiqish "
              "bo‘yicha xizmatlarga haq to‘lash majburiyatlaridan to‘liq ozod bo‘lish;\n"
              "- shartnoma tuzilayotganda (yuridik shaxs va yakka tartibdagi tadbirkor), maishiy chiqindilarni o‘z vaqtida chiqarib yuborish "
              "zaruriyatidan kelib chiqqan holda, sanitariya qoidalari, normalari va gigiyena normativlarida belgilangan cheklangan muddatlardan "
              "oshmaydigan xizmat ko‘rsatish muddatlarini belgilash;\n"
              "- qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha sifatsiz xizmat ko‘rsatilganligi sababli, agar Xizmat ko‘rsatuvchi o‘z "
              "vaqtida shartnomani bajarishga kirishmasa yoki sifatsiz xizmat ko‘rsatsa, zararlar undirilishini talab qilib sudga murojaat qilish.\n"
              "- Iste’molchi qonun hujjatlariga muvofiq boshqa huquqlarga ham ega bo‘lishi mumkin."),
        ("p", "3.2. Iste’molchi quyidagilarga majbur:\n"
              "- qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha ko‘rsatilgan xizmatlar uchun to‘lovlarni ushbu shartnomada belgilangan "
              "muddatlarda o‘z vaqtida va to‘liq miqdorda to‘lash;\n"
              "- mazkur shartnomani to‘g‘ridan to‘g‘ri tuzishda qonunchilik hujjatlarida belgilangan huquq va vakolatlarga ega bo‘lish, agar bunday "
              "vakolat mavjud bo‘lganda ushbu shartnomani tuzish hamda davlat buyurtmachilari to‘g‘ridan-to‘g‘ri shartnomalar tuzilganligi to‘g‘risidagi "
              "axborotni ushbu shartnoma tuzilgan paytdan e’tiboran besh ish kuni ichida maxsus axborot portaliga joylashtirishi;\n"
              "- konteynersiz to‘plash tizimida – qattiq maishiy chiqindilarni olib chiqish jadvaliga muvofiq maxsus chiqindi tashuvchi texnikalarga "
              "ortib berish;\n"
              "- qattiq maishiy chiqindilarni to‘plash va olib chiqib ketish xizmatlari uchun majburiy to‘lovlarni Ekologiya, atrof-muhitni muhofaza "
              "qilish va iqlim o‘zgarishi vazirligi huzuridagi Chiqindilarni boshqarish va sirkulyar iqtisodiyotni rivojlantirish Agentligining maxsus "
              "tranzit bank hisobvaraqlariga to‘lash;\n"
              "- konteynerda to‘plash tizimida – chiqindilarni o‘ziga tegishli bo‘lgan binolarga yaqin yoki tutash hududlarda o‘rnatgan konteynerlarga "
              "yoki maxsus chiqindi yig‘ish idishlarga tashlash;\n"
              "- qattiq maishiy chiqindilarni ruxsat etilmagan joylarga va obyektlarga tashlamaslik hamda joylashtirmaslik (ko‘chalarga, suv "
              "yo‘llariga, ariq va qattiq hamda suyuq maishiy chiqindilarni to‘plash va ko‘mish uchun belgilanmagan boshqa joylarga, shu jumladan, "
              "avtotransport vositalaridan ularning to‘xtashi, to‘xtab turishi yoki harakatlanishi vaqtida);\n"
              "- qattiq maishiy chiqindilarni ularni joylashtirish obyektlarida (idishlar, yer o‘ralari va hokazolar), tashkilot hududida, dalalarda va "
              "aholi yashash punktlarida yoqmaslik;\n"
              "- qattiq maishiy chiqindilarni maxsus avtotransport vositasiga ortish uchun Xizmat ko‘rsatuvchining ortish joyiga bemalol o‘tishini "
              "ta’minlash;\n"
              "- chiqindi to‘plash konteynerlari, chiqindi to‘plash shoxobchalari, chiqindi to‘plash kameralari va boshqa uskunalarning nosozliklari "
              "aniqlanganda Xizmat ko‘rsatuvchini darhol xabardor qilish;\n"
              "- yirik gabaritli maishiy chiqindilar va qurilish chiqindilarini xususiy uy-joy mulkdorlari shirkatlari, fuqarolarning o‘zini o‘zi "
              "boshqarish organlari, boshqaruvchi tashkilotlar tomonidan belgilangan, vaqtinchalik maxsus ajratilgan joylarga joylashtirish va ularning "
              "chiqindi to‘plash shoxobchalaridagi konteynerlarga tashlanishiga yo‘l qo‘ymaslik;\n"
              "- yuridik shaxslar chiqindilarni to‘plashni ta’minlashi, o‘ziga tegishli bo‘lgan binolarga yaqin yoki tutash hududlarda qattiq maishiy "
              "chiqindilarni to‘plash va vaqtinchalik saqlash uchun konteynerlar (qutilar)ni o‘rnatish;\n"
              "- Iste’molchi qonun hujjatlariga muvofiq boshqa majburiyatlarga ham ega bo‘lishi mumkin."),
        ("h", "4. Xizmat ko‘rsatuvchining huquq va majburiyatlari"),
        ("p", "4.1. Xizmat ko‘rsatuvchi tashkilot quyidagi huquqlarga ega:\n"
              "- qattiq maishiy chiqindilarni olib chiqib ketish bo‘yicha Iste’molchilarga ko‘rsatilgan xizmatlar uchun to‘lovlarni qonun hujjatlarida "
              "belgilangan tartibda, o‘z vaqtida va to‘liq hajmda olish;\n"
              "- sanoat chiqindilari, suyuq maishiy chiqindilar, yirik hajmli maishiy chiqindilar, qurilish chiqindilari va tuproq, tibbiyot "
              "chiqindilari va zaharli-kimyoviy chiqindilarni alohida to‘lov evaziga olib chiqish bo‘yicha qo‘shimcha xizmatlar ko‘rsatish;\n"
              "- Hisobga olishning yagona elektron tizimida iste’molchilarning ma’lumotlar bazasini muntazam ravishda yangilab borish hamda ularga "
              "qarzdorlik to‘g‘risida ogohlantirish xati yuborish;\n"
              "- maishiy chiqindilarni to‘plash va olib chiqib ketish bo‘yicha ko‘rsatilgan xizmatlar uchun to‘lovlarni undirish bo‘yicha sudga "
              "da’volar taqdim qilish, shuningdek, qonunchilikda belgilangan tartibda penya undirish;\n"
              "- yong‘in kelib chiqishiga sabab bo‘luvchi, cho‘g‘, cho‘g‘lanib turgan kul yoki o‘chmagan boshqa qattiq yoqilg‘i chiqindilarini maxsus "
              "avtotransport vositasiga ortmaslik.\n"
              "- Xizmat ko‘rsatuvchi qonun hujjatlariga muvofiq boshqa huquqlarga ham ega bo‘lishi mumkin."),
        ("p", "4.2. Xizmat ko‘rsatuvchi tashkilot quyidagilarga majbur:\n"
              "- o‘ziga biriktirilgan hududda qattiq maishiy chiqindilarning muntazam olib chiqib ketilishini amalga oshirish;\n"
              "- qattiq maishiy chiqindilarni olib chiqishning minimal davriyligiga rioya etish;\n"
              "- Iste’molchilarga qattiq maishiy chiqindilarni olib chiqish bo‘yicha qonun hujjatlari va ushbu shartnoma talablariga muvofiq zarur "
              "sifatdagi xizmatlar ko‘rsatish;\n"
              "- Xizmat ko‘rsatuvchi tashkilot tomonidan qattiq maishiy chiqindilarni olib chiqib ketish jadvaliga rioya qilinmagan hollarda Xizmat "
              "ko‘rsatuvchi tashkilotning dispetcherlik xizmatiga tushgan Iste’molchilarning buyurtmanomalarini operativ tartibda (buyurtmanoma kelib "
              "tushgan kundan boshlab bir ish kunidan kechikmay) bajarish;\n"
              "- Iste’molchilarning ma’lumotlar bazasini yuritish va muntazam ravishda yangilab borish (ko‘rsatilgan qo‘shimcha xizmatlar bo‘yicha);\n"
              "- qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar ko‘rsatishning rejimi va sifati bo‘yicha Iste’molchilarning "
              "murojaatlari, shuningdek, ularning ijrosi hisobini olib borish;\n"
              "- chiqindi to‘plash shoxobchalari va konteynerlarning holatini nazorat qilib borish hamda ularning tegishli holatda saqlanishini "
              "ta’minlash;\n"
              "- chiqindi to‘plash shoxobchalarining qattiq maishiy chiqindilarni to‘plash uchun zarur miqdordagi konteynerlar bilan jihozlanishini "
              "ta’minlash;\n"
              "- maishiy chiqindilarni mustaqil ravishda saralashni amalga oshirishni ta’minlash;\n"
              "- chiqindi to‘plash shoxobchalarini joriy va mukammal ta’mirlashni amalga oshirish;\n"
              "- fuqarolarning hayoti va salomatligi, atrof muhit uchun xavfli bo‘lgan bakteriyalarning va boshqa zararli moddalarning rivojlanishiga, "
              "chiqindilarning ko‘plab to‘planib qolishiga qarshi rejali ishlarni olib borish (konteyner va chiqindi to‘plash shoxobchalarini "
              "dezinfeksiyalash yoki yuvib turish yo‘li bilan va shu kabilar);\n"
              "- qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar ko‘rsatishning tartibi va tariflarining o‘zgarganligi "
              "to‘g‘risida ushbu tariflar kuchga kirishidan o‘n besh kun avval Xizmat ko‘rsatuvchi ommaviy axborot vositalari, ijtimoiy tarmoqlar "
              "orqali Iste’molchini xabardor qilish;\n"
              "- Iste’molchilarga ularning so‘roviga asosan qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar ko‘rsatishning "
              "amaldagi tartibi, talablari, qoidalari va xizmatlar ko‘rsatish tartibining, shuningdek, tariflarining o‘zgarganligi to‘g‘risida bepul "
              "ma’lum qilish;\n"
              "- qattiq maishiy chiqindilar bilan bog‘liq ishlarni amalga oshirishda buzilgan yer uchastkalarini qayta tiklash ishlarini amalga "
              "oshirish;\n"
              "- Xizmat ko‘rsatuvchi tashkilotning stendida, e’lonlar taxtasida ko‘rsatilayotgan xizmatlar, ularning amaldagi tariflari, to‘lov "
              "shartlari, shuningdek, qattiq maishiy chiqindilarni olib chiqish jadvalini va mazkur shartnomani joylashtirish;\n"
              "- Iste’molchiga ko‘rsatilayotgan xizmatlar sifati bo‘yicha aniqlangan kamchiliklarni bartaraf etish va yangi kamchiliklarning oldini "
              "olish choralarini ko‘rish;\n"
              "- maishiy chiqindilarni to‘plash va olib chiqib ketish bo‘yicha xizmatlar ko‘rsatish bilan bog‘liq ma’lumotlar va buxgalteriya "
              "hujjatlari besh yil mobaynida but holatda saqlanishini ta’minlash.\n"
              "- Xizmat ko‘rsatuvchi qonun hujjatlariga muvofiq boshqa majburiyatlarga ham ega bo‘lishi mumkin."),
        ("h", "5. Hisob-kitob qilish tartibi va shartlari"),
        ("p", "5.1. Qoraqalpog‘iston Respublikasi Jo‘qorg‘i Kengesi, viloyatlar va Toshkent shahar xalq deputatlari Kengashlari yuridik shaxslar va "
              "yakka tartibdagi tadbirkorlar uchun ularning faoliyat turlari va xususiyatlaridan kelib chiqib, chiqindi to‘plash me’yorlarini va "
              "tariflarini tasdiqlaydi hamda ommaviy shartnomadagi to‘lov summalari ushbu me’yorlarga asoslangan holda belgilanadi."),
        ("p", "5.2. Bunda, maishiy chiqindilarni olib chiqib ketish bo‘yicha xizmat narxlari yuqoridagi bandda ko‘rsatib o‘tilgan me’yorlar va "
              "tariflarga asoslanib, Iste’molchi hamda Xizmat ko‘rsatuvchi o‘rtasida tuzilgan mazkur ommaviy shartnomaning 1.2 bandida keltirilgan "
              "jadvalga muvofiq belgilanadi. Tarif o‘zgargan taqdirda qonunchilikda belgilangan tartibda yangi tarif bo‘yicha hisob-kitob qilinadi va "
              "buning uchun qo‘shimcha kelishuv tuzish talab etilmaydi.\n"
              "Shartnomaning 1.2 bandida keltirilgan jadvalda belgilangan chiqindilarni olib chiqib ketish hajmi amalda ortgan taqdirda, ortiqcha "
              "ko‘rsatilgan xizmatlar uchun hisob-kitoblar Xizmat ko‘rsatuvchi tomonidan taqdim etilgan elektron hisobvaraq-faktura (EHF) asosida "
              "amalga oshiriladi. Iste’molchi tomonidan EHFni qabul qilishi yoki asoslagan holda rad etishi shart bo‘ladi. Iste’molchi EHFni rad "
              "etmagan yoki uni javobsiz qoldirilgan taqdirda, ortiqcha ko‘rsatilgan xizmatlarga rozilik berilgan deb hisoblanadi.\n"
              "Bunda, Iste’molchi tomonidan EHFning qabul qilinishi (imzolanishi), tan olinishi xizmatlar hajmi oshganligiga va to‘lov majburiyatining "
              "yuzaga kelishiga Tomonlarning o‘zaro roziligi hisoblanadi hamda mazkur holat bo‘yicha alohida qo‘shimcha kelishuv tuzish talab "
              "etilmaydi.\n"
              "Ortiqcha ko‘rsatilgan xizmatlar natijasida shartnomaning yillik umumiy bahosi o‘zgarishiga taraflar o‘z roziligini bildiradi.\n"
              "Iste’molchi avans tariqasida to‘langan to‘lovlar uchun, ushbu davrda tegishli tariflar oshgan taqdirda, to‘lov amalga oshirilgan sanadan "
              "o‘n ikki oydan oshmaydigan davrga qayta hisob-kitob qilishdan ozod etiladi."),
        ("p", "5.3. Bunda Maishiy chiqindilarni olib chiqib ketish bo‘yicha xizmatlar quyidagi usullar orqali amalga oshiriladi:"),
        ("p", "5.4. Chiqindi yig‘ish shoxobchasiga tashlash: Iste’molchi chiqindilarni belgilangan chiqindi yig‘ish shoxobchasiga olib boradi. Ushbu "
              "usulda xizmat haqi ushbu shartnomada belgilangan summa asosida hisoblanadi va tegishli faktura faqat shu summaga tuziladi."),
        ("p", "5.5. Konteynersiz yig‘ish usuli orqali obyektning o‘zidan olib ketish: Iste’molchi chiqindilarni o‘z obyektida saqlaydi va xizmat "
              "ko‘rsatuvchi tashkilot maxsus signal orqali chiqindilarni olib ketadi. Bu usulda ham xizmat haqi belgilangan me’yorlar va tariflar "
              "asosida hisoblanadi va faktura faqat shu summaga tuziladi."),
        ("p", "5.6. Konteyner usuli: Iste’molchi chiqindilarni xizmat ko‘rsatuvchi tashkilot tomonidan taqdim etilgan yoki iste’molchi tomonidan "
              "o‘rnatilgan konteynerlarda to‘playdi. Ushbu usulda xizmat haqi belgilangan me’yorlar va tariflar asosida aniqlanadi va faktura faktik "
              "xizmat ko‘rsatish hajmiga muvofiq shakllantiriladi."),
        ("p", "5.7. Quyidagi holatlarda shartnoma tuzilishi majburiy hisoblanmaydi:\n"
              "iste’molchi faoliyat olib boradigan hududda sanitar tozalash korxonalari faoliyati yo‘lga qo‘yilmaganda;\n"
              "iste’molchi faoliyat olib boradigan hududda o‘rnatilgan me’yorlarga muvofiq maishiy chiqindilarni yig‘ish maydonchalari (konteyner yoki "
              "maxsus chiqindilarni saqlash joylari) joylashtirilmagan taqdirda, bunda maishiy chiqindilarni yig‘ish maydonchalarini (konteyner yoki "
              "maxsus chiqindilarni saqlash joylari) joylashtirish me’yor va tartiblari Vazirlar Mahkamasi tomonidan belgilanadi;\n"
              "yuridik shaxs yoki yakka tartibdagi tadbirkorda qattiq maishiy chiqindilarni olib chiqish uchun mo‘ljallangan maxsus avtotransport "
              "vositasi mavjud bo‘lganda hamda u bilan chiqindi poligoni o‘rtasida qattiq maishiy chiqindilarni joylashtirish va utilizatsiya qilish "
              "bo‘yicha shartnomalar tuzilganda."),
        ("p", "5.8. Qattiq maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar uchun to‘lovlar majburiy hisoblanadi."),
        ("p", "5.9. Qattiq maishiy chiqindilarni to‘plash va olib chiqib ketish xizmatlari uchun majburiy to‘lovlar to‘lov hisoblangan davrdan "
              "keyingi oyning o‘ninchi sanasiga qadar Chiqindilarni boshqarish va sirkulyar iqtisodiyotni rivojlantirish agentligining maxsus tranzit "
              "bank hisobvarag‘iga to‘lanadi va uning maxsus bank hisobvarag‘ida jamlanadi.\n"
              "Sanoat chiqindilari, suyuq maishiy chiqindilar, yirik hajmli maishiy chiqindilar, qurilish chiqindilari va tuproq, tibbiyot chiqindilari "
              "hamda zaharli-kimyoviy chiqindilarni olib chiqish bo‘yicha alohida xizmatlar uchun to‘lovlar bevosita Xizmat ko‘rsatuvchining bank hisob "
              "raqamiga 100 foiz oldindan to‘lov asosida amalga oshiriladi."),
        ("p", "5.10. Iste’molchi avans tariqasida to‘langan to‘lovlar uchun, ushbu davrda tegishli tariflar oshgan taqdirda, to‘lov amalga oshirilgan "
              "sanadan o‘n ikki oydan oshmaydigan davrga qayta hisob-kitob qilishdan ozod etiladi."),
        ("p", "5.11. Maishiy chiqindilarni olib chiqib ketish bo‘yicha xizmatlar uchun to‘lovlarning qayta hisob-kitobi qonun hujjatlarida "
              "belgilangan tartibda amalga oshiriladi.\n"
              "Maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha tegishli bo‘lmagan sifatdagi xizmatlar ko‘rsatilganda yoki xizmat ko‘rsatilmagan "
              "taqdirda Iste’molchi tegishli davr uchun to‘lovlardan ozod etiladi."),
        ("p", "5.12. Maishiy chiqindilarni to‘plash va olib chiqish bo‘yicha xizmatlar ko‘rsatilmagan yoki tegishli bo‘lmagan sifatdagi xizmatlar "
              "ko‘rsatilganligi holati aniqlangan hollarda manfaatdor shaxslar tomonidan Iste’molchi, Xizmat ko‘rsatuvchi tashkilotning vakili "
              "tomonidan imzolanadigan yoki “mahalla yettiligi” tomonidan imzolanadigan xizmatlar ko‘rsatilmaganligi yoki tegishlicha bo‘lmagan "
              "sifatdagi xizmatlar ko‘rsatilganligi holatini tasdiqlovchi dalolatnoma tuziladi hamda to‘plangan hujjatlar Agentlikning tegishli "
              "hududiy bo‘linmasiga yuboriladi."),
        ("p", "5.13. Xizmatlar ko‘rsatilmaganligi yoki tegishlicha bo‘lmagan sifatdagi xizmatlar ko‘rsatilganligi to‘g‘risida tuzilgan dalolatnoma "
              "xizmatlar uchun to‘lovlar miqdorini qayta hisob-kitob qilish uchun asos hisoblanadi."),
        ("p", "5.14. Xizmat ko‘rsatuvchi tomonidan ko‘rsatilayotgan xizmatlar bilan bog‘liq ravishda Iste’molchiga yoki uning mol-mulkiga zarar "
              "yetkazilgan taqdirda, Iste’molchi tomonidan qonunchilikda belgilangan tartibda yetkazilgan zarar holati qayd etilgan dalolatnoma "
              "tuziladi. Dalolatnoma Iste’molchining imzosi, Xizmat ko‘rsatuvchi tashkilot vakillarining imzolari bo‘lgandagina haqiqiy hisoblanadi."),
        ("p", "5.15. Xizmat ko‘rsatuvchi tashkilotning vakili dalolatnomani imzolashdan bosh tortgan taqdirda u ushbu dalolatnomaga imzo qo‘yishdan "
              "bosh tortganlik sabablarini yozma ravishda asoslashi shart. Aks holda Iste’molchi maishiy chiqindilarni to‘plash va olib chiqish "
              "bo‘yicha xizmatlar uchun to‘lovlarni sud qarori qabul qilinguniga qadar to‘xtatishga haqlidir."),
        ("p", "5.16. Mulk egalari tomonidan Xizmat ko‘rsatuvchi tashkilot vakillariga yuridik shaxs yoki yakka tartibdagi tadbirkor faoliyatini "
              "vaqtincha yoki butunlay to‘xtatganligini tasdiqlovchi hujjatlar taqdim etilgan taqdirda, qattiq maishiy chiqindilarni to‘plash va olib "
              "chiqish bo‘yicha xizmatlar uchun to‘lov undirilmaydi."),
        ("h", "6. Tomonlarning javobgarligi"),
        ("p", "6.1. Majburiyatlarni buzganlik uchun tomonlar O‘zbekiston Respublikasining amaldagi qonunchiligiga va ushbu shartnomaga muvofiq "
              "javobgar bo‘ladilar."),
        ("p", "6.2. Xizmat ko‘rsatish muddatlarini buzganligi uchun Iste’molchi Xizmat ko‘rsatuvchidan har bir kun uchun kechiktirib ko‘rsatilgan "
              "xizmat narxining 0,4 % (foizi) miqdorida penya to‘lashni talab qilishga haqlidir, lekin talab qilingan penya miqdori, ushbu shartnoma "
              "bahosining 50 % (foizi)dan ortiq bo‘lishi mumkin emas."),
        ("p", "6.3. Xizmat uchun to‘lov shartlarini buzganligi uchun Xizmat ko‘rsatuvchi Iste’molchidan kechiktirilgan har bir kun uchun "
              "kechiktirilgan to‘lov summasining 0,4 % (foizi) miqdorida penya to‘lashni talab qilishga haqli, lekin talab qilingan penya miqdori, ushbu "
              "shartnoma bahosining 50 % (foizi)dan ortiq bo‘lishi mumkin emas."),
        ("p", "6.4. Fors-major holatlari tufayli Shartnoma bo‘yicha majburiyatlarni bajarishning imkonsizligi yuzaga kelgan tomon 5 (besh) ish kuni "
              "ichida boshqa tomonga bunday holatlar yuzaga kelishi va tugashi to‘g‘risida yozma ravishda xabar berishi kerak."),
        ("p", "6.5. Shartnoma va unga qo‘shimcha bitim (kelishuv)larning shartlari va Shartnomaga muvofiq Tomonlar tarafidan olingan boshqa "
              "ma’lumotlar maxfiydir va oshkor etilishi mumkin emas."),
        ("p", "6.6. Shartnomaning amal qilishi Iste’molchining tashabbusi bilan bekor qilingan taqdirda, bajarilgan ishlar uchun to‘lov Iste’molchi "
              "tomonidan Xizmat ko‘rsatuvchining haqiqiy xarajatlari bo‘yicha shartnoma bekor qilingan kundan boshlab 5 (besh) ish kuni ichida amalga "
              "oshiriladi."),
        ("p", "6.7. Mazkur shartnomani to‘g‘ridan-to‘g‘ri tuzishda qonunchilik hujjatlarida belgilangan huquq va vakolatlarga ega bo‘lish, agar "
              "bunday vakolat mavjud bo‘lsa, ushbu shartnomani tuzish hamda davlat buyurtmachilari to‘g‘ridan-to‘g‘ri shartnomalar tuzilganligi "
              "to‘g‘risidagi axborotni ushbu shartnoma tuzilgan paytdan e’tiboran 5 (besh) ish kuni ichida maxsus axborot portaliga joylashtirishi "
              "shart. Ushbu talabni buzgan iste’molchilar tegishli vakolatli organlar oldida mustaqil ravishda javobgar bo‘ladilar."),
        ("p", "6.8. Shartnomada ko‘zda tutilmagan boshqa barcha javobgarlik choralari O‘zbekiston Respublikasining amaldagi qonunchilik hujjatlariga "
              "muvofiq belgilanadi."),
        ("h", "7. Taraflarning korrupsiyaga qarshi qo‘shimcha shartlari"),
        ("p", "7.1. Taraflar/Tomonlar shartnoma tuzishda, shartnomaning amal qilish muddatida va ushbu muddat tugaganidan so‘ng, shartnoma bilan "
              "bog‘liq korrupsiyaviy harakatlarni sodir qilmaslikka kelishib oldilar."),
        ("p", "7.2. Taraflar shartnomadagi korrupsiyaga qarshi qo‘shimcha shartlarda belgilangan korrupsiyaning oldini olish choralarini tan oladi "
              "va ularga rioya etilishi bo‘yicha hamkorlikni ta’minlaydilar."),
        ("p", "7.3. Har bir taraf shartnoma tuzilgan paytda bevosita o‘zi yoki uning ijroiya organlari, mansabdor shaxslari va xodimlari tomonidan "
              "shartnoma bilan bog‘liq munosabatlar yuzasidan qonunga xilof ravishda pul, moddiy qiymatliklar berilmaganligini, shartnoma tuzilishi "
              "evaziga norasmiy pul yoki boshqa moddiy qiymatliklar olinishiga yo‘l qo‘yilmaganligini, taklif etilmaganligini, ularni berishga va’da "
              "qilinmaganligini, shuningdek moddiy yoki har qanday turdagi imtiyoz, ustunliklar olinmaganligini (kelajakda bu turdagi harakatlarni "
              "amalga oshirishi mumkinligi haqida taassurot qoldirilmaganligini) kafolatlaydi.\n"
              "Taraflar, ular tomonidan shartnoma doirasida jalb qilingan shaxslarning (yordamchi pudratchi tashkilotlar, agentlar va taraflar nazorati "
              "ostidagi boshqa shaxslarning) yuqoridagi harakatlarni sodir etmasligi yuzasidan oqilona choralar ko‘radi."),
        ("p", "7.4. Taraflar davlat xizmatchilari, siyosiy partiyalar, shuningdek o‘zining ijroiya organlari, mansabdor shaxslari va xodimlari "
              "tomonidan har qanday vaqt va shaklda quyidagi harakatlarni bevosita yoki bilvosita (shu jumladan, uchinchi shaxslar orqali) sodir "
              "etilishiga yo‘l qo‘ymaydi:\n"
              "a) nazorat qiluvchi organlardan litsenziya va ruxsatnomalar olish, soliq solish, bojxona rasmiylashtiruvini amalga oshirish, sudda ish "
              "ko‘rilishi, qonunchilik jarayoni va boshqa sohalarda qonunga xilof ravishda tijorat yoki boshqa tusdagi ustunlikka ega bo‘lish yoki "
              "saqlab qolish maqsadida yuqoridagi shaxslar foydasiga yoki ular tomonidan moddiy yoki nomoddiy naf olishning taklif etilishi, va’da "
              "qilinishi, berilishiga;\n"
              "b) qonunga xilof ravishda olingan daromadlarning legallashtirilishiga, shuningdek, agar mulk jinoiy faoliyatdan olingan daromad ekanligi "
              "taraflarga ma’lum bo‘lsa, uni o‘tkazish, mulkka aylantirish yoxud almashtirish yo‘li bilan uning kelib chiqishiga qonuniy tus berish, "
              "bunday pul mablag‘lari yoki boshqa mol-mulkning asl xususiyatini, manbaini, turgan joyini, tasarruf etish, ko‘chirish usulini, pul "
              "mablag‘lariga yoki boshqa mol-mulkka bo‘lgan haqiqiy egalik huquqlarini yoki uning kimga qarashliligini yashirishga;\n"
              "c) korrupsiyaga oid huquqbuzarlik sodir qilish uchun ta’magirlik qilish, undash, tazyiq o‘tkazish yoki tahdid qilish. Ushbu holat "
              "bo‘yicha bir taraf ikkinchi tarafni hamda vakolatli davlat organlarini darhol xabardor qilishi shart."),
        ("p", "7.5. Taraflar tovarlar, xizmat va ishlarni realizatsiya qilish va o‘tkazishda, bitimlar tuzish bo‘yicha muzokaralar olib borishda, "
              "litsenziya, ruxsatnomalar va boshqa ruxsat etish xususiyatiga ega bo‘lgan hujjatlarni olishda yoki ularning manfaatlarini ko‘zlab "
              "boshqa harakatlarni amalga oshiruvchi taraflarning nazorati ostida bo‘lgan va ular nomidan harakat qiladigan shaxslarga (shu jumladan, "
              "yordamchi pudratchilar, agentlar, savdo vakillari, distribyuterlar, huquqshunoslar, hisobchilar, ular nomidan harakat qiluvchi boshqa "
              "vakillarga) nisbatan quyidagi harakatlarni amalga oshirishi shart:"),
        ("p", "7.6. korrupsiyaviy harakatlarga yo‘l qo‘yib bo‘lmasligi va korrupsiyaviy harakatlarga nisbatan murosasiz munosabatda bo‘lishi "
              "shartligi haqida ko‘rsatmalar va tushuntirishlar berish;"),
        ("p", "7.7. ulardan korrupsiyaviy harakatlarni amalga oshirish uchun vositachi sifatida foydalanmaslik;"),
        ("p", "7.8. ularni faqat tarafning oddiy kundalik faoliyati jarayonidagi ishlab chiqarish zarurati doirasidan kelib chiqib ishga jalb qilish;"),
        ("p", "7.9. ularga qonunchilik doirasida amalga oshirgan xizmatlari uchun belgilangan haq miqdoridan asossiz ravishda ortiqcha to‘lovlarni "
              "amalga oshirmaslik."),
        ("p", "7.10. Taraflar ularning nazorati ostida bo‘lgan va ular nomidan harakat qiladigan shaxslar tomonidan korrupsiyaga qarshi qo‘shimcha "
              "shartlarda belgilangan majburiyatlar buzilganligi holatlari haqida xabar berilganligi uchun ularga tazyiq o‘tkazilmasligini "
              "kafolatlaydilar."),
        ("p", "7.11. Agar bir tarafga boshqa tarafning korrupsiyaga qarshi qo‘shimcha shartlarning 7.4 va 7.5-bandlarida belgilangan "
              "majburiyatlarni buzilishiga yo‘l qo‘yganligi ma’lum bo‘lib qolsa, ikkinchi tarafni bu haqda zudlik bilan xabardor qilishi va ushbu "
              "tarafdan oqilona muddat ichida tegishli choralar ko‘rilishini va amalga oshirilgan ishlar yuzasidan unga xabardor qilishini talab "
              "qilishi shart. Tarafning talabi bo‘yicha ikkinchi taraf tomonidan qoidabuzarliklarni bartaraf qilish bo‘yicha oqilona muddat ichida "
              "tegishli choralar ko‘rilmagan yoki ko‘rib chiqish natijalari haqida xabardor qilmagan taqdirda, ushbu taraf shartnomani bir taraflama "
              "to‘xtatib turishga, bekor qilishga hamda zararni to‘liq qoplab berishni talab qilishga haqli."),
        ("h", "8. Shartnomaning amal qilish muddati"),
        ("p", "8.1. Ommaviy shartnoma my.soliq.uz soliq to‘lovchilarning shaxsiy kabinetiga hamda maxsus platformadagi iste’molchining shaxsiy "
              "kabinetiga yuboriladi va Iste’molchi uni 15 (o‘n besh) kun ichida elektron raqamli imzosi yordamida imzolaydi va u o‘sha kuni yuridik "
              "kuchga kiradi yoki asoslantirilgan tartibda imzolashni rad etadi aks holda shartnoma u shaxsiy kabinetga yuborilgan kundan 15 (o‘n "
              "beshinchi) kuni belgilangan tartibda imzolangan hisoblanib, yuridik kuchga kiradi."),
        ("p", "8.2. Shartnoma Iste’molchi tomonidan imzolangan yoki aksept hisoblanishi belgilangan harakatlarni amalga oshirgan paytdan boshlab "
              "tuzilgan hisoblanadi."),
        ("p", "8.3. Iste’molchi tomonidan ushbu shartnomada ko‘rsatilgan shartlarni bajarish yuzasidan qilingan harakatlar (chiqindi to‘plash "
              "shoxobchalarida chiqindilarni joylashtirishda, chiqindilarni konteynerlarga tashlash yoki Xizmat ko‘rsatuvchining maxsus avtotransport "
              "vositasiga joylashtirish, ko‘rsatilgan xizmatlar uchun tegishli summani to‘lash va shu kabilar)."),
        ("p", f"8.4. Shartnoma {c['valid_from']} dan {c['valid_to']} gacha amal qiladi."),
        ("h", "9. Nizolarni hal qilish"),
        ("p", "9.1. Shartnomadan kelib chiqadigan nizolarni sudgacha hal qilish bo‘yicha talabnoma yuborish tartibi Tomonlar uchun majburiydir."),
        ("p", "9.2. Talabnomalar tomonlar tarafidan qog‘oz shaklida yoki buyurtma pochta jo‘natmasi bilan Tomonlar joylashgan joyi bo‘yicha taqdim "
              "etilgani to‘g‘risida xabardor qilish orqali yuboriladi."),
        ("p", "9.3. Talabnomani ko‘rib chiqish muddati, u olingan kundan boshlab 15 (o‘n besh) kalendar kuni hisoblanadi."),
        ("p", "9.4. Tomonlar zudlik bilan to‘lanishi lozim bo‘lgan hal etilmagan barcha da’volar bo‘yicha bir-birlarini yozma ravishda darhol "
              "xabardor qilishlari shart."),
        ("p", "9.5. Tomonlarning Shartnoma bo‘yicha o‘z majburiyatlarini bajarmasligi munosabati bilan yuzaga keladigan hal qilinmagan nizolar "
              "O‘zbekiston Respublikasi qonunchiligiga muvofiq sud tartibida hal qilinadi."),
        ("h", "10. Boshqa shartlar"),
        ("p", "10.1. Ushbu Shartnomaga kiritilgan har qanday o‘zgartirish va qo‘shimchalar, agar ular yozma ravishda rasmiylashtirilib, har ikki "
              "tomondan imzolangan bo‘lsa, qonuniy kuchga ega va Shartnomaning ajralmas qismi bo‘lib hisoblanadi."),
        ("p", "10.2. Mazkur Shartnomaning biron bir bandi ijrosi ta’minlanmasa yoki amal qilishi bekor bo‘lsa, bu o‘z navbatida Shartnomaning "
              "boshqa bandlari ijrosi ta’minlanmasligiga yoki amal qilishini bekor bo‘lishiga ta’sir ko‘rsatmasa, Tomonlar o‘zaro kelishuv asosida "
              "ushbu bandlarni yanada qulay shakllarga o‘zgartirish bo‘yicha qo‘shimcha kelishuvlar imzolashi mumkin."),
        ("p", f"10.3. Xizmatlar {c['object_address']} manzilida joylashgan" + (f", kadastr raqami: {c['cadastre']} bo‘lgan" if c["cadastre"] != "______" else "")
              + f" ko‘chmas mulk obyekti uchun amalga oshiriladi. Ushbu obyekt Buyurtmachiga {c['ownership_text']}."),
        ("p", "10.4. Tomonlardan birining yuridik manzili, rekvizitlari o‘zgarganda tomonlar 3 (uch) kalendar kuni ichida tegishli o‘zgarishlar "
              "to‘g‘risida bir-birlarini yozma ravishda xabardor qilish majburiyatini oladilar."),
        ("p", "10.5. Ushbu Shartnoma bo‘yicha ma’lumotlar almashinuvida tomonlarning rasmiy elektron pochtalaridan foydalaniladi."),
        ("p", "10.6. Mazkur Shartnomada tartibga solinmagan barcha masalalar, O‘zbekiston Respublikasining amaldagi qonunchilik hujjatlari bilan "
              "tartibga solinadi."),
        ("h", "TOMONLARNING REKVIZITLARI"),
        ("req", {
            "left_title": "Yetkazib beruvchi (Xizmat ko‘rsatuvchi)", "right_title": "Sotib oluvchi (Buyurtmachi)",
            "left": [("Nomi", c["provider_name"]), ("Manzil", c["provider_address"]), ("Telefon", c["provider_phone"]),
                     ("H/r", c["provider_account"]), ("MFO", c["provider_mfo"]), ("STIR", c["provider_inn"]), ("OKED", c["provider_oked"])],
            "right": [("Nomi", c["customer_name"]), ("Manzil", c["customer_address"]), ("Telefon", c["customer_phone"]),
                      ("H/r", c["customer_account"]), ("MFO", c["customer_mfo"]), ("STIR", c["customer_stir"]), ("OKED", c["customer_oked"])],
        }),
        ("sign",),
    ]


# Viloyat (provider kodi) → shablon. Ro'yxatda bo'lmagan viloyat — standart (didox) shablon.
BY_PROVIDER = {"BTE": ("ommaviy", ommaviy), "BTK": ("didox", didox)}
DEFAULT = ("didox", didox)


def pick(provider_code: str | None):
    return BY_PROVIDER.get(provider_code or "", DEFAULT)
