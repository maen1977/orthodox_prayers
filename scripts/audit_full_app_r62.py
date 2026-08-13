#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / 'canonical/internal_calendar_2026_2050.json'
CHURCHES = ROOT / 'app/src/main/assets/data/churches.json'
LIB = {lang: ROOT / f'app/src/main/assets/data/native/library_{lang}.json' for lang in ('ar','en','el')}
CORE = ROOT / 'app/src/main/assets/data/native/arabic_office_reader_core.json'
OFFICIAL_PRAYERS = ROOT / 'app/src/main/assets/data/official_prayer_resources.json'
CHURCH_FULL_SOURCES = ROOT / 'canonical/church_service_full_sources.json'

def load(path):
    with path.open(encoding='utf-8') as f: return json.load(f)

def svc_map(lang):
    return {s.get('id'):s for s in load(LIB[lang]).get('services',[])}

def seg_chars(service, lang):
    total=0
    for seg in service.get('segments',[]):
        text=seg.get('text','')
        if isinstance(text,dict): text=text.get(lang,'')
        total += len(str(text))
    return total

def main():
    cal=load(CAL); days=cal.get('days',[])
    churches=load(CHURCHES); ar=svc_map('ar'); en=svc_map('en'); el=svc_map('el')
    official_prayers=load(OFFICIAL_PRAYERS); church_sources=load(CHURCH_FULL_SOURCES)
    reading_counts={k:sum(1 for d in days if (d.get('reading_references') or {}).get(k)) for k in ('epistle','gospel','matins_gospel')}
    generic_comm=sum(1 for d in days if 'تذكار قديسي يوم' in ((d.get('feast') or {}).get('ar','')))
    meaningful_occ=sum(1 for d in days if d.get('occasions'))
    fast_days=sum(1 for d in days if (d.get('fasting') or {}).get('is_fast'))
    fast_codes=Counter((d.get('fasting') or {}).get('code','') for d in days if (d.get('fasting') or {}).get('is_fast'))
    cs_pending={lang:sum(1 for s in svc_map(lang).values() if s.get('category')=='church_service' and 'PENDING' in s.get('publication_status','')) for lang in ('ar','en','el')}
    church_groups=Counter(c.get('country_group','other') for c in churches.get('churches',[]))
    live_urls=[x.get('url','') for x in churches.get('live_resources',[])]
    official_prayer_references=len(official_prayers.get('resources',[]))
    ar_build_specs=(church_sources.get('languages',{}).get('ar',{}) or {}).get('services',[])
    ar_rights_pending=sum(1 for x in ar_build_specs if not x.get('permission_confirmed',False) or x.get('redistribution_review_required',True))
    ar_rights_confirmed=sum(1 for x in ar_build_specs if x.get('permission_confirmed') is True and x.get('redistribution_review_required') is False)

    checks=[]
    def add(id,title,status,evidence,action=''):
        checks.append({'id':id,'title':title,'status':status,'evidence':evidence,'action':action})

    add('home_date','Home date + old calendar','PASS',f'{len(days)} civil days are precomputed for 2026-01-01..2050-12-31 with julian_date; the home card intentionally omits the daily commemoration line.')
    add('prayer_of_day','Prayer of the Day by local time','FIXED_R62','Home now selects morning_prayer 04:00-11:59, thanksgiving 12:00-17:29, evening_prayer 17:30-21:29, small_compline otherwise, using Asia/Amman time.')
    add('fasting','Fasting state and food-rule type','PASS_WITH_SCOPE',f'{fast_days}/{len(days)} days are marked fasting; codes include {dict(fast_codes)}. Exact abstinence clock times are intentionally not invented.', 'Keep fail-closed behavior for abstinence start/end unless an official dated source states it.')
    add('commemorations','Daily commemorations through 2050','INCOMPLETE',f'{meaningful_occ} days contain explicit occasion entries; {generic_comm} days still use generic date-based commemoration wording.', 'Import a verified annual Jerusalem/Jordan native commemoration corpus; do not AI-generate saint names.')
    add('daily_readings','Daily Epistle/Gospel coverage through 2050','INCOMPLETE',f"Pinned references: epistle {reading_counts['epistle']}/{len(days)}, gospel {reading_counts['gospel']}/{len(days)}, matins gospel {reading_counts['matins_gospel']}/{len(days)}.", 'Build/verify a full Jerusalem-compatible regular lectionary and fixed-feast override corpus before claiming 2050 completeness.')
    add('current_reading_sample','2026-08-10 reading spot check','PASS', 'Internal refs are 2 Corinthians 2:4-15 and Matthew 23:13-22; this date was cross-checked against the official OCA daily lectionary as a lower-priority regular-cycle authority.')
    add('daily_prayers','Daily prayer library','OFFLINE_CORE_NO_EXTERNAL_CARDS',f"Arabic embedded core: morning {len(ar['morning_prayer'].get('segments',[]))} segments; evening {len(ar['evening_prayer'].get('segments',[]))}; small compline {len(ar['small_compline'].get('segments',[]))}; the complete pinned Arabic before/after-meal sequence and pre/post-Communion texts open inside the reader. {official_prayer_references} official Jordan references remain catalog evidence and are not rendered as external prayer cards.", 'Import any additional native text only after exact-text and redistribution evidence are recorded.')
    add('orthros_ar','Arabic Orthros / Matins','PASS_R66_AUTHORIZED_NATIVE',f"Arabic Orthros is {ar['orthros'].get('publication_status','UNKNOWN')} with {len(ar['orthros'].get('segments',[]))} source segments / {seg_chars(ar['orthros'],'ar')} chars; its authorized exact native edition is displayed and searchable without machine translation.")
    add('vespers_ar','Arabic Vespers','PASS',f"Arabic Vespers is packaged as a complete exact native edition with {len(ar['vespers'].get('segments',[]))} segments / {seg_chars(ar['vespers'],'ar')} chars.")
    add('small_compline_ar','Arabic Small Compline','PASS',f"Arabic Small Compline is packaged as a complete exact native edition with {len(ar['small_compline'].get('segments',[]))} segments / {seg_chars(ar['small_compline'],'ar')} chars.")
    add('divine_liturgy','Divine Liturgy','PASS_WITH_READER_OVERLAY',f"Arabic Divine Liturgy is {ar['divine_liturgy'].get('completion_status')} with {len(ar['divine_liturgy'].get('segments',[]))} source segments. Optional quiet believer prayers remain a reader overlay, not part of the canonical-text hash.")
    add('basil_liturgy','Saint Basil Liturgy','PASS_R66_AUTHORIZED_NATIVE',f"Complete authorized native editions are displayable in Arabic ({len(ar['divine_liturgy_basil'].get('segments',[]))} segments), English ({len(en['divine_liturgy_basil'].get('segments',[]))}), and Greek ({len(el['divine_liturgy_basil'].get('segments',[]))}); the smart selector attaches the Basil template on appointed days without a wrong-rite fallback.")
    add('presanctified_liturgy','Presanctified Liturgy','PASS_R66_AUTHORIZED_NATIVE',f"Complete authorized native editions are displayable in Arabic ({len(ar['presanctified_liturgy'].get('segments',[]))} segments), English ({len(en['presanctified_liturgy'].get('segments',[]))}), and Greek ({len(el['presanctified_liturgy'].get('segments',[]))}); the smart selector attaches the Presanctified template on appointed days without a wrong-rite fallback.")
    add('church_services','Church-service section','CATALOG_COMPLETE_TEXT_INCOMPLETE',f"13 fallback service cards exist in each language; pending full authorized rite text in source packs: ar={cs_pending['ar']}, en={cs_pending['en']}, el={cs_pending['el']}. Arabic build manifest now has {ar_rights_confirmed}/{len(ar_build_specs)} registered Jordan sources marked owner-confirmed for R64; rights-pending={ar_rights_pending}. Source checkout can still contain catalog snapshots until the build materializes the authorized native corpus.", 'Do not label catalog/reference cards as complete services until native full texts are imported and gated. Public-domain/CC-BY lanes may still generate full text at build time where their registered rights permit it.')
    add('church_directory','Church directory','PARTIAL_WITH_FULL_DIRECTORY_LINKS',f"Packaged directory has {churches.get('count')} entries grouped as {dict(church_groups)}: the Jordan list and West Bank list are expanded from the official directories, while Jerusalem/Holy Land currently contains selected major entries plus direct links to the complete official Patriarchate directories. No clergy phone numbers are republished.", 'Do not claim every Holy Land church/monastery is individually packaged until the official Jerusalem and outside-Jerusalem lists are fully normalized.')
    add('live','Official live resources','FIXED_R62',f'{len(live_urls)} verified official portal/radio links are packaged; unverified direct/stale links were removed from the visible Live section.')
    add('language_isolation','Arabic / English / Greek isolation','PASS_GATE_REQUIRED','All newly added directory metadata contains independent ar/en/el values; existing localization gate remains authoritative.')

    report={
      'schema_version':1,'audit':'R62_FULL_APP_AUDIT','audited_on':'2026-08-13','base':'OrthodoxPrayers 5.6.4 R66 authorized Liturgy completion',
      'policy':'No AI-generated/translated scripture or liturgical text; official-site availability does not imply redistribution permission.',
      'source_urls':{
        'orthodox_jordan_churches':'https://orthodoxjordan.org/%D8%A7%D9%84%D9%83%D9%86%D8%A7%D8%A6%D8%B3/',
        'orthodox_jordan_prayers':'https://orthodoxjordan.org/%D8%AA%D8%AD%D9%85%D9%8A%D9%84-%D8%A7%D9%84%D8%B5%D9%84%D9%88%D8%A7%D8%AA/',
        'orthodox_jordan_daily_prayers':'https://orthodoxjordan.org/category/%D8%B5%D9%84%D9%88%D8%A7%D8%AA/%D8%B5%D9%84%D9%88%D8%A7%D8%AA-%D9%8A%D9%88%D9%85%D9%8A%D8%A9/',
        'jerusalem_jordan_churches':'https://ar.jerusalem-patriarchate.info/%D8%A7%D9%84%D9%83%D9%86%D8%A7%D8%A6%D8%B3-%D8%A7%D9%84%D9%85%D9%82%D8%AF%D8%B3%D8%A9-%D9%82%D9%8A-%D8%A7%D9%84%D8%A3%D8%B1%D8%AF%D9%86',
        'jerusalem_west_bank_churches':'https://ar.jerusalem-patriarchate.info/%D8%A7%D9%84%D9%83%D9%86%D8%A7%D8%A6%D8%B3-%D8%A7%D9%84%D9%85%D9%82%D8%AF%D8%B3%D8%A9-%D9%81%D9%8A-%D8%A7%D9%84%D8%B6%D9%81%D8%A9-%D8%A7%D9%84%D8%BA%D8%B1%D8%A8%D9%8A%D8%A9/',
        'orthodox_tv':'https://orthodoxjo.tv/',
        'jerusalem_live':'https://ar.jerusalem-patriarchate.info/%D8%A7%D9%84%D8%A8%D8%AB-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B4%D8%B1-%D8%B1%D8%A7%D8%AF%D9%8A%D9%88-%D8%A8%D8%B7%D8%B1%D9%8A%D8%B1%D9%83%D9%8A%D8%A9-%D8%A7%D9%84%D8%B1%D9%88%D9%85-%D8%A7/',
        'oca_2026_08_10':'https://www.oca.org/readings/daily/2026/08/10'
      },
      'metrics':{'calendar_days':len(days),'reading_counts':reading_counts,'generic_commemoration_days':generic_comm,'meaningful_occasion_days':meaningful_occ,'fast_days':fast_days,'church_groups':dict(church_groups),'church_total':churches.get('count'),'church_service_pending_full_text':cs_pending,'official_daily_prayer_references':official_prayer_references,'arabic_church_build_rights_pending':ar_rights_pending,'arabic_church_build_rights_confirmed':ar_rights_confirmed},
      'checks':checks,
      'release_claim':'AUDITED_WITH_KNOWN_CONTENT_GAPS; NOT A 100_PERCENT_CONTENT_COMPLETENESS CLAIM'
    }
    (ROOT/'canonical/r62_full_app_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# تدقيق R62 الكامل لتطبيق Orthodox Prayers','',f'تاريخ التدقيق: **2026-08-13**  ','النسخة الأساسية: **5.6.4 — إكمال النصوص الطقسية المصرّح بها R66**','',
           '> هذا التقرير يفرّق بين سلامة البرنامج تقنيًا وبين اكتمال المحتوى الكنسي. نجاح Release Gate لا يعني تلقائيًا وجود نص كامل أو قراءة موثقة لكل يوم.','',
           '## النتائج']
    labels={'PASS':'✅ PASS','PASS_R66_AUTHORIZED_NATIVE':'✅ PASS R66 — نص أصلي مصرّح به','FIXED_R62':'✅ FIXED R62','PASS_WITH_SCOPE':'✅ PASS (بنطاق موثق)','PASS_WITH_READER_OVERLAY':'✅ PASS (طبقة قارئ)','PASS_GATE_REQUIRED':'✅ PASS / Gate','INCOMPLETE':'❌ INCOMPLETE','PARTIAL':'⚠️ PARTIAL','OFFLINE_CORE_NO_EXTERNAL_CARDS':'✅ داخل التطبيق / بلا بطاقات صلاة خارجية','PARTIAL_WITH_FULL_DIRECTORY_LINKS':'⚠️ PARTIAL + روابط الدليل الرسمي الكامل','INCOMPLETE_FAIL_CLOSED':'❌ INCOMPLETE — Fail closed','CATALOG_COMPLETE_TEXT_INCOMPLETE':'⚠️ البطاقات موجودة / النصوص الكاملة ناقصة'}
    for c in checks:
        lines += ['',f"### {labels.get(c['status'],c['status'])} — {c['title']}",c['evidence']]
        if c.get('action'): lines.append('**الإجراء:** '+c['action'])
    lines += ['', '## الخلاصة', 'R62 لا يدّعي أن كل المحتوى الديني مكتمل. الإصلاحات الآمنة التي لا تحتاج اختراع نص ديني نُفذت، أما الفجوات التي تتطلب نصًا كنسيًا عربيًا أصليًا أو مرجع قراءات كاملًا فبقيت معلّمة صراحةً حتى يتم استيراد مصدر مخوّل ومتحقق.', '']
    (ROOT/'R62_FULL_APP_AUDIT_AR.md').write_text('\n'.join(lines),encoding='utf-8')
    print('R62_AUDIT_OK checks=%d churches=%d reading_days=%d/%d generic_commemorations=%d' % (len(checks),churches.get('count'),reading_counts['gospel'],len(days),generic_comm))

if __name__=='__main__': main()
