# Third-party content notices — Orthodox Prayers 5.0.0

## Arabic Van Dyck Bible

Source identifier: `ebible_arabic_van_dyck`  
Distribution status: Public Domain  
Use in this repository: exact Arabic wording for registered daily Scripture passages.

## World English Bible

Source identifier: `ebible_world_english_bible`  
Distribution status: Public Domain  
Use in this repository: exact English wording for registered daily Scripture passages. “World English Bible” is a trademark; a modified text must not be presented under that name.

## 1904 Patriarchal Greek New Testament

Source identifier: `ebible_greek_byzantine_1904`  
Distribution status: Public Domain  
Use in this repository: exact Greek wording for registered daily Scripture passages.

## Divine Liturgy bilingual publication

Source identifiers: `metropolis_toronto_liturgy_en`, `metropolis_toronto_liturgy_el`  
Publication: Greek Orthodox Metropolis of Toronto bilingual Divine Liturgy PDF, 2017.  
Distribution basis: project-owner permission confirmation recorded in `canonical/native_language_sources.json`. Retain the external written authorization before public redistribution.

The Apache-2.0 license applies to project-owned software code, not automatically to third-party religious content.


## Hapgood Service Book 1922

Source: Isabel F. Hapgood, *Service Book of the Holy Orthodox-Catholic Apostolic Church*, revised edition, Association Press, 1922.  
Source record: Internet Archive/Open Library item `servicebookofhol0000orth_i9n7`.  
Use in 5.5.2: build-time extraction of English Orthodox service sections from the historical open edition; no machine translation.

## Ευχολόγιον τὸ Μέγα — Venice 1860

Source: University of Ioannina repository item `123456789/28576`, *Εὐχολόγιον τὸ Μέγα*, Venice 1860.  
License recorded by the repository: **Creative Commons Attribution 4.0 International (CC BY 4.0)**.  
Use in 5.5.2: build-time extraction of Greek service sections. The project must preserve attribution, the license link, and indicate that sections are programmatically extracted from the digitized source.  
License: `https://creativecommons.org/licenses/by/4.0/`

## Orthocal perpetual lectionary reference bootstrap (R63)

R63 can fetch scripture **reference metadata only** from the Orthocal Greek/Julian API at build time. The implementation is pinned for audit to `brianglass/orthocal-python` commit `393d5bb55d31bf14fa9c2a706e21c2f1bb48f400`, which is distributed under the MIT License. The app does not import Orthocal saint stories or use Orthocal saint names as Jerusalem/Jordan authority. Existing pinned Jerusalem/Jordan exact-date and fixed-feast rules take priority over this baseline.
