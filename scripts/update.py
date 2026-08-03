#!/usr/bin/env python3
"""Generate and validate daily data, then optionally sign it."""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from rolling_window_contract import resolve_day_count

ROOT = Path(__file__).resolve().parents[1]


PIPELINE_PATCH_LEVEL = "R18.4"

SOURCE_WINDOW_RESEARCH_SHA256 = "4f536834cd6de05d3830cf6a41a000e91bfc55d9ad1aa8b25367a34140d4ffaf"
SOURCE_WINDOW_RESEARCH_B85_ZLIB = (
    'c-pN!+ioMtb?^L&cF)6*vlK@=_Bu8b8jv-djO^LbK+?o;6rs1pZi>BXcGKO>k!US}_1@qZK@#LGkAAXY!-*HRv9_}d|AFRJ^SJ(!'
    'oKx3R)zu_5-UW6<*5%Zxs#E7)#XDcSKQD{>r%84{&R%%4MK#H@ueW^P|L#0VBQMOna9-upu!^IuH!AY7+!}>xoJC>bmHE6F#oj2N'
    '&cY%o^UNFPg;z~tuT0LeIP$V2i?^b1;awzIlwb5(t)od&dec0br?HpCFXF-r%kvV4+1bPLIQ6RB8%^@OjJ?n+;xJ0Gv#wVaVOFMq'
    '1r%2CW!3dyq$GP0XO$PW0E1~f&5N)~@~r3WRRX6NAg2gpv2_+_ae=b{nB%yJvk_EYB-O;r$Kzy_gsGfPep<%G3kIs}ws1B{R>egI'
    'Exs2Q^Acu1z5l(uhyZE16kV7><jr6}=n7+`In->y%1!bjsTMHi2s)HKZ&!3^&5C@Sq=;Y<d*|`2^2!)6#u=75Ofriv^g>5T8J-n!'
    'JjLmb!Ys?7IrPq|bm8T&ibWE|xbUqShItxkIJ0nc9-hTL+~3x?$fsTqjOW$7h=agOrn9_&)kNrg_N|sIE6xD7GM3**`D`ISPr`DN'
    'Ca3c2yFdo=b6(0%<z!wZsrt516;(2gIVMq9g`+eqOIQ;*Y#Ak^N>#_$Sk~e9t}5*^KtMfJ$Upu#&jj3ASRsD0-!u5iE2_l|NK2OQ'
    'WQ$hoV1NI}8?ZKQSQ%L1An5d9SM&5m-0t*{q_V0!e)FVtxO=eo?C20$vrhLtzZ@0GtSbFhGWN=<Xp0sd4|glcaMnFUrr+}5Kl!bf'
    'WI!`jd%J6N>a;kLMV_XBWxx+mFv>GH38PA4El>;Kj6vNTsKdJh<NYY?d&6&RKj1JpU1Q%Y9#wgv*0*i7M!a@qtB3J8$r7Z4u353K'
    '&j+tb^DqjE_$+}5EO=3t7t=6JejEqtwDAglxCk=57*4}!9AH%fn8J+D;po8{JllV=xBJ83+0M~pveIw@@+<+W_Sw42=}9gW%<?oD'
    'EqX|bertE<$?)mJorBdt<Pi_#SqUC&Klmp6^VYV2^JE_&tp>tQePA%7QuKa2+<9{J*zS%rPv%gv&yzSzs|ou!nioiL0>=LHqi4^L'
    'f`@wt>p<wW@LM~Fhr=U#;BYqMor)3rI}MYJeZccqaUd3CvcPg>pC23yp8`TVdryAoLP@SA`%>jVq@ri*4w4h6<Y`!(gBSpUDCcm5'
    'z0-v^pW(Ug%@&NS7I7MfAPrssK}CYY6EOm?W^n<6XIe7RgJ`BP3JNW^#$l3fjZ%;)L?+dwSFg46{AmB}oulEy;1SFz*nP5pID7~*'
    'J1XXJtM!k=r^AE2-Qdx1=kO?ad*|T$!vkahZAQZW&982L`|87+U)+4^-TdO!N3VYN>Zh+h_HKT8^P8LB-Tac3-Tdm+2T=MmEXO7v'
    'zWU_mcdvfNzkG1>zgXjUSAl~+{{i5B1zkUW^^phvd?FyjFwp<z*Sz(|uYP*->sKF0U~KXK`u=~Ho<W^nI6}FEY!IX_t{#XBkiM`m'
    '6D8Xuj0hHSVf9Z+wcc#!5Cn*$WSqcvzKyc`m!JRKd->t@XV;%!|Ka6NuK#rX#g||F-h*#nT>lUJ`<ZwB=j%^je)Q!RzxD9nKYB0U'
    'zy9?4|KR^W;kPe8|4(S}XDIj#p!^A%e)#eu`1@yG`EvpGFW3L~^53q12Ni#z1CwC@_+LJG`GM&38|d>Xd;@47Uw;lmBK)7c{C8;n'
    '2Y?TQL&Nu9zRwT>w0?j61)?Hw`|SFU(ClM`106nNNPfYl2ykEiD^AyEe5@74W6me>0JNDHU}6SDSUe8rY1Kyw)bX~ygMYb*0B*`Z'
    ';D1F7Vmf2uwTFO82Be3|O@Inf8+dGvJ2~*@)p+Y$K8O(P7hjH0xfrrPuw^xfD9d|M9MAAWTVNwmo>!wF%P-mtF<|e!x9BN_Zx35Y'
    'q1%HlC^BbhIEvfT1XV^*ezIt=-RZ$8!-E=DZQaCwV|%;5z3q2B|DSz1u257^uHi%%IOD#D+Q2bj(Zw}7L4g?-uy9fp5F)UT`Wizx'
    '1&MTQb~@oRK)7&nj|J!xRoH{21gdW*RXk<dEc*b`TeR$*#Z}wCh~x8g!Lai?sEHn*cp&wY5`=jbg0N%#y9{Bm4^R!qsf}Ga-q!{M'
    'UA-Y;0&MPZQ9|G0Wm2`reqF<kFJ~Y(;dEUo2urzKYzDyXpb+ZSa7&+~fYSkG7Z`k3O)JiT>7v%jn`&g#IKbc7I(u(u9g8&{a9AB<'
    'TUCEt4j6;47w%91t$a3h30e>4oV`)Y@OLZ+LiVOf34;U63M(-|?~4Cj_C4PL=Srb=SE6>evqapkByvl$U&kbTP+$e2&QF2LCUK+{'
    '9bBBCk!H_9k?Z48GLIDQjWBj_TL=igf}&25Tc0j8Q!q8{DWi#zpQj;nP>2EF2!@L>P1G-w41}F#5@J?B2L=>X!7;j88aq#sk@_D;'
    '#~cr*orc-j9H|%P-S*=QIRQ!?&yQ2zYLEYc9xz9AP+eBg8B!7w!^rnLJ!q252vHIg8I(G3vdgSRYvrg-<GA71;EDpU#W*pE1rFjD'
    'V9wo=lFZt#fT)@YiYsMxiW;~mifaQSt}a+KltC%j0z$u}Eo(%@><qEJ$hobmIvoiL%9`njvA}_WphZRID$s^<DdH4()>E`K9VF%!'
    '2X2~Eb32xwPH>jawoI!5z}39;`-IDiqE2^3FTT`CWOh`gtNJQiN3%KuimQGVJk(l(auPmx>zf7~TE41(m;}-*1UnMULAf{Jxau3='
    'EnVmI%2%5LaMkB!tFg`1aw$&o7%Y~G>1E}rLu{Q~_(z^x?C%ZgN0wC>r=!mQS(_TQDU9J{Ft)+l2^PlB3P?+FUhtDSQ#n!6cO}!^'
    ';7rQZV!pX#6fmG1bl+MQwo<2go=VP^Moc&HJ-_#Eo@4?c##_ra=p-XB8L?H{klbOmXmf*;G(hA8K*U)Xq)_NI_@s)eJO;wI*S0p('
    'sdtLK1jMy5U^pncut7|%>;peu8n|m_fE(acu7tj-%YC^k{9v>wzjSK0RHbdL<z-A1Y>Wz@%~DxIqpx7`v{wdKPC(;FQ7#@Uf=-s`'
    '<1Oh)66-8`*fNln8jSx+&IMXb@*<#~<MtX0#5Eb>B*NKHa1MGnUTvcoz1JEkCz5d`m&_e}x~SkB$!}3oaC6mrk4d|(r~G#yH5f<e'
    'dSE2Lz}y_;#}#3S9(~EH2uSoE=sGepB~U@6MCkKjB3~N>6vlm2=P5SJtt*ZRHA|MgNi|LV?%xE0`K~qvak~L;3A?(iL}P8)skK5%'
    '&<khibgCF8#@yTOj#EX|?U;Xo6N5o~Y>PO_fTfitSxl)P-3Y>Y+;@7E>%`)6FAJjKdYY?&CJDMe13h{#iS(i>HHS7(g}R*#2+?M;'
    'Ot(_OouEqMg0?klbPr}La{VzV@-(J>>^j{`Iiy9zi1xDUbT7WX0WR;LPRqL8yfCH-Ujt~==3PiTu3HX#x!Is{1fxkjItQhS;L1ya'
    'unOkYXrR1DUAj+WZrlvEd)vCaNX{lz8DIpE;zNo_TM+emHt@5!y2y)j79BfH<A_P4ESHDJE9bLWnkWPf`eo8k(60zdU@#Em5oj+!'
    '?A#%=hKgHyrG*!YmE04d4!%@<rnc~+Mt;g_!wQg^RV8y^@gg=7h{@A%bPn)H%{07Brt_(zW*k?eNiYgwGpH6-&1Y$RjIB6h=6cnM'
    'zyJ;yM`X=mEW!(D+9)Nuo_Y4f>L?eOSQBnS0;nblu$rfsU{j_px==RfrZ}ZoXXKM$ADqSQH@mo;_(yI*$9uzjlkmortK+rkl>@0R'
    'PHX`Gcj-<H$Y;Y(KzRU$SPL|x{b*FGXc&u)`Sy|tVy_gLS*9|>*AZ50r`$MD!y4FNWsjeA8MeHV=PZbeB4-->q^f568%JAwUz&KF'
    '!dX411Be+QY&HwB9p4$~6R-kE6sO?=<~9YT-#P?c`@DGfy!Hd{9{ei@*@A8D=qWSzb(zNT3}ImqmVp;7Fc?-;d@%{qit2h7VUeK&'
    'r5Da-=rtbuat4Dd@ku&g1z}@1!FP0wlu&tq2bL*jYivdB<*AtmJ{5+hiB2mBSH6v3z?Y)X=bVkG|Ei`#+neIhG||l}+RGMgmaD<4'
    'q&<n~GyMvroVJhRig|qNJ<J+oy*BZ__*&RO%Q2|tRomDLS;@3>5QnrcNMZv#ey8>93_8%D<rXegoH-pXR+Tx=Vm@Nb-O;aB=^BrT'
    '2<LFThW3ePU@oO`gMX=BOZ%SX<t%P;P1Pz*OliE{Le;1eRuo+y%396EF>2~Pxe{Y^5k(X?$zY6js?Y&d>q{nRQZC>x>wXLwz~Hv-'
    '#<2_OMrQ6^>}hzHHC)r$7HYlh%=+K}9k=tjbh}*Z-Y=)CReRdWH_MHZlrv!cffd+j)BUkR9vwlLnO}=I@U;~TRQmHx2f;eOV6*R_'
    'h|76eu>j^t%Xa6~T!t1Bn?#Tr-PN`DkP;ChG@@4vrG{9QMq36Qc<;)LwIENUK&Ol(V*;G%A$bAPBFZm=cUfv1>K?lDEQFO0i_rvG'
    '^^#MGKhMs={>Xen2W;h}yf)@mcedMtbnMIhx>Beu{klup5T_0U^ERTi%aTtz4#)K>!8$7vR^xJbyF_cVA-PtpYM-B@(+b(Ts@tuC'
    '8>X1u?tR;gJ<E<vuNDbaKBtfE-dk@u;H?q84I)_EaW-;Ia<@6gQInnx!2bq;`L_$sW&uh?QlqGJHrhxkx}>8UnjsD4;SFqtX!g{x'
    'ppNMkW}HJXc9C98WTvq1W8h&~IOS0ik=rO!1W1__x{e}2QKW`SjlNSXbXx{@JuCA0th7TYGFg-7C<?|VhG{e|l#vnzY97F~9r>MY'
    'Ro@{(%9d<KP}5gkV0+YOqRzNRho-J#(o3$S-`APjAc)K}<Xh`a8jBK_y6-=Ky1W1M(cZz^!-qb#ab$M3O^b{<rLY9GiU#8KnH^0_'
    'jWC~U>U~SR9ZMJ|+Ah7)q`5>}cAAtR?$3y9mVL!sai{$6KH1;>zHe($yk*O#54F~A@{rZa7i2AWk7XH^=!I+h&-R`^9X<^Fj&O6-'
    '2C=l4Iuc(StXZp7>*Yupnk5<DXi)Ht1(loJ_pThc@Wdh)HqIm?mVE`{$&D(ZG==V!P&kl4Yl+OLCYhW8n`y;KC{xQ$tENgCj7Pi2'
    'xf3i3XiALY*LqnRvv9~tNLURtV-D4^HC6|pHR@`78IHIPg8`*AN&?saEyc|832*|nED5{Gz}AfoSA<xm+Uy9f^)V#E9qp!*XfM~S'
    '0aa>iTD$2Xvh{bZwp+bw{utI%s^1y_qd(|wi7Ey~s-AKbavHL#Sk%&CZ0($WHAVVu(_UN}vQsgxA1wCQYD85llcKGLnx0J|Cp&dp'
    '&3f<c+)JD2xyuF?tIzChSgeb0v3>2VOF-oPwH$5gj`2-{v<J4bgX>^7Q6`;jUB0%YV1w%L;3kqnF6nDY3YfPzRs#oLf9+|MfUmwe'
    '=A4Abt{0iH>4t>cuWGVQVo_;RtEOaKUo_?vC1W_HC8iLY6Z(5NA@a_hx@u=%v$GMFI*z^G{Y}*^bEewT*T)FGKdo9mBNgASqt~)?'
    '6ze>kv$BqxoQ(cPj*lfdP$XH$uiJdsx-P{<Ga!<RltnRaFJ6SS1%f3ZHFq}=6}nPq75bf8cIifoYOqYqzbEK+Fu?V|O}&%|lzkDr'
    '{rt(%UU0bo{9t$Jn+M)S5Vrxn^Ze-X{=weS4=uQ^+1&>2?!o@yVX*snNX>@kQ%iyDJv|y8Jl%Q1u3jDPJR15fht0vPZ**}+@hB-('
    '3dpKN>4qr%rdG8!)m?BIiPwx=8rA2Q5$nAhO>Rp!!Z0qs&*(U&rc2!xcU(=Qy?F~wJ*utH*sOCIusdHuf3xg0sRW8r%SEn2P*jCv'
    '{FY>IbFL^BA6*pMqb>Qlvl7oEh6==u0q*8P9>U#KG}&9TcuZUHudv&a__K&stnQQyn%p~epr%H(<}wHmpjcX%Bm5$ZR=2mE6gEwp'
    'H5S>Jl{TMl)g`Z9o@1G|&+@dD6YWIDa-8=U#AM8kDUbD1o~U)lQ8e>lG$OBMQ8c7X)i6~!-qBhs2-46MDb@|C+8uJD41#ZS{f-8J'
    '=*<8p;U{Ag60_HM>gxWZM|-<_@PYIB;Gc#Edyn?eyX5&#Fzr|t1ibyhaCiUUAvN+`w~o=et>ftmXPOsx9GTcw1W4?MP_le=*^`fE'
    '-VTi~;bfNH>AccML#%rd<CWu54(J<{ra|bX_pNn!b}&2~K0R`2OAQM`X4*8y)BT3!zTFzxX(7(5vvLLCBi@>=3Si3Pd8$23<1kGz'
    'kHr@RTgE9IPkxQ27UWA45R+#MmFuG#n=x0#JP0h4gKr3E?1IJI6!IJK(8-q7VisFsL-#hr=GfHXe^3mTfVvd~ia3M8-t92KhFN4a'
    '0z<`Yv+7KY@pgTV0N_;c)ud*h35Xd%+No#^yVTsnn&U;01DlmwB?%>fzxhSXv~QlR^e8kAhIMuslr7K$Vnu7RV|+OSbQ64D1cdEr'
    '5=9u~Zjm4dKQ#O<mcx%mRc6lW)!ht5K|=hK%r36dDN`uW_wiB1e6qKD<U2A+q5XDmyQP%aCKX!YqL6ow{p|U7pX?nzCZoGGaSMZQ'
    'KX9U;RqfXw-=VHsgMaIr4o0{dXoJG-0RDFmS`C?IDvI0pR%IFc5))`AKQ`q_=`S?fX+8yQv;f5-zJNbJnkNNwk}(2zWsNBn*K~Fp'
    'DF&n;CsA~xu@9@VgDfYc3Jtkrisf*lF)V&b%dD5eG++`8FP%9gncKCgZ@xI>zI+;_mM^rVO91#_M5s1Higo=yn&`zqJ8Pxfu<&*S'
    '=^PMgH;Qbtlv;_tYPKGkz|odsU|r5}Yu+@-SAuO7M<A`Lwk$Q$BvssxG~{I+D`QLN-9<nzRa-dz8;n?dmFh*3&l`-~b=Q<c=iqd~'
    '!v$9x#0&a$UzCKyng3{ldDjgIOmaG3MZf}|GZ|QuVEt&fTI2<Kt%;%Jiirz^pum!V7A6@mF4J(X3(Y$60luzf4`JtPx`rbCniD<k'
    'jwL?GhA!&?9*J@8TURcyT*Ba67#W%|SrsE9g%|o?fC`MaG(^TYW@-CN9^KU|lVr8io1^)LcQ~v>^Dc&$=A{H_rlgx0>-zkfyGo}!'
    'NzNv|<)e~QmgJKz0zRP3Ac^9$B8=!FFyXKEP0mhzQ8gHy78T7nnOmShODY<Wm0K6`<LB)))83i`Ya+3Sqs;g#|F|l%hktOiP^VOh'
    'R6Sc)))6Nz-CD24O5idNOYKE1HKaa-?4vf**{30MNG!g3;~|THi1CtflwV}+RT-cv!xk@im=1scj<+M<w-QzcUcIkBYDKjidcn}&'
    '@_xYHl<Rx%TnQwO@3I^W7IVIPvV6z;>nHz3YXNmtXTf?HE=mKEdY#76cps<)3=X9V_Pu-e2oCcptj^-@2>=ld0LHz07LdoN5_()E'
    '^rT9NC@`O=1m;v6@1AseXekw7jJ(sZK>m9$C$Nm*kJO^y!%Id|FMiMafso?xameJf_ny&zYimpX-zWcwHg&ltaprfhiQAp+zVqyk'
    '0ZV3m9qV^&PL`f7)a$1UwSs;3q~Cim#wy<e%N`Hn&84yei^hQH8m^u2a^Ir;WbC<;keR|l{j+>-!e4jHULUw~$2;Uy%v(bdb@Dlv'
    '%m8miESi^3lF~bRWfY@BvhB+yvse=@Cms#i&EP~>=?a0iMQh0;p<Txn=QPmu&D%r%zhvUM1J+8WnWH0#-#6En>EvZH^>$}(r#PEq'
    'Naq==5&1a0Suc#DAQbg&e`|~Jfi3=gn>t(rmWjNo8>8GVzN{G!*iA$6oY(;ITGJB)4Y~t+MDV^e)$WtW16P6(m*D_V$aMDsC|5Zs'
    '%AhgFt9yz|j9XDs$Qj@T&6Ry5S!@+~UTxeftg3J{aiiGvCUH6&_&cl(a}26y47E8g-s<CCMfs+ym>!J8A3I=Uvp+aGUf*tsi@XJY'
    'S)_`47{AvBJ2vZS3D8lIHU6^bp#It@@4{XV6O92QOvRt*=O9HBsL)M}R}XZjE}E?LeKzA6IMz-)`bM66>yRj$0hhcTssYPqO2r$Y'
    '<RODnc9u=V2~ma*)1&dVgPL)pVOVa~(}m16tG^aP;tRT&^(Y2Uu@u*w%{ZVaHN3JwX|P31MKzQKHicu#-A)X4Y8Y6^R>?R_t`NZF'
    '8ClmmAvP#Bv=De4NA^?(@+H@s8QeM){8TkPUUOB_bT{&D>Pf$#c3URJ=oKATZU9xnTqf~}jv~D7CF`ptGcx(+$%rlh2{7Fz!0Y#z'
    '0GoiyGDnZQzU)+c!H+mwRzBp%{c_9}T=j}y%N0XJiiCA&n>*4GH@WehJ+MNyIhKSDC<rOrH@yngF(tjer_8oi(_z0U@JX&|*KhRG'
    '|03%mKmAW!<*t<r`7&TkO?;`hA{XL$OL{}T)>>T|2C``zlp$+CEPUN{1IW7VTnAt^2>45!2=7f7JnK4j9iG*I!25;^Uc>$OZbNog'
    'jdX+(wBq#h7sA`5oZjxf1G;-OpRtEEVxCW{8Ppqi;@{9u`AN$3E+&}bdLGB@d2o5eWOa{t*8#RT{QTU@s}}m7liE{8W*~BXwl)5D'
    '9xsgdZ`=t_PES~OO{ZEWa@~#ZfZ@v3HsLz%9?3lC*8x|*hvbH45)<2@V^}?0b>saj7n5VH^$TLeL}?Hg$Mv;3QQSwopl@b8iO8*)'
    'yQHus$r7z~%&0lj!&W}n0y=^-s1mu-Kvs9Nx(F@GkuX9euRO>6E6pZH24h*CA`N19|Ltcx2ScW&4qUG>DQ$RgC9=s3Yu7et$-6VE'
    'ecce2w(fvgxw4&M0du3*Y@iKc>n_<iotG14Hqj+A9qa4!(6r`)nSUrxRA)3i`eZ>xvCzQlZRPXq_eDtPK7VZfzWLC+177{HGGnk+'
    '&y_XKwwA%VPR(mf%Cr$}egUnu(Hoss;wf`0aBsRR@FLWru6veZzfa+GowJKB^>^E-mMU^`k9ElOgk|D32E+x5qP2?08vq&xQ;~Rq'
    '9J%8oJalU#@ysht28Yqt#m|?{VKxc6^U(Sxk!&_miPeVVHN?ZskormpBusC;@kc`DC1^m?5MR3$0r5BKD;DxsYQz&-Q0;g`%hyIa'
    'd&(2OG{oJd#}?zl4f?+}@Y&lqO#yt_N(6z~XHx&}yhxZXmIx=mVP^C5XtZ%<2gsYchW%;ObzUPUK=_mEkztaQAhy*C3yWhBhzB{5'
    '<%=TwD$Nv*Q=-B`yg7{9b{^$5q~3H|?J;#0@9hU9NhuqSrql}jEsZi9zs@ur=XAr-g$Pz8h=VFeG|lbY6d)7X4d7H_=?1`-^+%Mr'
    '6S~i(hIxcaae4$C71qZ;`qy20({nHs+v3NDxcb0zDTDl+IANoZzt2y87lyqRSz`!GBG-k?vb*_p4FFSOp&9$diD*8ZsUKnhWU>;a'
    'U|5clWWdiGyP1(yg9rF@8v3a<ioFZWG2_2d!GF7}_FEMcwN0D1%?XHO-kXB)LqRkI+&WEQ_3!0~pL^PLJNR#0_3&pj9!S-oOTg({'
    'K};{>ZeT501pf7Fj;jR5W_)ZzPATHF_|s52<SBmMtH%r2hV<CN#clONBfUv{86{_NX~+x;j{U3<reYE0v-X2RR#%5CRPml#-HGeo'
    'BL4xJXsx%Iv_1Bfzdfj-$&%c~KA9#wkl1C{o5s^q{&KYT#tFEMzZ+tu4x1_|2S^`VW+UO_gx){M-xE<>ss6G&@9&rsWz`L@%o{m-'
    'dX!^@!3pK~?swJA%)TZlq)`)`TTrk`0(!eCPar%^?9XOAt%+wSRu{<d#>(HqTF0a1(~ufs(|f(N37;Q-l9NoEzTm4_P)*~fqOMjc'
    '8!*X;ElfdKCp>Q2+tz$AJUG}t5H@{1Y<<PxE$N#S^<Ts>AnqORKMk0HGJMElM%*r!N}2>^IT~C*_P@{d=z(Kr1Z47iJKFak7%p`<'
    'jD77!a3wVux(v>nDGD5O_OT=GzhZb7wklxPV}gJwRY8Ek-XIY7dU@ox_5WcikRk'
)


def ensure_source_window_research_module(root: Path = ROOT) -> Path:
    """Restore the automated source-research module if a branch lost or corrupted it."""
    target = root / "scripts/source_window_research.py"
    expected = bytes.fromhex(SOURCE_WINDOW_RESEARCH_SHA256)
    current = target.read_bytes() if target.is_file() else b""
    current_digest = hashlib.sha256(current).digest() if current else b""
    if current_digest == expected and b"AUTOMATED_FAIL_CLOSED" in current:
        return target

    try:
        restored = zlib.decompress(base64.b85decode("".join(SOURCE_WINDOW_RESEARCH_B85_ZLIB).encode("ascii")))
    except Exception as error:
        raise SystemExit(f"PIPELINE_SELF_REPAIR_FAILED decode={error}") from error
    restored_digest = hashlib.sha256(restored).hexdigest()
    if restored_digest != SOURCE_WINDOW_RESEARCH_SHA256 or b"AUTOMATED_FAIL_CLOSED" not in restored:
        raise SystemExit("PIPELINE_SELF_REPAIR_FAILED embedded source checksum or marker mismatch")

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=target.parent, prefix=target.name + ".", suffix=".tmp") as handle:
        handle.write(restored)
        temporary = Path(handle.name)
    temporary.chmod(0o755)
    temporary.replace(target)
    print(
        f"PIPELINE_SELF_REPAIR_OK restored={target.relative_to(root)} sha256={restored_digest}",
        flush=True,
    )
    return target

def verify_pipeline_patch() -> None:
    """Repair the critical research module, then verify the complete pipeline contract."""
    ensure_source_window_research_module()
    integrity_path = ROOT / "scripts/orthodox_integrity.py"
    schedule_path = ROOT / "scripts/update_liturgical_data.py"
    integrity_text = integrity_path.read_text(encoding="utf-8")
    schedule_text = schedule_path.read_text(encoding="utf-8")
    fasting_validator_path = ROOT / "scripts/validate_fasting_guidance.py"
    home_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
    settings_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"
    sources_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SourcesScreen.java"
    coordinator_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java"
    repository_path = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"
    workflow_path = ROOT / ".github/workflows/update.yml"
    required = {
        str(integrity_path.relative_to(ROOT)): '"Mt.": "Matthew"',
        str(schedule_path.relative_to(ROOT)): 'data["fasting_guidance_version"] = 1',
        str(fasting_validator_path.relative_to(ROOT)): "documented_interval",
        # R32 intentionally removed the obsolete ThemePalette dependency from HomeScreen.
        # Verify the current owner-facing home contract instead of the retired R15 marker.
        str(home_path.relative_to(ROOT)): "R32_OWNER_UI_REFINEMENT",
        str(settings_path.relative_to(ROOT)): "host.navigate(\"sources\", null)",
        str(sources_path.relative_to(ROOT)): "ui_sources_and_references_1a2c2926",
        str(coordinator_path.relative_to(ROOT)): "MORNING_REFRESH_HOUR = 4",
        str(repository_path.relative_to(ROOT)): "downloadManifestSelection",
        str(workflow_path.relative_to(ROOT)): "ORTHODOX_ENABLE_LIVE_SOURCE_FETCH",
        "canonical/source_connectors.json": "local_authority_source_id",
        "scripts/source_connectors.py": "dcs_reference_after_heading",
        "scripts/source_window_research.py": "AUTOMATED_FAIL_CLOSED",
        "canonical/source_comparison_policy.json": "human_review_required",
    }
    actual: dict[str, str] = {}
    missing_files: list[str] = []
    missing_markers: list[str] = []
    for name, marker in required.items():
        path = ROOT / name
        if not path.is_file():
            actual[name] = ""
            missing_files.append(name)
            continue
        text = path.read_text(encoding="utf-8")
        actual[name] = text
        if marker not in text:
            missing_markers.append(f"{name}:{marker}")
    if missing_files or missing_markers:
        details = []
        if missing_files:
            details.append("missing_files=" + ",".join(missing_files))
        if missing_markers:
            details.append("missing_markers=" + ",".join(missing_markers))
        raise SystemExit(
            f"PIPELINE_PATCH_MISMATCH expected={PIPELINE_PATCH_LEVEL} " + " ".join(details) + "; "
            "run python scripts/update.py --repair-pipeline-only or extract the release ZIP into the repository root"
        )
    print(f"PIPELINE_PATCH_OK level={PIPELINE_PATCH_LEVEL}", flush=True)


def run(*args: str, check: bool = True) -> int:
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode


def remove_stale_daily_signatures(date_iso: str) -> None:
    """Unsigned generation must never leave signatures from an older payload."""
    for path in (
        ROOT / "data/calendar/today.json.sig",
        ROOT / "app/src/main/assets/data/today.json.sig",
        ROOT / f"data/calendar/{date_iso}.json.sig",
    ):
        path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repair-pipeline-only",
        action="store_true",
        help="Restore and verify critical update-pipeline files, then exit.",
    )
    parser.add_argument("--date")
    parser.add_argument(
        "--window-days",
        type=int,
        default=None,
        help="Signed moving-horizon length (exactly 9 days; defaults to ORTHODOX_ROLLING_WINDOW_DAYS or 9).",
    )
    signing = parser.add_mutually_exclusive_group(required=False)
    signing.add_argument("--private-key", type=Path)
    signing.add_argument(
        "--unsigned",
        action="store_true",
        help="Generate and validate only; remove stale signatures and sign in a later protected step.",
    )
    parser.add_argument(
        "--skip-scripture-preparation",
        action="store_true",
        help="Skip the exact native Scripture horizon step because the caller already completed it.",
    )
    args = parser.parse_args()
    if args.repair_pipeline_only:
        ensure_source_window_research_module()
        verify_pipeline_patch()
        print(f"PIPELINE_REPAIR_ONLY_OK level={PIPELINE_PATCH_LEVEL}", flush=True)
        return
    if not args.date:
        parser.error("--date is required unless --repair-pipeline-only is used")
    if (args.private_key is None) == (not args.unsigned):
        parser.error("exactly one of --private-key or --unsigned is required")
    try:
        window_days = resolve_day_count(args.window_days)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    verify_pipeline_patch()
    os.environ["ORTHODOX_DATE"] = args.date
    live_sources = os.getenv("ORTHODOX_ENABLE_LIVE_SOURCE_FETCH", "").strip() == "1"
    source_mode = [] if live_sources else ["--offline"]
    run("scripts/collect_source_health.py", "--date", args.date, *source_mode)
    run("scripts/collect_local_commemorations.py", "--start-date", args.date, "--days", str(window_days), *source_mode)
    run("scripts/build_church_directory.py", "--date", args.date, *source_mode)
    run("scripts/build_public_source_registry.py")
    run("scripts/validate_public_source_registry.py")

    # Keep the manual CLI and GitHub workflow behavior identical. The workflow
    # may pre-run this step for clearer logs and then pass --skip-scripture-preparation.
    if not args.skip_scripture_preparation:
        run(
            "scripts/prepare_rolling_week_scripture_slice.py",
            "--start-date",
            args.date,
            "--days",
            str(window_days),
        )

    if args.private_key is not None and not args.private_key.is_file():
        raise SystemExit("data-signing private key is missing")

    run("scripts/update_liturgical_data.py")
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    integrity = run("scripts/orthodox_integrity.py", "--apply", check=False)
    mode = "full" if integrity == 0 else "partial"
    run("scripts/fill_daily_from_native_corpora.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Services are initially composed before native Scripture is resolved.
    # Recompose them now so the Divine Liturgy uses the same verified text as
    # the Readings screen, then re-apply lane metadata to the new overlays.
    run("scripts/rebuild_daily_services.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Recalculate service completeness after the final native-language overlays are composed.
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{args.date}.json")
    # Never publish a new day with blank Epistle/Gospel cards. A transient
    # Scripture-source failure keeps the last signed good day instead.
    run("scripts/validate_daily_native_content.py", "data/calendar/today.json", "--require-complete")
    run("scripts/mark_partial_daily.py", "--date", args.date, "--mode", mode)

    # This is the final fail-closed local-jurisdiction gate. It is deliberately
    # executed before the generated payload is copied into the Android assets
    # or signed, so manual/non-workflow update paths cannot bypass Jordan's
    # date, Epistle, Gospel, and Divine Liturgy contract.
    run(
        "scripts/validate_jordan_liturgical_contract.py",
        "data/calendar/today.json",
        "--expected-date",
        args.date,
        "--require-jordan-authority",
        "--require-complete-liturgy",
    )

    # Publish one fail-closed moving package: the fully validated current day
    # plus a configurable horizon of independently generated future days. The
    # language-lane step later strips this package to Arabic, English, or Greek
    # before signing, so Android downloads only the active native-language lane.
    run(
        "scripts/build_rolling_week.py",
        "--start-date",
        args.date,
        "--days",
        str(window_days),
        *source_mode,
    )
    run(
        "scripts/validate_rolling_week.py",
        "data/calendar/today.json",
        "--expected-start",
        args.date,
    )
    # Automated source research replaces manual review. It compares the complete
    # nine-day package against local authority evidence, the internal calendar,
    # and date-addressable official cross-checks, then attaches a signed decision.
    run(
        "scripts/source_window_research.py",
        "--start-date",
        args.date,
        "--days",
        str(window_days),
        "--attach",
        *source_mode,
    )
    run(
        "scripts/validate_source_comparison.py",
        "--start-date",
        args.date,
        "--days",
        str(window_days),
    )
    run(
        "scripts/validate_rolling_week.py",
        "data/calendar/today.json",
        "--expected-start",
        args.date,
    )

    asset = ROOT / "app/src/main/assets/data/today.json"
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data/calendar/today.json", asset)
    run("scripts/build_search_index.py")

    if mode == "full":
        for command in (
            ("scripts/validate_native_source_contract.py",),
            ("scripts/validate_daily_native_content.py",),
            ("scripts/validate_official_sources.py",),
            ("scripts/validate_no_placeholder_guidance.py",),
            ("scripts/validate_json_schema.py",),
            ("scripts/validate_liturgical_schedule.py", "data/calendar/today.json"),
            ("scripts/validate_fasting_guidance.py", "data/calendar/today.json"),
            ("scripts/quality_check.py", "data/calendar/today.json"),
            ("scripts/validate_embedded_app_data.py",),
            ("scripts/validate_static_prayer_sources.py",),
            ("scripts/validate_native_language_packs.py",),
            ("scripts/validate_public_source_registry.py",),
            ("scripts/validate_source_intelligence.py", "data/calendar/today.json", "--expected-date", args.date),
            ("scripts/validate_reader_services.py",),
            ("scripts/validate_full_liturgy_services.py", "data/calendar/today.json"),
            ("scripts/validate_daily_ui_localizations.py", "data/calendar/today.json"),
            ("scripts/validate_scripture_translations.py", "data/calendar/today.json"),
        ):
            run(*command)
    else:
        run("scripts/validate_partial_daily.py", "--expected-date", args.date)
        run("scripts/validate_static_prayer_sources.py")
        run("scripts/validate_reader_services.py")
        run("scripts/validate_full_liturgy_services.py")
        run("scripts/validate_public_source_registry.py")
        run("scripts/validate_source_intelligence.py", "data/calendar/today.json", "--expected-date", args.date)

    # data/calendar is a publication alias directory, not a historical archive.
    # Keep only today.json and the current dated fallback so rsync --delete also
    # removes stale aliases from verified-data before the consistency gate runs.
    # Historical language-lane payloads remain under data/daily/YYYY-MM-DD/.
    run("scripts/clean_legacy_calendar_snapshots.py")

    if args.unsigned:
        remove_stale_daily_signatures(args.date)
        print(f"DAILY_UPDATE_UNSIGNED_OK date={args.date} mode={mode} window_days={window_days}")
        return

    # No human review is required for routine publication. The protected signer
    # approves only a machine-verifiable, fail-closed source comparison.
    run(
        "scripts/validate_automated_religious_evidence.py",
        "--start-date",
        args.date,
        "--days",
        str(window_days),
        "--daily",
        "data/calendar/today.json",
    )
    run("scripts/sign_daily_data.py", "--private-key", str(args.private_key))
    run("scripts/verify_data_signature.py")
    print(f"DAILY_UPDATE_OK date={args.date} mode={mode} window_days={window_days}")


if __name__ == "__main__":
    main()
