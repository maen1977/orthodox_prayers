package com.orthodoxprayers.privateapp.bible;

import java.util.HashMap;
import java.util.Map;

public final class BibleBookNames {
    private static final Map<String, String[]> NAMES = new HashMap<>();
    static {
        add("GEN","التكوين","Genesis","Γένεσις"); add("EXO","الخروج","Exodus","Ἔξοδος"); add("LEV","اللاويين","Leviticus","Λευιτικόν");
        add("NUM","العدد","Numbers","Ἀριθμοί"); add("DEU","التثنية","Deuteronomy","Δευτερονόμιον"); add("JOS","يشوع","Joshua","Ἰησοῦς Ναυή");
        add("JDG","القضاة","Judges","Κριταί"); add("RUT","راعوث","Ruth","Ῥούθ"); add("1SA","صموئيل الأول","1 Samuel","Α΄ Βασιλειῶν");
        add("2SA","صموئيل الثاني","2 Samuel","Β΄ Βασιλειῶν"); add("1KI","الملوك الأول","1 Kings","Γ΄ Βασιλειῶν"); add("2KI","الملوك الثاني","2 Kings","Δ΄ Βασιλειῶν");
        add("1CH","أخبار الأيام الأول","1 Chronicles","Α΄ Παραλειπομένων"); add("2CH","أخبار الأيام الثاني","2 Chronicles","Β΄ Παραλειπομένων");
        add("EZR","عزرا","Ezra","Ἔσδρας"); add("NEH","نحميا","Nehemiah","Νεεμίας"); add("EST","أستير","Esther","Ἐσθήρ");
        add("JOB","أيوب","Job","Ἰώβ"); add("PSA","المزامير","Psalms","Ψαλμοί"); add("PRO","الأمثال","Proverbs","Παροιμίαι");
        add("ECC","الجامعة","Ecclesiastes","Ἐκκλησιαστής"); add("SNG","نشيد الأنشاد","Song of Songs","Ἆσμα Ἀσμάτων");
        add("ISA","إشعياء","Isaiah","Ἠσαΐας"); add("JER","إرميا","Jeremiah","Ἱερεμίας"); add("LAM","مراثي إرميا","Lamentations","Θρῆνοι");
        add("EZK","حزقيال","Ezekiel","Ἰεζεκιήλ"); add("DAN","دانيال","Daniel","Δανιήλ"); add("HOS","هوشع","Hosea","Ὡσηέ");
        add("JOL","يوئيل","Joel","Ἰωήλ"); add("AMO","عاموس","Amos","Ἀμώς"); add("OBA","عوبديا","Obadiah","Ὀβδιού"); add("JON","يونان","Jonah","Ἰωνᾶς");
        add("MIC","ميخا","Micah","Μιχαίας"); add("NAM","ناحوم","Nahum","Ναούμ"); add("HAB","حبقوق","Habakkuk","Ἀμβακούμ");
        add("ZEP","صفنيا","Zephaniah","Σοφονίας"); add("HAG","حجي","Haggai","Ἀγγαῖος"); add("ZEC","زكريا","Zechariah","Ζαχαρίας"); add("MAL","ملاخي","Malachi","Μαλαχίας");
        add("MAT","متى","Matthew","Κατὰ Ματθαῖον"); add("MRK","مرقس","Mark","Κατὰ Μᾶρκον"); add("LUK","لوقا","Luke","Κατὰ Λουκᾶν"); add("JHN","يوحنا","John","Κατὰ Ἰωάννην");
        add("ACT","أعمال الرسل","Acts","Πράξεις Ἀποστόλων"); add("ROM","رومية","Romans","Πρὸς Ῥωμαίους"); add("1CO","كورنثوس الأولى","1 Corinthians","Πρὸς Κορινθίους Α΄");
        add("2CO","كورنثوس الثانية","2 Corinthians","Πρὸς Κορινθίους Β΄"); add("GAL","غلاطية","Galatians","Πρὸς Γαλάτας"); add("EPH","أفسس","Ephesians","Πρὸς Ἐφεσίους");
        add("PHP","فيلبي","Philippians","Πρὸς Φιλιππησίους"); add("COL","كولوسي","Colossians","Πρὸς Κολοσσαεῖς"); add("1TH","تسالونيكي الأولى","1 Thessalonians","Πρὸς Θεσσαλονικεῖς Α΄");
        add("2TH","تسالونيكي الثانية","2 Thessalonians","Πρὸς Θεσσαλονικεῖς Β΄"); add("1TI","تيموثاوس الأولى","1 Timothy","Πρὸς Τιμόθεον Α΄");
        add("2TI","تيموثاوس الثانية","2 Timothy","Πρὸς Τιμόθεον Β΄"); add("TIT","تيطس","Titus","Πρὸς Τίτον"); add("PHM","فليمون","Philemon","Πρὸς Φιλήμονα");
        add("HEB","العبرانيين","Hebrews","Πρὸς Ἑβραίους"); add("JAS","يعقوب","James","Ἰακώβου"); add("1PE","بطرس الأولى","1 Peter","Πέτρου Α΄");
        add("2PE","بطرس الثانية","2 Peter","Πέτρου Β΄"); add("1JN","يوحنا الأولى","1 John","Ἰωάννου Α΄"); add("2JN","يوحنا الثانية","2 John","Ἰωάννου Β΄");
        add("3JN","يوحنا الثالثة","3 John","Ἰωάννου Γ΄"); add("JUD","يهوذا","Jude","Ἰούδα"); add("REV","الرؤيا","Revelation","Ἀποκάλυψις");
        add("TOB","طوبيا","Tobit","Τωβίτ"); add("JDT","يهوديت","Judith","Ἰουδίθ"); add("WIS","حكمة سليمان","Wisdom","Σοφία Σαλωμῶνος");
        add("SIR","يشوع بن سيراخ","Sirach","Σοφία Σειράχ"); add("BAR","باروخ","Baruch","Βαρούχ"); add("LJE","رسالة إرميا","Letter of Jeremiah","Ἐπιστολὴ Ἱερεμίου");
        add("S3Y","تسبحة الفتية الثلاثة","Song of the Three Youths","Ὕμνος τῶν Τριῶν Παίδων"); add("SUS","سوسنة","Susanna","Σωσάννα"); add("BEL","بال والتنين","Bel and the Dragon","Βὴλ καὶ Δράκων");
        add("1MA","المكابيين الأول","1 Maccabees","Α΄ Μακκαβαίων"); add("2MA","المكابيين الثاني","2 Maccabees","Β΄ Μακκαβαίων"); add("3MA","المكابيين الثالث","3 Maccabees","Γ΄ Μακκαβαίων");
        add("4MA","المكابيين الرابع","4 Maccabees","Δ΄ Μακκαβαίων"); add("1ES","عزرا الأول","1 Esdras","Α΄ Ἔσδρας"); add("2ES","عزرا الثاني","2 Esdras","Β΄ Ἔσδρας");
        add("MAN","صلاة منسى","Prayer of Manasseh","Προσευχὴ Μανασσῆ"); add("PS2","المزمور 151","Psalm 151","Ψαλμὸς 151"); add("ODA","الأودات","Odes","Ὠδαί");
    }
    private BibleBookNames() {}
    private static void add(String code, String ar, String en, String el) { NAMES.put(code, new String[]{ar,en,el}); }
    public static String name(String code, String language) {
        String[] names = NAMES.get(code);
        if (names == null) return code;
        if ("ar".equals(language)) return names[0];
        if ("el".equals(language)) return names[2];
        return names[1];
    }
}
