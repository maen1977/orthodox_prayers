package com.orthodoxprayers.privateapp.ui.screens;

import android.content.Intent;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import com.orthodoxprayers.privateapp.bible.BibleBookNames;
import com.orthodoxprayers.privateapp.bible.BibleCorpusRepository;
import com.orthodoxprayers.privateapp.ui.ScreenHost;
import com.orthodoxprayers.privateapp.ui.UiKit;

public final class BibleChapterScreen extends BaseScreen {
    private final String book;
    private final int chapter;
    private final BibleCorpusRepository bible;
    public BibleChapterScreen(ScreenHost host,String argument){ super(host); String[] p=argument==null?new String[0]:argument.split(":",2); book=p.length>0?p[0]:""; int c=1; try{if(p.length>1)c=Integer.parseInt(p[1]);}catch(Exception ignored){} chapter=Math.max(1,c); bible=new BibleCorpusRepository(host.activity()); }
    @Override public View createView(){
        String lang=preferences.effectiveLanguage();
        String title=BibleBookNames.name(book,lang)+" "+chapter;
        UiKit.Page page=page(title,true);
        LinearLayout holder=ui.card(); add(page.root,holder,12,8);
        holder.addView(centered(t(lang,"جارٍ تحميل النص…","Loading text…","Φόρτωση κειμένου…"),14,ui.colors().secondaryText(),false));
        new Thread(() -> {
            try{
                BibleCorpusRepository.Chapter value=bible.chapter(lang,book,chapter);
                StringBuilder plain=new StringBuilder();
                for(BibleCorpusRepository.Verse verse:value.verses){ if(plain.length()>0)plain.append("\n"); plain.append(verse.verse).append(". ").append(verse.text); }
                String text=plain.toString();
                holder.post(() -> {
                    holder.removeAllViews();
                    holder.addView(ui.text(text.isEmpty()?t(lang,"النص غير متوفر في هذه الترجمة.","Text is not available in this translation.","Τὸ κείμενο δὲν εἶναι διαθέσιμο σὲ αὐτὴν τὴν ἔκδοση."):text,17,ui.colors().primaryText(),false));
                    if(!text.isEmpty()){
                        Button share=ui.smallButton(t(lang,"مشاركة الأصحاح","Share chapter","Κοινοποίηση κεφαλαίου"),false);
                        share.setOnClickListener(v->{ Intent i=new Intent(Intent.ACTION_SEND); i.setType("text/plain"); i.putExtra(Intent.EXTRA_TEXT,title+"\n\n"+text); try{host.activity().startActivity(Intent.createChooser(i,title));}catch(Exception ignored){} });
                        holder.addView(share,ui.margins(-1,-2,0,10,0,0));
                    }
                });
            }catch(Exception error){holder.post(() -> {holder.removeAllViews();holder.addView(centered(t(lang,"تعذر فتح النص المضمّن.","Could not open the bundled text.","Δὲν ἦταν δυνατὸ νὰ ἀνοιχθεῖ τὸ ἐνσωματωμένο κείμενο."),14,ui.colors().secondaryText(),false));});}
        },"BibleChapter").start();
        return page.scroll;
    }
    private static String t(String l,String ar,String en,String el){return "ar".equals(l)?ar:("el".equals(l)?el:en);}
}
