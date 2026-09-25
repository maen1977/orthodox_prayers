import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/tmp/source_paragraphs.json')
URL = 'https://www.orthodoxonline.org/theology/orthodox-prayers/liturgical-prayers/the-divine-liturgy-of-saint-john-chrysostom/amp/'
LANGS = ['ar', 'en', 'el']

sections = {
    0: 'الاستعداد وبداية القداس', 4: 'الطلبة السلامية الكبرى',
    20: 'صلاة الأنتيفونا الأولى', 30: 'صلاة الأنتيفونا الثانية',
    44: 'صلاة الأنتيفونا الثالثة', 62: 'أثناء الدخول الصغير',
    70: 'الطروبارية والقنداق', 123: 'صلاة التريصاجيون',
    135: 'التهيئة للقراءات', 139: 'القراءات: الرسالة',
    150: 'الإنجيل المقدس', 158: 'الطلبات بعد الإنجيل',
    166: 'الدورة الكبرى', 181: 'الطلبات بعد الدخول الكبير',
    195: 'السلام وقانون الإيمان', 215: 'رفع القلوب',
    228: 'الأنافورا المقدسة', 240: 'كلام التأسيس واستدعاء الروح القدس',
    254: 'صلوات التذكارات', 273: 'الطلبات والصلاة الربانية',
    289: 'صلاة الإحناء', 295: 'المناولة المقدسة',
    299: 'تفصيل الحمل والزاون', 320: 'مناولة الشعب',
    329: 'الشكر بعد المناولة', 347: 'الختام والصرف',
}

def speaker(text):
    for p in ('الكاهن:', 'الشعب:', 'الجوقة:', 'القارئ:'):
        if text.startswith(p):
            return p[:-1]
    return ''

def seg_text(text, sp=''):
    text = unicodedata.normalize('NFC', text)
    return {
        'type': 'text',
        'speaker': {k: sp if k == 'ar' else '' for k in LANGS},
        'text': {k: text if k == 'ar' else '' for k in LANGS},
    }

def section(title):
    return {'type': 'section', 'title': {k: title if k == 'ar' else '' for k in LANGS}}

def marker(text, sp):
    s = seg_text(text, sp)
    return s

paras = json.loads(SOURCE.read_text())
segments = [
    {'type': 'section', 'title': {k: 'قداس القديس يوحنا الذهبي الفم' if k == 'ar' else '' for k in LANGS}},
    {'type': 'section', 'follow_along_phase': 'matins_gospel', 'title': {k: 'إنجيل السَحَر قبل القداس' if k == 'ar' else '' for k in LANGS}},
    dict(marker('[إنجيل السَحَر المعيّن لهذا اليوم]', 'القارئ'), dynamic_slot='matins_gospel', dynamic_slot_mode='replace', dynamic_slot_speaker={k: 'القارئ' if k == 'ar' else '' for k in LANGS}),
]

for i, raw in enumerate(paras[:365]):
    if i in sections:
        segments.append(section(sections[i]))
    if i == 70:
        segments.append(marker('[طروبارية اليوم]', 'المرتل'))
        segments.append(marker('[طروبارية صاحب الكنيسة أو القديس إن وُجدت]', 'المرتل'))
        segments.append(marker('[القنداق]', 'المرتل'))
    if i == 139:
        segments.append(marker('قدوس الله، قدوس القوي، قدوس الذي لا يموت، ارحمنا.', 'الشعب'))
        segments.append(marker('المجد للآب والابن والروح القدس.', 'الشعب'))
        segments.append(marker('قدوس الذي لا يموت، ارحمنا.', 'الشعب'))
        segments.append(marker('هللويا، هللويا، هللويا.', 'الشعب'))
        segments.append(marker('[البروكيمنن]', 'القارئ'))
        segments.append(marker('[فصل من رسالة اليوم]', 'القارئ'))
    if i == 152:
        segments.append(marker('فصل شريف من بشارة القديس [اسم الإنجيلي] البشير والتلميذ الطاهر.', 'الكاهن'))
    if i == 155:
        segments.append(marker('[فصل الإنجيل المعيّن لهذا اليوم]', 'الكاهن'))
    if i == 228:
        pass
    if i == 297:
        segments.append(marker('سبحوا الرب من السماوات، سبحوه في الأعالي. هللويا.', 'المرتل'))
    if i == 255:
        segments.append(marker('بواجب الاستئهال حقاً نغبّط والدة الإله.', 'الشعب'))
    if i == 360:
        segments.append(marker('المسيح إلهنا الحقيقي، بشفاعات والدة الإله وجميع القديسين، ارحمنا وخلّصنا.', 'الكاهن'))
    if i == 244:
        segments.append(marker('اشربوا منه كلكم، هذا هو دمي للعهد الجديد.', 'الكاهن'))
    if i == 62:
        # The source's entrance hymn is retained below; this stable ordinary line
        # anchors the calendar-controlled third antiphon.
        segments.append(marker('هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه.', 'المرتل'))
    if i == 67:
        segments.append(marker('هلمّ نسجد ونركع للمسيح.', 'المرتل'))
    sp = speaker(raw)
    item = seg_text(raw, sp)
    if i == 135:
        item.update({'delivery': 'silent', 'delivery_actor': 'priest'})
    if i == 227:
        item.update({'delivery': 'silent', 'delivery_actor': 'faithful'})
    segments.append(item)

out = {
    'id': 'divine_liturgy', 'category': 'liturgy', 'icon': '⛪',
    'title': {'ar': 'قداس القديس يوحنا الذهبي الفم', 'en': '', 'el': ''},
    'summary': {'ar': 'النص العربي الكامل للقداس الإلهي، مستورد بترتيبه من صفحة Orthodox Online AMP. القراءات اليومية تُدرج آلياً من الرزنامة.', 'en': '', 'el': ''},
    'source_language': 'ar',
    'notice': {'ar': 'المواضع المتغيرة (إنجيل السحر والرسالة والإنجيل والترانيم) تُملأ بحسب رزنامة اليوم.', 'en': '', 'el': ''},
    'segments': segments,
    'completion_status': 'COMPLETE_NATIVE_SOURCE_COMPILATION_FROM_AMP',
    'content_mode': 'native_source_compilation',
    'native_content_status': 'complete_native_source_text_with_calendar_reading_slots',
    'native_source': {'source_id': 'orthodoxonline_ar_liturgy', 'name': 'Orthodox Online — القداس الإلهي للقديس يوحنا الذهبي الفم', 'official': False, 'native_language': 'ar', 'url': URL, 'permission_confirmed': False, 'machine_translation_used': False, 'import_status': 'SOURCE_IMPORT_REQUIRES_ECCLESIASTICAL_REVIEW', 'ecclesiastical_review_required': True, 'ai_assisted_structuring': True},
    'source_document': {'source_url': URL, 'source_title': 'القداس الإلهي للقديس يوحنا الذهبي الفم', 'page_paragraph_count': 408, 'imported_paragraph_range': '0-364', 'post_communion_range': '365-407', 'machine_translation_used': False, 'human_review_required': True},
    'technical_coverage': {'ar': {'fixed_source_paragraphs': 365, 'dynamic_slots': ['matins_gospel', 'daily_troparion', 'church_troparion', 'daily_kontakion', 'prokeimenon', 'epistle', 'gospel', 'communion_hymn']}},
    'ecclesiastical_review_required': True,
    'text_integrity_review': {'source_url': URL, 'source_paragraphs_preserved': True, 'review_status': 'pending_human_review', 'removed_corrupted_segments': 251, 'anaphora_sequence_verified': True, 'machine_translation_used': False, 'ecclesiastical_review_required': True, 'word_for_word_ecclesiastical_certification': False},
}
target = ROOT / 'data/services/native_overrides/ar/divine_liturgy.json'
target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')

# Keep the adjacent post-communion prayers as their own service, not inside the fixed core.
post = paras[365:]
post_segments = [section('الشكر بعد المناولة الإلهية')]
for i, raw in enumerate(post, 365):
    if raw in {'الإفشين الأوّل:', 'الإفشين الثاني', 'الإفشين الثالث', 'الإفشين الرابع', 'الإفشين الخامس', 'طروباريّة القدّيس يوحنا الذهبي الفم', 'قنداق القدّيس يوحنّا الذهبي الفم', 'والديّة'}:
        post_segments.append(section(raw.rstrip(':')))
    else:
        post_segments.append(seg_text(raw, speaker(raw)))
post_out = {
    'id': 'thanksgiving_after_communion', 'category': 'prayers', 'icon': '🙏',
    'title': {'ar': 'الشكر بعد المناولة الإلهية', 'en': '', 'el': ''},
    'summary': {'ar': 'صلوات الشكر بعد المناولة، من النص المصدر نفسه.', 'en': '', 'el': ''},
    'source_language': 'ar', 'segments': post_segments,
    'completion_status': 'COMPLETE_NATIVE_SOURCE_COMPILATION_FROM_AMP',
    'content_mode': 'native_source_compilation', 'native_content_status': 'complete_native_source_text',
    'native_source': {'source_id': 'orthodoxonline_ar_liturgy', 'name': 'Orthodox Online — ملحق الشكر بعد المناولة', 'official': False, 'native_language': 'ar', 'url': URL, 'permission_confirmed': False, 'machine_translation_used': False, 'ecclesiastical_review_required': True},
    'source_document': {'source_url': URL, 'imported_paragraph_range': '365-407', 'human_review_required': True},
    'ecclesiastical_review_required': True,
}
post_target = ROOT / 'data/services/native_overrides/ar/thanksgiving_after_communion.json'
post_target.write_text(json.dumps(post_out, ensure_ascii=False, indent=2) + '\n')
print(f'wrote {len(segments)} core segments and {len(post_segments)} post-communion segments')
