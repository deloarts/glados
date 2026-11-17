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
Drafted for the made_item_label classifier (catalogue-rooted, printed by
the made_item_completed trigger via LotCompleted.made_item_id -- fires
once per lot completion, not per delivered unit): part number + revision
identify the item exactly like production_order_label's header, but the
LOT/PROD. ORDER row is replaced with MATERIAL/BASE SIZE since a
catalogue root has no lot or production order context.^FS

^FO6,6^GB401,177,2^FS

^FO296,10^BQN,2,3^FDQA,{made_item_uuid}^FS

^FO16,14^A0N,12,12^FDPART NO.^FS
^FO222,14^A0N,12,12^FDREV^FS
^FO16,28^A0N,26,26^FB195,1,0,L^FD{part_number}^FS
^FO222,28^A0N,26,26^FB74,1,0,L^FD{revision}^FS

^FO16,66^A0N,18,18^FB264,2,4,L^FD{article_name}^FS

^FO16,118^A0N,11,11^FDMATERIAL^FS
^FO150,118^A0N,11,11^FDBASE SIZE^FS
^FO16,134^A0N,14,14^FB126,1,0,L^FD{material}^FS
^FO150,134^A0N,14,14^FB136,1,0,L^FD{base_size}^FS

^FO6,163^A0N,13,13^FB401,1,0,C^FD{company_name}^FS

^XZ
