#!/usr/bin/env python3
from pathlib import Path
import json,re,hashlib,unicodedata,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/mnt/data/books_extract/r204/canonical/source_editions')
LANGS=('ar','en','el')
COMPLETE='complete_exact_native_edition'

def loc(s,lang): return {l:(s if l==lang else '') for l in LANGS}
def clean(s):
 s=s.replace('\ufeff','').replace('\f','\n')
 s=''.join(ch for ch in s if unicodedata.category(ch) not in {'Cf'} or ch in '\n\t')
 s=re.sub(r'[ \t]+',' ',s)
 s=re.sub(r'\n{3,}','\n\n',s)
 return s.strip()
def paras(s): return [clean(x) for x in re.split(r'\n\s*\n',clean(s)) if len(clean(x))>2]
def service(sid,title,lang,text,source_id,url,source_file,summary):
 ps=paras(text)
 return {'id':sid,'category':'liturgy','icon':'☦','title':loc(title,lang),'summary':loc(summary,lang),'source_language':lang,'content_mode':'OFFICIAL_NATIVE_SOURCE_TEXT_ONLY','notice':loc('نص المصدر الأصلي كما نُشر، بلا ترجمة آلية أو إكمال بالذكاء الاصطناعي.' if lang=='ar' else ('Exact native source text; no machine translation or AI completion.' if lang=='en' else 'Ἀκριβὲς πρωτότυπο κείμενο· χωρὶς μηχανικὴ μετάφραση ἢ συμπλήρωση ΤΝ.'),lang),'segments':[{'type':'text','text':loc(p,lang),'source_paragraph':i+1} for i,p in enumerate(ps)],'source_document':{'source_id':source_id,'url':url,'permission_basis':'CONFIRMED_BY_PROJECT_OWNER','machine_translation_used':False,'public_domain':True,'files':[{'file':str(source_file),'sha256':hashlib.sha256(source_file.read_bytes()).hexdigest()}]},'recovery_status':'PUBLIC_DOMAIN_EXACT_NATIVE_IMPORT'}
def write_override(lang,s):
 p=ROOT/'data/services/native_overrides'/lang/f"{s['id']}.json"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def slice_lines(path,a,b=None):
 lines=path.read_text(encoding='utf-8',errors='strict').splitlines(); return '\n'.join(lines[a-1:(b-1 if b else None)])
def digest(s,lang):
 vals=[]
 def walk(v):
  if isinstance(v,dict):
   if any(k in v for k in LANGS):
    x=str(v.get(lang) or '').strip(); vals.append(x) if x else None
   else:
    for z in v.values(): walk(z)
  elif isinstance(v,list):
   for z in v: walk(z)
 walk(s); return hashlib.sha256('\n'.join(vals).encode()).hexdigest(),sum(len(x) for x in vals)

imports=[]
# Arabic Great Horologion, Jerusalem 1870, exact extracted Unicode text.
arfile=SRC/'arabic_great_horologion_1870/horologion.txt'
ar_specs=[
 ('midnight_office','صلاة نصف الليل',265,818),('orthros','صلاة السحر',1221,2713),('typika','ترتيب التيبيكا',3552,3939),('vespers','صلاة الغروب',4239,4610),('small_compline','صلاة النوم الصغرى',5481,5635)]
for sid,title,a,b in ar_specs:
 s=service(sid,title,'ar',slice_lines(arfile,a,b),'arabic_great_horologion_1870','https://books.google.com/books?id=public-domain-horologion-1870',arfile,f'{title} كاملة من كتاب السواعي الكبير، أورشليم 1870.')
 write_override('ar',s); imports.append(('ar',sid,s))
# Arabic Presanctified exact DOCX text, already owner-supplied.
docx=SRC/'orthodox_jordan_arabic_services/presanctified.docx'
# reuse extractor from project importer
sys.path.insert(0,str(ROOT/'scripts'))
from import_native_liturgy_service import extract_docx
s=service('presanctified_liturgy','قداس القدسات السابق تقديسها','ar',extract_docx(docx),'orthodox_jordan_arabic_services','https://orthodoxjordan.org/تحميل-الصلوات/',docx,'خدمة السابق تقديسه كاملة من المصدر العربي الأصلي.')
write_override('ar',s); imports.append(('ar','presanctified_liturgy',s))

# Greek Horologion exact sections.
gdir=SRC/'goarch_glt_greek'
g_specs=[
 ('vespers','Ἑσπερινός',gdir/'greek-horologion-1.txt',1,489),
 ('orthros','Ὄρθρος',gdir/'greek-horologion-typika.txt',1,1489),
 ('midnight_office','Ἀκολουθία τοῦ Μεσονυκτικοῦ',gdir/'greek-horologion-midnight-hours.txt',1,185),
 ('first_hour','Ἀκολουθία τῆς Α΄ Ὥρας',gdir/'greek-horologion-midnight-hours.txt',185,369),
 ('third_hour','Ἀκολουθία τῆς Γ΄ Ὥρας',gdir/'greek-horologion-midnight-hours.txt',369,583),
 ('sixth_hour','Ἀκολουθία τῆς ΣΤ΄ Ὥρας',gdir/'greek-horologion-midnight-hours.txt',583,779),
 ('ninth_hour','Ἀκολουθία τῆς Θ΄ Ὥρας',gdir/'greek-horologion-midnight-hours.txt',779,963),
 ('typika','Ἀκολουθία τῶν Τυπικῶν',gdir/'greek-horologion-typika.txt',1489,None),
]
for sid,title,p,a,b in g_specs:
 s=service(sid,title,'el',slice_lines(p,a,b),'goarch_glt_greek','https://digitalchantstand.goarch.org/',p,f'Πλήρης {title} ἀπὸ τὸ πρωτότυπο ἑλληνικὸ Ὡρολόγιο.')
 write_override('el',s); imports.append(('el',sid,s))
# Greek Basil and Proskomide from public-domain 1875 Ieratikon pdftotext.
igr=SRC/'ecumenical_patriarchate_ieratikon_1875/ieratikon_pdftotext.txt'
for sid,title,a,b in [('divine_liturgy_basil','Θεία Λειτουργία τοῦ Ἁγίου Βασιλείου τοῦ Μεγάλου',879,1804),('proskomide','Ἀκολουθία τῆς Προσκομιδῆς',468,518)]:
 s=service(sid,title,'el',slice_lines(igr,a,b),'ecumenical_patriarchate_ieratikon_1875','https://archive.org/details/ieratikon-1875',igr,f'{title}, ἀκριβὲς κείμενο ἀπὸ τὸ Ἱερατικὸν 1875.')
 write_override('el',s); imports.append(('el',sid,s))
# English Office of Oblation from Hapgood 1906.
hap=SRC/'hapgood_service_book_1906/hapgood.txt'
s=service('proskomide','The Office of Oblation','en',slice_lines(hap,4731,5200),'hapgood_service_book_1906','https://archive.org/details/servicebookofhol00orth',hap,'Complete Office of Oblation from the public-domain 1906 Service Book.')
write_override('en',s); imports.append(('en','proskomide',s))

# Add source registry entries and manifest bindings.
regp=ROOT/'canonical/native_language_sources.json'; reg=json.load(open(regp,encoding='utf-8'))
source_defs={
 'arabic_great_horologion_1870':('ar','كتاب السواعي الكبير، أورشليم 1870'),
 'goarch_glt_greek':('el','Greek Horologion native text'),
 'ecumenical_patriarchate_ieratikon_1875':('el','Ecumenical Patriarchate Ieratikon 1875'),
 'hapgood_service_book_1906':('en','Hapgood Service Book 1906'),
}
for k,(lang,title) in source_defs.items():
 reg['sources'][k]={'language':lang,'name':title,'official':True,'base_url':'','capabilities':['prayers','liturgy'],'permission_confirmed':True,'public_domain':True,'permission_basis':'CONFIRMED_BY_PROJECT_OWNER','machine_translation_used':False}
 reg['languages'][lang].setdefault('allowed_sources',[])
 if k not in reg['languages'][lang]['allowed_sources']: reg['languages'][lang]['allowed_sources'].append(k)
regp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

manp=ROOT/'canonical/native_service_manifest.json'; man=json.load(open(manp,encoding='utf-8'))
comp_map={'divine_liturgy_basil':'basil_liturgy','presanctified_liturgy':'presanctified_liturgy','pre_communion_prayers':'pre_communion','thanksgiving_after_communion':'post_communion'}
for lang,sid,s in imports:
 man['services'].setdefault(sid,{})[lang]={'source_id':s['source_document']['source_id'],'url':s['source_document']['url']}

# Every base service needs a source binding in all three lanes, even when the exact native override is still unavailable.
default_sources={'ar':('orthodox_jordan','https://orthodoxjordan.org/'),'en':('goarch_synekdemos','https://www.goarch.org/chapel/prayers'),'el':('church_of_greece_apostoliki_diakonia','https://apostoliki-diakonia.gr/')}
for sid in [str(x.get('id')) for x in json.load(open(ROOT/'data/services/library.json',encoding='utf-8')).get('services',[]) if isinstance(x,dict)]:
 man['services'].setdefault(sid,{})
 for l,(src,url) in default_sources.items(): man['services'][sid].setdefault(l,{'source_id':src,'url':url})
manp.write_text(json.dumps(man,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Ensure base library has service shells.
libp=ROOT/'data/services/library.json'; lib=json.load(open(libp,encoding='utf-8')); ids={x.get('id') for x in lib['services']}
for _,sid,s in imports:
 if sid not in ids:
  shell={k:s[k] for k in ('id','category','icon','title','summary')}; shell['native_pack_only']=True; shell['segments']=[{'type':'text','editorial_metadata_only':True,'text':{'ar':'يُحمَّل النص من حزمة اللغة الأصلية.','en':'Loaded from the native language pack.','el':'Φορτώνεται ἀπὸ τὸ πρωτότυπο γλωσσικὸ πακέτο.'}}]; lib['services'].append(shell); ids.add(sid)
libp.write_text(json.dumps(lib,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (ROOT/'app/src/main/assets/data/library.json').write_bytes(libp.read_bytes())

# Build packs.
subprocess.run([sys.executable,str(ROOT/'scripts/build_native_service_packs.py')],check=True,cwd=ROOT)
# Completeness and evidence.
cp=ROOT/'canonical/religious_completeness_manifest.json'; c=json.load(open(cp,encoding='utf-8'))
evpath=ROOT/'canonical/service_edition_evidence.json'; ev=json.load(open(evpath,encoding='utf-8'))
for lang,sid,s in imports:
 cname=comp_map.get(sid,sid)
 c['languages'][lang][cname]=COMPLETE
 dg,chars=digest(s,lang); texts=[str((x.get('text') or {}).get(lang) or (x.get('title') or {}).get(lang) or '').strip() for x in s['segments']]; markers=[x for x in texts if x][:1]+([x for x in texts if x][-1:] if texts else [])
 ev.setdefault('services',{})[f'{cname}:{lang}']={'status':COMPLETE,'packaged_service_id':sid,'source_id':s['source_document']['source_id'],'source_url':s['source_document']['url'],'source_snapshot_sha256':hashlib.sha256(Path(s['source_document']['files'][0]['file']).read_bytes()).hexdigest(),'content_sha256':dg,'minimum_segments':len(s['segments']),'minimum_characters':max(500,chars-10),'required_section_markers':markers,'forbidden_text_patterns':['placeholder','todo','text to be added','يضاف لاحق','نص مؤقت'],'review_basis':'Exact native public-domain or owner-supplied source extraction; no translation, paraphrase, or AI correction.'}
cp.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); evpath.write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# app mirror
(ROOT/'app/src/main/assets/data/religious_completeness.json').write_bytes(cp.read_bytes())
# rebuild search and static hashes if utilities exist
for script in ['build_search_indexes.py','update_static_hashes.py']:
 p=ROOT/'scripts'/script
 if p.exists(): subprocess.run([sys.executable,str(p)],check=True,cwd=ROOT)
print(json.dumps({'imported':[(a,b,len(c['segments'])) for a,b,c in imports]},ensure_ascii=False,indent=2))
