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
dots here print as 826x378 head dots = 70x32 mm at 300 dpi.
Field order is article name (headed, up to two lines) -> order code ->
manufacturer | part no. All rows sit left of x=290 so the QR block owns
the right edge. The QR carries a bare uuid (36 bytes -> version 4, 33
modules, 99 dots) and ends at x=395; if the field map ever switches it to
a resolve URL it grows to 123 dots and must move to x=270, as on
lot_label. order_code_2 is no longer laid out -- add it back as a third
column on the detail row if it is needed.
Rooted on BoughtItem itself (catalogue-rooted, printed by the
bought_item_delivered trigger via OrderItemDelivered.bought_item_id):
field names are bare BoughtItem result fields, no order_item/quantity
context.^FS

^FO6,6^GB401,177,2^FS

^FO296,10^BQN,2,3^FDQA,{bought_item_uuid}^FS

^FO16,14^A0N,11,11^FDARTICLE^FS
^FO16,26^A0N,18,18^FB264,2,4,L^FD{article_name}^FS

^FO16,76^A0N,11,11^FDORDER CODE^FS
^FO16,88^A0N,22,22^FB264,1,0,L^FD{order_code}^FS

^FO16,122^A0N,11,11^FDMANUFACTURER^FS
^FO150,122^A0N,11,11^FDPART NO.^FS
^FO16,134^A0N,14,14^FB126,1,0,L^FD{manufacturer}^FS
^FO150,134^A0N,14,14^FB136,1,0,L^FD{part_number}^FS

^FO6,163^A0N,13,13^FB401,1,0,C^FD{company_name}^FS

^XZ
