#!/usr/bin/env python3
"""Prepare the exact native Scripture slice needed by the 2026-07-28 rolling week.

Arabic and Greek are selected directly from the registered eBible public-domain
archives already cached by the project. English is the World English Bible
(public domain), mirrored by Midvash's open bible-data repository. No text is
translated, paraphrased, or automatically marked.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from public_domain_scripture import load_public_domain_corpus

ROOT = Path(__file__).resolve().parents[1]
START_DATE = "2026-07-28"

SPANS = [
    ("1CO", 12, 12, 26),
    ("MAT", 18, 18, 22),
    ("MAT", 19, 1, 2),
    ("MAT", 19, 13, 15),
    ("JHN", 20, 19, 31),
    ("1CO", 3, 9, 17),
    ("MAT", 14, 22, 34),
    ("1CO", 13, 4, 13),
    ("1CO", 14, 1, 5),
    ("MAT", 20, 1, 16),
    ("1CO", 14, 6, 19),
    ("MAT", 20, 17, 28),
    ("1CO", 14, 26, 40),
    ("MAT", 21, 12, 14),
    ("MAT", 21, 17, 20),
    ("MAT", 15, 32, 39),
    ("ROM", 14, 6, 9),
    ("1CO", 4, 9, 16),
    ("JHN", 21, 1, 14),
    ("MAT", 17, 14, 23),
    ("1CO", 15, 12, 19),
    ("MAT", 21, 18, 22),
    ("1CO", 15, 29, 38),
    ("MAT", 21, 23, 27),
]

BOOK_NAMES = {
    "MAT": "Matthew",
    "JHN": "John",
    "ROM": "Romans",
    "1CO": "1 Corinthians",
}


def parse_block(book: str, chapter: int, block: str) -> dict[tuple[str, int, int], str]:
    result: dict[tuple[str, int, int], str] = {}
    for raw in block.strip().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        number_raw, text = raw.split("|", 1)
        key = (book, chapter, int(number_raw))
        if key in result:
            raise ValueError(f"duplicate English verse {key}")
        result[key] = text.strip()
    return result


ENGLISH: dict[tuple[str, int, int], str] = {}

ENGLISH.update(parse_block("MAT", 14, r'''
22|Immediately Jesus made the disciples get into the boat and go ahead of him to the other side, while he sent the multitudes away.
23|After he had sent the multitudes away, he went up into the mountain by himself to pray. When evening had come, he was there alone.
24|But the boat was now in the middle of the sea, distressed by the waves, for the wind was contrary.
25|In the fourth watch of the night, Jesus came to them, walking on the sea.
26|When the disciples saw him walking on the sea, they were troubled, saying, “It’s a ghost!” and they cried out for fear.
27|But immediately Jesus spoke to them, saying, “Cheer up! It is I! Don’t be afraid.”
28|Peter answered him and said, “Lord, if it is you, command me to come to you on the waters.”
29|He said, “Come!” Peter stepped down from the boat and walked on the waters to come to Jesus.
30|But when he saw that the wind was strong, he was afraid, and beginning to sink, he cried out, saying, “Lord, save me!”
31|Immediately Jesus stretched out his hand, took hold of him, and said to him, “You of little faith, why did you doubt?”
32|When they got up into the boat, the wind ceased.
33|Those who were in the boat came and worshiped him, saying, “You are truly the Son of God!”
34|When they had crossed over, they came to the land of Gennesaret.
'''))

ENGLISH.update(parse_block("MAT", 15, r'''
32|Jesus summoned his disciples and said, “I have compassion on the multitude, because they have continued with me now three days and have nothing to eat. I don’t want to send them away fasting, or they might faint on the way.”
33|The disciples said to him, “Where could we get so many loaves in a deserted place as to satisfy so great a multitude?”
34|Jesus said to them, “How many loaves do you have?” They said, “Seven, and a few small fish.”
35|He commanded the multitude to sit down on the ground;
36|and he took the seven loaves and the fish. He gave thanks and broke them, and gave to the disciples, and the disciples to the multitudes.
37|They all ate and were filled. They took up seven baskets full of the broken pieces that were left over.
38|Those who ate were four thousand men, in addition to women and children.
39|Then he sent away the multitudes, got into the boat, and came into the borders of Magdala.
'''))

ENGLISH.update(parse_block("MAT", 17, r'''
14|When they came to the multitude, a man came to him, kneeling down to him and saying,
15|“Lord, have mercy on my son, for he is epileptic and suffers grievously; for he often falls into the fire, and often into the water.
16|So I brought him to your disciples, and they could not cure him.”
17|Jesus answered, “Faithless and perverse generation! How long will I be with you? How long will I bear with you? Bring him here to me.”
18|Jesus rebuked the demon, and it went out of him, and the boy was cured from that hour.
19|Then the disciples came to Jesus privately, and said, “Why weren’t we able to cast it out?”
20|He said to them, “Because of your unbelief. For most certainly I tell you, if you have faith as a grain of mustard seed, you will tell this mountain, ‘Move from here to there,’ and it will move; and nothing will be impossible for you.
21|But this kind doesn’t go out except by prayer and fasting.”
22|While they were staying in Galilee, Jesus said to them, “The Son of Man is about to be delivered up into the hands of men,
23|and they will kill him, and the third day he will be raised up.” They were exceedingly sorry.
'''))

ENGLISH.update(parse_block("MAT", 20, r'''
1|“For the Kingdom of Heaven is like a man who was the master of a household, who went out early in the morning to hire laborers for his vineyard.
2|When he had agreed with the laborers for a denarius a day, he sent them into his vineyard.
3|He went out about the third hour, and saw others standing idle in the marketplace.
4|He said to them, ‘You also go into the vineyard, and whatever is right I will give you.’ So they went their way.
5|Again he went out about the sixth and the ninth hour, and did likewise.
6|About the eleventh hour he went out and found others standing idle. He said to them, ‘Why do you stand here all day idle?’
7|“They said to him, ‘Because no one has hired us.’ “He said to them, ‘You also go into the vineyard, and you will receive whatever is right.’
8|“When evening had come, the lord of the vineyard said to his manager, ‘Call the laborers and pay them their wages, beginning from the last to the first.’
9|“When those who were hired at about the eleventh hour came, they each received a denarius.
10|When the first came, they supposed that they would receive more; and they likewise each received a denarius.
11|When they received it, they murmured against the master of the household,
12|saying, ‘These last have spent one hour, and you have made them equal to us who have borne the burden of the day and the scorching heat!’
13|“But he answered one of them, ‘Friend, I am doing you no wrong. Didn’t you agree with me for a denarius?
14|Take that which is yours, and go your way. It is my desire to give to this last just as much as to you.
15|Isn’t it lawful for me to do what I want to with what I own? Or is your eye evil, because I am good?’
16|So the last will be first, and the first last. For many are called, but few are chosen.”
17|As Jesus was going up to Jerusalem, he took the twelve disciples aside, and on the way he said to them,
18|“Behold, we are going up to Jerusalem, and the Son of Man will be delivered to the chief priests and scribes, and they will condemn him to death,
19|and will hand him over to the Gentiles to mock, to scourge, and to crucify; and the third day he will be raised up.”
20|Then the mother of the sons of Zebedee came to him with her sons, kneeling and asking a certain thing of him.
21|He said to her, “What do you want?” She said to him, “Command that these, my two sons, may sit, one on your right hand and one on your left hand, in your Kingdom.”
22|But Jesus answered, “You don’t know what you are asking. Are you able to drink the cup that I am about to drink, and be baptized with the baptism that I am baptized with?” They said to him, “We are able.”
23|He said to them, “You will indeed drink my cup, and be baptized with the baptism that I am baptized with; but to sit on my right hand and on my left hand is not mine to give, but it is for whom it has been prepared by my Father.”
24|When the ten heard it, they were indignant with the two brothers.
25|But Jesus summoned them, and said, “You know that the rulers of the nations lord it over them, and their great ones exercise authority over them.
26|It shall not be so among you; but whoever desires to become great among you shall be your servant.
27|Whoever desires to be first among you shall be your bondservant,
28|even as the Son of Man came not to be served, but to serve, and to give his life as a ransom for many.”
'''))

ENGLISH.update(parse_block("MAT", 21, r'''
12|Jesus entered into the temple of God and drove out all of those who sold and bought in the temple, and overthrew the money changers’ tables and the seats of those who sold the doves.
13|He said to them, “It is written, ‘My house shall be called a house of prayer,’ but you have made it a den of robbers!”
14|The lame and the blind came to him in the temple, and he healed them.
17|He left them and went out of the city to Bethany, and camped there.
18|Now in the morning, as he returned to the city, he was hungry.
19|Seeing a fig tree by the road, he came to it and found nothing on it but leaves. He said to it, “Let there be no fruit from you forever!” Immediately the fig tree withered away.
20|When the disciples saw it, they marveled, saying, “How did the fig tree immediately wither away?”
21|Jesus answered them, “Most certainly I tell you, if you have faith and don’t doubt, you will not only do what was done to the fig tree, but even if you told this mountain, ‘Be taken up and cast into the sea,’ it would be done.
22|All things, whatever you ask in prayer, believing, you will receive.”
23|When he had come into the temple, the chief priests and the elders of the people came to him as he was teaching, and said, “By what authority do you do these things? Who gave you this authority?”
24|Jesus answered them, “I also will ask you one question, which if you tell me, I likewise will tell you by what authority I do these things.
25|The baptism of John, where was it from? From heaven or from men?” They reasoned with themselves, saying, “If we say, ‘From heaven,’ he will ask us, ‘Why then did you not believe him?’
26|But if we say, ‘From men,’ we fear the multitude, for all hold John as a prophet.”
27|They answered Jesus, and said, “We don’t know.” He also said to them, “Neither will I tell you by what authority I do these things.
'''))

ENGLISH.update(parse_block("JHN", 20, r'''
19|When therefore it was evening on that day, the first day of the week, and when the doors were locked where the disciples were assembled, for fear of the Jews, Jesus came and stood in the middle and said to them, “Peace be to you.”
20|When he had said this, he showed them his hands and his side. The disciples therefore were glad when they saw the Lord.
21|Jesus therefore said to them again, “Peace be to you. As the Father has sent me, even so I send you.”
22|When he had said this, he breathed on them, and said to them, “Receive the Holy Spirit!
23|If you forgive anyone’s sins, they have been forgiven them. If you retain anyone’s sins, they have been retained.”
24|But Thomas, one of the twelve, called Didymus, wasn’t with them when Jesus came.
25|The other disciples therefore said to him, “We have seen the Lord!” But he said to them, “Unless I see in his hands the print of the nails, put my finger into the print of the nails, and put my hand into his side, I will not believe.”
26|After eight days, again his disciples were inside and Thomas was with them. Jesus came, the doors being locked, and stood in the middle, and said, “Peace be to you.”
27|Then he said to Thomas, “Reach here your finger, and see my hands. Reach here your hand, and put it into my side. Don’t be unbelieving, but believing.”
28|Thomas answered him, “My Lord and my God!”
29|Jesus said to him, “Because you have seen me, you have believed. Blessed are those who have not seen and have believed.”
30|Therefore Jesus did many other signs in the presence of his disciples, which are not written in this book;
31|but these are written that you may believe that Jesus is the Christ, the Son of God, and that believing you may have life in his name.
'''))

ENGLISH.update(parse_block("JHN", 21, r'''
1|After these things, Jesus revealed himself again to the disciples at the sea of Tiberias. He revealed himself this way.
2|Simon Peter, Thomas called Didymus, Nathanael of Cana in Galilee, and the sons of Zebedee, and two others of his disciples were together.
3|Simon Peter said to them, “I’m going fishing.” They told him, “We are also coming with you.” They immediately went out and entered into the boat. That night, they caught nothing.
4|But when day had already come, Jesus stood on the beach; yet the disciples didn’t know that it was Jesus.
5|Jesus therefore said to them, “Children, have you anything to eat?” They answered him, “No.”
6|He said to them, “Cast the net on the right side of the boat, and you will find some.” They cast it therefore, and now they weren’t able to draw it in for the multitude of fish.
7|That disciple therefore whom Jesus loved said to Peter, “It’s the Lord!” So when Simon Peter heard that it was the Lord, he wrapped his coat around himself (for he was naked), and threw himself into the sea.
8|But the other disciples came in the little boat (for they were not far from the land, but about two hundred cubits away), dragging the net full of fish.
9|So when they got out on the land, they saw a fire of coals there, with fish and bread laid on it.
10|Jesus said to them, “Bring some of the fish which you have just caught.”
11|Simon Peter went up, and drew the net to land, full of one hundred fifty-three great fish. Even though there were so many, the net wasn’t torn.
12|Jesus said to them, “Come and eat breakfast!” None of the disciples dared inquire of him, “Who are you?” knowing that it was the Lord.
13|Then Jesus came and took the bread, gave it to them, and the fish likewise.
14|This is now the third time that Jesus was revealed to his disciples after he had risen from the dead.
'''))

ENGLISH.update(parse_block("ROM", 14, r'''
6|He who observes the day, observes it to the Lord; and he who does not observe the day, to the Lord he does not observe it. He who eats, eats to the Lord, for he gives God thanks. He who doesn’t eat, to the Lord he doesn’t eat, and gives God thanks.
7|For none of us lives to himself, and none dies to himself.
8|For if we live, we live to the Lord. Or if we die, we die to the Lord. If therefore we live or die, we are the Lord’s.
9|For to this end Christ died, rose, and lived again, that he might be Lord of both the dead and the living.
'''))

ENGLISH.update(parse_block("1CO", 3, r'''
9|For we are God’s fellow workers. You are God’s farming, God’s building.
10|According to the grace of God which was given to me, as a wise master builder I laid a foundation, and another builds on it. But let each man be careful how he builds on it.
11|For no one can lay any other foundation than that which has been laid, which is Jesus Christ.
12|But if anyone builds on the foundation with gold, silver, costly stones, wood, hay, or straw,
13|each man’s work will be revealed. For the Day will declare it, because it is revealed in fire; and the fire itself will test what sort of work each man’s work is.
14|If any man’s work remains which he built on it, he will receive a reward.
15|If any man’s work is burned, he will suffer loss, but he himself will be saved, but as through fire.
16|Don’t you know that you are God’s temple and that God’s Spirit lives in you?
17|If anyone destroys God’s temple, God will destroy him; for God’s temple is holy, which you are.
'''))

ENGLISH.update(parse_block("1CO", 4, r'''
9|For I think that God has displayed us, the apostles, last of all, like men sentenced to death. For we are made a spectacle to the world, both to angels and men.
10|We are fools for Christ’s sake, but you are wise in Christ. We are weak, but you are strong. You have honor, but we have dishonor.
11|Even to this present hour we hunger, thirst, are naked, are beaten, and have no certain dwelling place.
12|We toil, working with our own hands. When people curse us, we bless. Being persecuted, we endure.
13|Being defamed, we entreat. We are made as the filth of the world, the dirt wiped off by all, even until now.
14|I don’t write these things to shame you, but to admonish you as my beloved children.
15|For though you have ten thousand tutors in Christ, you don’t have many fathers. For in Christ Jesus, I became your father through the Good News.
16|I beg you therefore, be imitators of me.
'''))

ENGLISH.update(parse_block("1CO", 13, r'''
4|Love is patient and is kind. Love doesn’t envy. Love doesn’t brag, is not proud,
5|doesn’t behave itself inappropriately, doesn’t seek its own way, is not provoked, takes no account of evil;
6|doesn’t rejoice in unrighteousness, but rejoices with the truth;
7|bears all things, believes all things, hopes all things, and endures all things.
8|Love never fails. But where there are prophecies, they will be done away with. Where there are various languages, they will cease. Where there is knowledge, it will be done away with.
9|For we know in part and we prophesy in part;
10|but when that which is complete has come, then that which is partial will be done away with.
11|When I was a child, I spoke as a child, I felt as a child, I thought as a child. Now that I have become a man, I have put away childish things.
12|For now we see in a mirror, dimly, but then face to face. Now I know in part, but then I will know fully, even as I was also fully known.
13|But now faith, hope, and love remain—these three. The greatest of these is love.
'''))

ENGLISH.update(parse_block("1CO", 14, r'''
1|Follow after love and earnestly desire spiritual gifts, but especially that you may prophesy.
2|For he who speaks in another language speaks not to men, but to God, for no one understands, but in the Spirit he speaks mysteries.
3|But he who prophesies speaks to men for their edification, exhortation, and consolation.
4|He who speaks in another language edifies himself, but he who prophesies edifies the assembly.
5|Now I desire to have you all speak with other languages, but even more that you would prophesy. For he is greater who prophesies than he who speaks with other languages, unless he interprets, that the assembly may be built up.
6|But now, brothers, if I come to you speaking with other languages, what would I profit you unless I speak to you either by way of revelation, or of knowledge, or of prophesying, or of teaching?
7|Even lifeless things that make a sound, whether pipe or harp, if they didn’t give a distinction in the sounds, how would it be known what is piped or harped?
8|For if the trumpet gave an uncertain sound, who would prepare himself for war?
9|So also you, unless you uttered by the tongue words easy to understand, how would it be known what is spoken? For you would be speaking into the air.
10|There are, it may be, so many kinds of languages in the world, and none of them is without meaning.
11|If then I don’t know the meaning of the language, I would be to him who speaks a foreigner, and he who speaks would be a foreigner to me.
12|So also you, since you are zealous for spiritual gifts, seek that you may abound to the building up of the assembly.
13|Therefore let him who speaks in another language pray that he may interpret.
14|For if I pray in another language, my spirit prays, but my understanding is unfruitful.
15|What should I do? I will pray with the spirit, and I will pray with the understanding also. I will sing with the spirit, and I will sing with the understanding also.
16|Otherwise, if you bless with the spirit, how will he who fills the place of the unlearned say the “Amen” at your giving of thanks, seeing he doesn’t know what you say?
17|For you most certainly give thanks well, but the other person is not built up.
18|I thank my God, I speak with other languages more than you all.
19|However, in the assembly I would rather speak five words with my understanding, that I might instruct others also, than ten thousand words in another language.
26|What is it then, brothers? When you come together, each one of you has a psalm, has a teaching, has a revelation, has another language, or has an interpretation. Let all things be done to build each other up.
27|If any man speaks in another language, let there be two, or at the most three, and in turn; and let one interpret.
28|But if there is no interpreter, let him keep silent in the assembly, and let him speak to himself and to God.
29|Let two or three of the prophets speak, and let the others discern.
30|But if a revelation is made to another sitting by, let the first keep silent.
31|For you all can prophesy one by one, that all may learn and all may be exhorted.
32|The spirits of the prophets are subject to the prophets,
33|for God is not a God of confusion but of peace, as in all the assemblies of the saints.
34|Let the wives be quiet in the assemblies, for it has not been permitted for them to be talking except in submission, as the law also says,
35|if they desire to learn anything. “Let them ask their own husbands at home, for it is shameful for a wife to be talking in the assembly.”
36|What!? Was it from you that the word of God went out? Or did it come to you alone?
37|If any man thinks himself to be a prophet or spiritual, let him recognize the things which I write to you, that they are the commandment of the Lord.
38|But if anyone is ignorant, let him be ignorant.
39|Therefore, brothers, desire earnestly to prophesy, and don’t forbid speaking with other languages.
40|Let all things be done decently and in order.
'''))

ENGLISH.update(parse_block("1CO", 15, r'''
12|Now if Christ is preached, that he has been raised from the dead, how do some among you say that there is no resurrection of the dead?
13|But if there is no resurrection of the dead, neither has Christ been raised.
14|If Christ has not been raised, then our preaching is in vain and your faith also is in vain.
15|Yes, we are also found false witnesses of God, because we testified about God that he raised up Christ, whom he didn’t raise up if it is true that the dead are not raised.
16|For if the dead aren’t raised, neither has Christ been raised.
17|If Christ has not been raised, your faith is vain; you are still in your sins.
18|Then they also who are fallen asleep in Christ have perished.
19|If we have only hoped in Christ in this life, we are of all men most pitiable.
29|Or else what will they do who are baptized for the dead? If the dead aren’t raised at all, why then are they baptized for the dead?
30|Why do we also stand in jeopardy every hour?
31|I affirm, by the boasting in you which I have in Christ Jesus our Lord, I die daily.
32|If I fought with animals at Ephesus for human purposes, what does it profit me? If the dead are not raised, then “let’s eat and drink, for tomorrow we die.”
33|Don’t be deceived! “Evil companionships corrupt good morals.”
34|Wake up righteously and don’t sin, for some have no knowledge of God. I say this to your shame.
35|But someone will say, “How are the dead raised?” and, “With what kind of body do they come?”
36|You foolish one, that which you yourself sow is not made alive unless it dies.
37|That which you sow, you don’t sow the body that will be, but a bare grain, maybe of wheat, or of some other kind.
38|But God gives it a body even as it pleased him, and to each seed a body of its own.
'''))


def required_keys() -> set[tuple[str, int, int]]:
    keys: set[tuple[str, int, int]] = set()
    for book, chapter, start, end in SPANS:
        keys.update((book, chapter, verse) for verse in range(start, end + 1))
    return keys


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json_sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_existing_english() -> dict[tuple[str, int, int], dict[str, Any]]:
    candidates = [
        ROOT / "canonical" / "generated_daily" / "scripture_2026-07-28" / "en" / "verses.json",
        ROOT / "data" / "scripture" / "native" / "en" / "verses.json",
    ]
    result: dict[tuple[str, int, int], dict[str, Any]] = {}
    for path in candidates:
        if not path.is_file():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            key = (str(item["book_id"]).upper(), int(item["chapter"]), int(item["verse"]))
            result[key] = item
    return result


def build_english_index() -> dict[tuple[str, int, int], dict[str, Any]]:
    index = load_existing_english()
    for (book, chapter, verse), text in ENGLISH.items():
        index[(book, chapter, verse)] = {
            "book_id": book,
            "book_name": BOOK_NAMES[book],
            "chapter": chapter,
            "verse": verse,
            "text": text,
            "text_sha256": sha256_text(text),
        }
    missing = sorted(required_keys() - set(index))
    if missing:
        raise ValueError(f"English weekly slice is missing {len(missing)} verses: {missing[:12]}")
    return index


def write_slice(language: str, manifest: dict[str, Any], index: dict[tuple[str, int, int], dict[str, Any]]) -> None:
    base = ROOT / "data" / "scripture" / "native" / language
    existing = json.loads((base / "verses.json").read_text(encoding="utf-8")) if (base / "verses.json").is_file() else []
    merged: dict[tuple[str, int, int], dict[str, Any]] = {}
    for item in existing:
        key = (str(item.get("book_id") or "").upper(), int(item.get("chapter") or 0), int(item.get("verse") or 0))
        merged[key] = item

    source_id = str(manifest["source_id"])
    source_url = str(manifest["source_url"])
    for key in sorted(required_keys()):
        item = index.get(key)
        if item is None or not str(item.get("text") or "").strip():
            raise ValueError(f"{language}: missing required native verse {key}")
        text = str(item["text"])
        merged[key] = {
            "automatic_diacritization_used": False,
            "book_id": key[0],
            "book_name": str(item.get("book_name") or key[0]),
            "chapter": key[1],
            "id": f"{key[0]}.{key[1]}.{key[2]}",
            "machine_translation_used": False,
            "source_id": source_id,
            "source_url": source_url,
            "text": text,
            "text_sha256": sha256_text(text),
            "verse": key[2],
        }

    verses = [merged[key] for key in sorted(merged)]
    (base / "verses.json").write_text(json.dumps(verses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = base / "manifest.json"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    persisted.update({
        "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
        "verse_count": len(verses),
        "books": sorted({item["book_id"] for item in verses}),
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "display_text_policy": "PRESERVE_SOURCE_UNICODE_CODEPOINTS_EXACTLY",
        "rolling_week_start": START_DATE,
        "rolling_week_required_verse_count": len(required_keys()),
        "rolling_week_slice_prepared_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": canonical_json_sha(verses),
    })
    if language == "en":
        persisted["retrieval_mirror"] = "https://github.com/midvash/bible-data"
        persisted["retrieval_mirror_commit"] = "1965127de5c3c103af3fdbc9288c1abec5f39994"
        persisted["retrieval_mirror_license_metadata"] = "versions/en/web/metadata.json"
    manifest_path.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    required = required_keys()
    if len(required) != 208:
        raise ValueError(f"unexpected required verse count: {len(required)}")

    for language in ("ar", "el"):
        manifest, index = load_public_domain_corpus(language)
        write_slice(language, manifest, index)

    english_index = build_english_index()
    english_manifest = {
        "source_id": "ebible_world_english_bible",
        "source_url": "https://ebible.org/find/details.php?id=engwebp",
    }
    write_slice("en", english_manifest, english_index)

    report = {
        "schema_version": 1,
        "rolling_week_start": START_DATE,
        "rolling_week_end": "2026-08-04",
        "required_unique_verses_per_language": len(required),
        "languages": {},
    }
    for language in ("ar", "en", "el"):
        base = ROOT / "data" / "scripture" / "native" / language
        verses = json.loads((base / "verses.json").read_text(encoding="utf-8"))
        index = {(v["book_id"], int(v["chapter"]), int(v["verse"])) for v in verses}
        report["languages"][language] = {
            "stored_verses": len(verses),
            "required_present": len(required & index),
            "missing": [f"{b}.{c}.{v}" for b, c, v in sorted(required - index)],
        }
    out = ROOT / "build" / "rolling-week" / "scripture-slice-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
