^XA
^CI28
^PW413
^LL189
^LH0,0
^MNY
^MMT
^PON
^PR4

^FX150 dpi authoring grid: printer #1 (ZT230) has FORMAT CONVERT 150->300
set at the front panel and cannot be changed (shared with another
service), so it doubles every coordinate in an incoming format. 413x189
dots here print as 826x378 head dots = 70x32 mm at 300 dpi. Sizes are
exactly half of the former 1:1 300 dpi layout -- halve/double when
comparing the two.
The QR carries a resolve URL (66-68 bytes), which needs a version 6
symbol: 41 modules x 3 dots = 123 dots wide. It sits at x=270 so even a
version 7 symbol (135 dots, payload up to 86 bytes) clears the frame at
x=407 -- do not move it right without rechecking that budget. Field
blocks left of it stop at x=264 so a version 7 symbol still has clear
space, hence the narrower FB widths here than on the uuid-QR labels.^FS

^FO6,6^GB401,177,2^FS

^FO270,10^BQN,2,3^FDQA,{po_uuid}^FS

^FO16,14^A0N,12,12^FDPART NO.^FS
^FO222,14^A0N,12,12^FDREV^FS
^FO16,28^A0N,26,26^FB195,1,0,L^FD{part_number}^FS
^FO222,28^A0N,26,26^FB45,1,0,L^FD{revision}^FS

^FO16,66^A0N,18,18^FB248,2,4,L^FD{article_name}^FS

^FO16,118^A0N,12,12^FDLOT^FS
^FO150,118^A0N,12,12^FDPROD. ORDER^FS
^FO16,134^A0N,17,17^FB126,1,0,L^FD{lot_number}^FS
^FO150,134^A0N,17,17^FB118,1,0,L^FD{production_order}^FS

^FO6,163^A0N,13,13^FB401,1,0,C^FD{company_name}^FS

^XZ
