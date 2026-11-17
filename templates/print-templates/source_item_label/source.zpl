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
Field order is dimension -> material -> type -> order code | manufacturer:
three stacked single-column rows, then a two-column detail row, all left
of x=290 so the QR block owns the right edge. The QR carries a bare uuid
(36 bytes -> version 4, 33 modules, 99 dots) and ends at x=395; if the
field map ever switches it to a resolve URL it grows to 123 dots and must
move to x=270, as on lot_label.
Rooted on SourceItem itself (catalogue-rooted, printed by the
source_item_delivered trigger via OrderItemDelivered.source_item_id):
field names are bare SourceItem result fields, no order_item/quantity
context -- dimension + material identify the stock, type_name stands in
for an article name.^FS

^FO6,6^GB401,177,2^FS

^FO296,10^BQN,2,3^FDQA,{source_item_uuid}^FS

^FO16,14^A0N,11,11^FDDIM.^FS
^FO16,26^A0N,22,22^FB264,1,0,L^FD{dimension}^FS

^FO16,56^A0N,11,11^FDMATERIAL^FS
^FO16,68^A0N,18,18^FB264,1,0,L^FD{material}^FS

^FO16,94^A0N,11,11^FDTYPE^FS
^FO16,106^A0N,18,18^FB264,1,0,L^FD{type_name}^FS

^FO16,132^A0N,11,11^FDORDER CODE^FS
^FO150,132^A0N,11,11^FDMANUFACTURER^FS
^FO16,144^A0N,14,14^FB126,1,0,L^FD{order_code}^FS
^FO150,144^A0N,14,14^FB136,1,0,L^FD{manufacturer}^FS

^FO6,163^A0N,13,13^FB401,1,0,C^FD{company_name}^FS

^XZ
