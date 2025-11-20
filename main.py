# main.py
# type: ignore

import flet as ft
from supabase import create_client, Client
from datetime import datetime
import threading
import requests
import re
import os

# ==============================================================================
# 1. الإعدادات وقائمة المنتجات (تبقى كما هي)
# ==============================================================================

# إعدادات Supabase (نفس الإعدادات القديمة)
SUPABASE_URL = "https://dtklpugpwejrjnkxdkhh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0a2xwdWdwd2Vqcmpua3hka2hoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwOTg0OTEsImV4cCI6MjA3NzY3NDQ5MX0.ZUPzyPWPzZBabr3HjBtg08Fccm6Kq_hRd-9V8muk57Y"

# قائمة المنتجات (نفس القائمة القديمة)
PRODUCTS_LIST = [
    {"name": "حبوب لقاح", "type": "gram", "price_per_gram": 10},
    {"name": "غذاء ملكات بلدي", "type": "gram", "price_per_gram": 35},
    {"name": "بروبوليس تركيز عالي", "type": "gram", "price_per_gram": 15},
    {"name": "طلع نخيل بيور", "type": "gram", "price_per_gram": 15},
    {"name": "عسل موالح نقي", "type": "unit", "sizes": {"920جم": 350, "450جم": 180}},
    {"name": "عسل برسيم فاتح", "type": "unit", "sizes": {"920جم": 300, "450جم": 160}},
    {"name": "عسل برسيم غامق", "type": "unit", "sizes": {"920جم": 350, "450جم": 180}},
    {"name": "عسل شمر نقي", "type": "unit", "sizes": {"920جم": 600, "450جم": 320}},
    {"name": "عسل سدر مصري فاخر", "type": "unit", "sizes": {"920جم": 1200, "450جم": 650}},
    {"name": "شمع العسل الطبيعي", "type": "unit", "sizes": {"500جم": 175, "250جم": 90}},
    {"name": "تمر الوادي نص جاف", "type": "unit", "sizes": {"1 كجم": 110}},
    {"name": "زيتون أخضر سليم", "type": "unit", "sizes": {"370جم": 65, "720جم": 110}},
    {"name": "زيتون مخلي", "type": "unit", "sizes": {"370جم": 75, "720جم": 120}},
    {"name": "زيتون شرائح", "type": "unit", "sizes": {"370جم": 75, "720جم": 120}},
    {"name": "زيتون دولسي (الطعم الريفي)", "type": "unit", "sizes": {"370جم": 65, "720جم": 110}},
    {"name": "زيتون كلاماتا (يوناني فاخر)", "type": "unit", "sizes": {"370جم": 100, "720جم": 165}},
    {"name": "فلفل هلابينو طبيعي", "type": "unit", "sizes": {"370جم": 35, "720جم": 55}},
    {"name": "زيت زيتون بكر ممتاز 500 مل", "type": "unit", "sizes": {"500 مل": 475}},
]

# ==============================================================================
# 2. كلاس تبويب الفاتورة (تم تحويله بالكامل إلى Flet)
# ==============================================================================

class InvoiceTab:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.TELEGRAM_BOT_TOKEN = "8106133230:AAHNkZ85E5iaIuFwtSJoOlFwf6IKk6t_Ctk"
        self.TELEGRAM_CHAT_ID = "-5094019377"
        
        # --- إدارة الحالة (State Management) ---
        self.current_order_items = []
        self.current_total_price = 0.0
        self.current_shipping_cost = 0.0
        self.customer_list = []
        self.selected_customer_id = None
        self.shipping_rates = {}
        self.selected_cart_row = None # سيحتوي على كائن الصف المحدد

        # --- قواميس المنتجات (تبقى كما هي) ---
        self.PRODUCTS_DICT = {item['name']: item for item in PRODUCTS_LIST}
        self.PRODUCT_NAMES = sorted([item['name'] for item in PRODUCTS_LIST])
        
        # --- تهيئة عناصر الواجهة ---
        self._initialize_controls()

        # --- تحميل البيانات الأولية ---
        self.load_shipping_rates()
        self.refresh_customers_dropdown()
        threading.Thread(target=self.update_invoice_id_label, daemon=True).start()

    def _initialize_controls(self):
        # --- عناصر واجهة Flet ---
        self.customer_combobox = ft.Dropdown(
            label="اختر عميل حالي أو ابحث", options=[ft.dropdown.Option("عميل جديد...")], on_change=self.on_invoice_customer_select,
        )
        self.customer_name_entry = ft.TextField(label="اسم العميل *", text_align=ft.TextAlign.RIGHT)
        self.customer_phone_entry = ft.TextField(label="رقم الهاتف", text_align=ft.TextAlign.RIGHT, keyboard_type=ft.KeyboardType.PHONE)
        self.customer_address_entry = ft.TextField(label="العنوان", text_align=ft.TextAlign.RIGHT)
        self.customer_notes_entry = ft.TextField(label="ملاحظات (اختياري)", text_align=ft.TextAlign.RIGHT)

        self.shipping_region_combo = ft.Dropdown(
            label="منطقة الشحن", options=[ft.dropdown.Option("اختر المنطقة...")], on_change=self.on_shipping_region_select,
        )
        self.shipping_cost_label = ft.Text("0.00 ج", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700)
        
        self.product_combobox = ft.Dropdown(
            label="اختر منتج...", options=[ft.dropdown.Option(name) for name in self.PRODUCT_NAMES], on_change=self.on_product_select,
        )
        self.qty_container = ft.Row(alignment=ft.MainAxisAlignment.CENTER, wrap=True)
        self.add_item_button = ft.ElevatedButton("➕ إضافة للسلة", on_click=self.add_item)

        self.cart_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("الصنف")),
                ft.DataColumn(ft.Text("تفاصيل")),
                ft.DataColumn(ft.Text("السعر"), numeric=True),
            ],
            rows=[]
        )
        self.remove_item_button = ft.ElevatedButton("🗑️ حذف المحدد", on_click=self.remove_item, disabled=True, bgcolor=ft.Colors.RED_200)

        self.discount_entry = ft.TextField(label="الخصم", width=100, text_align=ft.TextAlign.CENTER, on_change=self.update_totals_display, value="0")
        self.discount_type = ft.SegmentedButton(
            segments=[ft.Segment(value="مبلغ", label=ft.Text("مبلغ")), ft.Segment(value="%", label=ft.Text("%"))],
            on_change=self.update_totals_display,
            selected={"مبلغ"}
        )
        self.breakdown_label = ft.Text("...", size=12, color=ft.Colors.GREY_600)
        self.final_total_label = ft.Text("0.00 ج", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)
        self.next_invoice_id_label = ft.Text("#...", color=ft.Colors.ORANGE, weight=ft.FontWeight.BOLD)
        
        self.save_btn = ft.ElevatedButton("💾 حفظ وإرسال", icon=ft.Icons.SAVE, on_click=self.save_invoice_thread, height=50, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
        self.receipt_btn = ft.ElevatedButton("🧾 عرض الفاتورة", icon=ft.Icons.RECEIPT, on_click=self.generate_receipt_thread, height=50)
        self.clear_btn = ft.ElevatedButton("مسح", icon=ft.Icons.CLEAR, on_click=self.clear_order_event, height=50, bgcolor=ft.Colors.RED_200)
        
        self.status_bar = ft.SnackBar(content=ft.Text(""), bgcolor=ft.Colors.BLUE)


    def build(self):
        # ... (باقي دالة build تبقى كما هي بدون تغيير)
        left_column = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.PERSON), ft.Text("👤 بيانات العميل", size=18, weight=ft.FontWeight.BOLD)]),
                        self.customer_combobox,
                        self.customer_name_entry,
                        self.customer_phone_entry,
                        self.customer_address_entry,
                        self.customer_notes_entry,
                    ]),
                    padding=15, border_radius=10, border=ft.border.all(1, ft.Colors.GREY_300)
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Icon(ft.Icons.LOCAL_SHIPPING), ft.Text("🚚 الشحن", size=18, weight=ft.FontWeight.BOLD)]),
                        self.shipping_region_combo,
                        ft.Row([ft.Text("تكلفة الشحن:"), self.shipping_cost_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ]),
                    margin=ft.margin.only(top=10), padding=15, border_radius=10, border=ft.border.all(1, ft.Colors.GREY_300)
                )
            ],
            scroll=ft.ScrollMode.AUTO, expand=True
        )

        right_column = ft.Column(
            controls=[
                 ft.Row([
                    ft.Icon(ft.Icons.SHOPPING_CART), 
                    ft.Text("🛒 المنتجات", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row([ft.Text("فاتورة رقم: "), self.next_invoice_id_label])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.product_combobox,
                self.qty_container,
                ft.Container(content=self.add_item_button, alignment=ft.alignment.center, padding=10),
                ft.Divider(),
                ft.Text("سلة المشتريات", weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Column([self.cart_table, self.remove_item_button], horizontal_alignment=ft.CrossAxisAlignment.CENTER), 
                    expand=True,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    padding=5
                ),
                ft.Divider(),
                 ft.Container(
                    content=ft.Column([
                        ft.Row([ft.Text("الخصم:"), self.discount_entry, self.discount_type], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        self.breakdown_label,
                        ft.Divider(),
                        ft.Row([ft.Text("الإجمالي النهائي:", size=16), self.final_total_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ]),
                    padding=15, bgcolor=ft.Colors.BLUE_GREY_50, border_radius=10
                )
            ],
            expand=True
        )

        main_layout = ft.Column(
            controls=[
                ft.ResponsiveRow(
                    [
                        ft.Container(content=left_column, padding=10, col={"md": 4}),
                        ft.Container(content=right_column, padding=10, col={"md": 8}),
                    ],
                ),
                ft.Container(
                    content=ft.Row([self.save_btn, self.receipt_btn, self.clear_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    padding=10,
                )
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO
        )
        return main_layout
    
    def on_product_select(self, e):
        choice = self.product_combobox.value
        prod = self.PRODUCTS_DICT.get(choice)
        self.qty_container.controls.clear()
        if not prod:
            self.qty_container.update()
            return
        
        if prod['type'] == 'gram':
            self.gram_entry = ft.TextField(label="الوزن (جم)", width=100, text_align=ft.TextAlign.CENTER)
            price_label = ft.Text(f"{prod['price_per_gram']} ج/جم", color=ft.Colors.GREEN)
            self.qty_container.controls.extend([self.gram_entry, price_label])
        else:
            self.size_combo = ft.Dropdown(
                label="الحجم", 
                options=[ft.dropdown.Option(s) for s in prod['sizes'].keys()],
                width=120
            )
            if prod['sizes']: self.size_combo.value = list(prod['sizes'].keys())[0]
            self.unit_entry = ft.TextField(label="العدد", width=80, text_align=ft.TextAlign.CENTER, value="1")
            self.qty_container.controls.extend([self.size_combo, self.unit_entry])
        
        self.qty_container.update()

    def add_item(self, e):
        name = self.product_combobox.value
        prod = self.PRODUCTS_DICT.get(name)
        if not prod: return
        try:
            if prod['type'] == 'gram':
                qty = int(self.gram_entry.value)
                price = qty * prod['price_per_gram']
                details = f"{qty} جم"
            else:
                qty = int(self.unit_entry.value)
                sz = self.size_combo.value
                price = qty * prod['sizes'][sz]
                details = f"{qty} × {sz}"
            
            self.current_order_items.append({"name": name, "details": details, "sub_total": price})
            
            new_row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(details)),
                    ft.DataCell(ft.Text(f"{price} ج")),
                ],
                on_select_changed=self.on_cart_row_select
            )
            self.cart_table.rows.append(new_row)
            
            self.current_total_price += price
            self.update_totals_display()
        except Exception as ex:
            self.show_message(f"خطأ في الإضافة: {ex}", "red")

    def on_cart_row_select(self, e):
        is_selected = e.data == "true"
        
        for row in self.cart_table.rows:
            if row != e.control and is_selected:
                row.selected = False

        if is_selected:
            self.selected_cart_row = e.control
            self.remove_item_button.disabled = False
        else:
            self.selected_cart_row = None
            self.remove_item_button.disabled = True
        
        self.page.update()

    def remove_item(self, e):
        if self.selected_cart_row is None:
            return
        
        try:
            row_index = self.cart_table.rows.index(self.selected_cart_row)
            item_to_remove = self.current_order_items.pop(row_index)
            self.current_total_price -= item_to_remove['sub_total']
            self.cart_table.rows.pop(row_index)
            
            self.selected_cart_row = None
            self.remove_item_button.disabled = True
            self.update_totals_display()
        except (ValueError, IndexError) as ex:
             self.show_message(f"خطأ في الحذف: {ex}", "red")

    def calculate_finals(self):
        sub = self.current_total_price
        disc = 0
        try:
            val = float(self.discount_entry.value or 0)
            if self.discount_type.selected.pop() == "%":
                disc = sub * (val / 100)
            else:
                disc = val
        except: pass
        ship = self.current_shipping_cost
        final = max(0, sub - disc + ship)
        return sub, disc, ship, final

    def update_totals_display(self, e=None):
        sub, disc, ship, final = self.calculate_finals()
        breakdown = f"المجموع: {sub:,.2f}  -  خصم: {disc:.2f}  +  شحن: {ship:.2f}"
        self.breakdown_label.value = breakdown
        self.final_total_label.value = f"{final:,.2f} ج"
        if hasattr(self, 'page'): self.page.update()

    def load_shipping_rates(self):
        try:
            response = self.supabase.table('shipping_rates').select('region_name, rate').execute()
            if response.data:
                self.shipping_rates = {item['region_name']: float(item['rate']) for item in response.data}
                regions = sorted(self.shipping_rates.keys())
                self.shipping_region_combo.options = [ft.dropdown.Option("اختر المنطقة...")] + [ft.dropdown.Option(r) for r in regions]
            else:
                self.show_message("تنبيه: لم يتم العثور على أسعار شحن", "orange")
        except Exception as e:
            self.show_message(f"فشل تحميل أسعار الشحن: {e}", "red")

    def on_shipping_region_select(self, e):
        region = self.shipping_region_combo.value
        if region == "اختر المنطقة...":
            self.current_shipping_cost = 0.0
        else:
            self.current_shipping_cost = self.shipping_rates.get(region, 0.0)
        
        self.shipping_cost_label.value = f"{self.current_shipping_cost:.2f} ج"
        self.update_totals_display()

    def refresh_customers_dropdown(self):
        try:
            r = self.supabase.rpc('get_customers_by_last_order').execute()
            self.customer_list = [{'id': c['customer_id'], 'name': c['customer_name'] or "", 'phone': c['customer_phone'] or ""} for c in r.data]
            
            options = [ft.dropdown.Option("عميل جديد...")]
            for c in self.customer_list:
                options.append(ft.dropdown.Option(key=c['id'], text=f"{c['name']} - {c['phone']}"))
            self.customer_combobox.options = options
            if hasattr(self, 'page') and self.page: self.page.update()
        except Exception as e:
            print(f"Error fetching customers: {e}")

    def on_invoice_customer_select(self, e):
        cid = self.customer_combobox.value
        if cid != "عميل جديد...":
            self.selected_customer_id = cid
            r = self.supabase.table('invoices').select("*").eq('customer_id', cid).order('invoice_id', desc=True).limit(1).execute()
            if r.data:
                c = r.data[0]
                self.customer_name_entry.value = c.get('customer_name', '')
                self.customer_phone_entry.value = c.get('customer_phone', '')
                self.customer_address_entry.value = c.get('customer_address', '')
                self.customer_notes_entry.value = c.get('notes', '')
        else:
            self.selected_customer_id = None
            self.customer_name_entry.value = ""
            self.customer_phone_entry.value = ""
            self.customer_address_entry.value = ""
            self.customer_notes_entry.value = ""
        self.page.update()

    def validate(self):
        if not self.customer_name_entry.value.strip():
            self.show_message("الرجاء إدخال اسم العميل", "red")
            return False
        if not self.current_order_items:
            self.show_message("السلة فارغة! الرجاء إضافة منتجات", "red")
            return False
        return True

    def _save_to_db(self):
        sub, disc, ship, final = self.calculate_finals()
        inv_data = {
            "customer_id": self.selected_customer_id,
            "customer_name": self.customer_name_entry.value.strip(),
            "customer_phone": self.customer_phone_entry.value.strip(),
            "customer_address": self.customer_address_entry.value.strip(),
            "invoice_date": datetime.now().isoformat(),
            "sub_total": sub, "discount_amount": disc, "shipping_cost": ship, "final_total": final,
            "status": "(جديد)", "notes": self.customer_notes_entry.value.strip()
        }
        res = self.supabase.table('invoices').insert(inv_data).execute()
        new_id = res.data[0]['invoice_id']
        
        items_to_insert = [{
            "invoice_id": new_id, "product_name": i['name'],
            "details": i['details'], "sub_total": i['sub_total']
        } for i in self.current_order_items]
        self.supabase.table('invoice_items').insert(items_to_insert).execute()
        return new_id
    
    def set_buttons_disabled(self, disabled: bool):
        self.save_btn.disabled = disabled
        self.receipt_btn.disabled = disabled
        self.clear_btn.disabled = disabled
        self.page.update()

    def save_invoice_thread(self, e):
        threading.Thread(target=self.save_invoice_task, args=(False,), daemon=True).start()

    def generate_receipt_thread(self, e):
        threading.Thread(target=self.save_invoice_task, args=(True,), daemon=True).start()

    def save_invoice_task(self, show_receipt: bool):
        if not self.validate(): return
        
        self.set_buttons_disabled(True)
        self.show_message("⏳ جاري الحفظ والإرسال...", "blue")
        try:
            inv_id = self._save_to_db()
            self.send_invoice_to_telegram(inv_id)
            
            if show_receipt:
                # Use page.run_thread for UI updates from thread
                self.page.run_thread(target=self._show_receipt_dialog, args=(inv_id,))
            
            self.on_success(inv_id)
        except Exception as e:
            self.show_message(f"❌ خطأ: فشل حفظ الفاتورة. {e}", "red")
        finally:
            self.set_buttons_disabled(False)
    
    def _show_receipt_dialog(self, inv_id):
        txt = self._format_text(inv_id)
        
        def close_dialog(e):
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text(f"الفاتورة #{inv_id}"),
            content=ft.TextField(value=txt, multiline=True, read_only=True, text_align=ft.TextAlign.RIGHT, height=400, width=400),
            actions=[ft.TextButton("إغلاق", on_click=close_dialog)],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
        
    def _format_text(self, inv_id):
        sub, disc, ship, final = self.calculate_finals()
        notes = self.customer_notes_entry.value.strip()
        notes_text = f"📝 ملاحظات: {notes}\n" if notes else ""
        items_text = "\n".join([f"* {i['name']} ({i['details']}) = {i['sub_total']}ج" for i in self.current_order_items])
        return f"""
🧾 فاتورة #{inv_id}
📅 {datetime.now().strftime('%Y-%m-%d')}
👤 {self.customer_name_entry.value}
📞 {self.customer_phone_entry.value}
📍 {self.customer_address_entry.value}
{notes_text}
{"-"*20}
{items_text}
{"-"*20}
المجموع: {sub:.2f} ج
خصم: -{disc:.2f} ج
شحن: +{ship:.2f} ج
الإجمالي: {final:.2f} ج
"""
    def send_invoice_to_telegram(self, inv_id):
        try:
            msg = self._format_telegram_message(inv_id)
            requests.post(f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}/sendMessage", 
                          json={"chat_id": self.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        except Exception as e:
            print(f"Telegram send failed: {e}")

    def _format_telegram_message(self, inv_id):
        sub, disc, ship, final = self.calculate_finals()
        items_txt = "".join([f"<b>- {i['name']}</b> ({i['details']}) = {i['sub_total']} ج\n" for i in self.current_order_items])
        notes = self.customer_notes_entry.value.strip()
        notes_section = f"📝 <b>ملاحظات:</b> {notes}\n────────────────\n" if notes else ""
        
        return f"""
🧾 <b>فاتورة جديدة #{inv_id}</b>
📅 <i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>
────────────────
👤 <b>العميل:</b> {self.customer_name_entry.value}
📱 <b>الهاتف:</b> {self.customer_phone_entry.value}
📍 <b>العنوان:</b> {self.customer_address_entry.value}
────────────────
{notes_section}🛒 <b>المنتجات:</b>
{items_txt}────────────────
💰 <b>المجموع:</b> {sub:,.2f} ج
🏷️ <b>الخصم:</b> -{disc:.2f} ج
🚚 <b>الشحن:</b> +{ship:.2f} ج
💎 <b>الإجمالي النهائي: {final:,.2f} ج</b>
"""

    def clear_order_event(self, e):
        """This function is called by the 'Clear' button click event."""
        self.clear_order()

    def clear_order(self):
        """This function contains the logic to clear the form."""
        self.current_order_items.clear()
        self.current_total_price = 0.0
        self.current_shipping_cost = 0.0
        self.cart_table.rows.clear()
        self.discount_entry.value = "0"
        self.shipping_cost_label.value = "0.00 ج"
        self.shipping_region_combo.value = "اختر المنطقة..."
        self.customer_name_entry.value = ""
        self.customer_phone_entry.value = ""
        self.customer_address_entry.value = ""
        self.customer_notes_entry.value = ""
        self.customer_combobox.value = "عميل جديد..."
        self.selected_customer_id = None
        self.selected_cart_row = None
        self.remove_item_button.disabled = True
        self.update_totals_display()

    def show_message(self, message, color):
        Colors_map = {"red": ft.Colors.RED_ACCENT, "green": ft.Colors.GREEN_ACCENT, "blue": ft.Colors.BLUE_ACCENT, "orange": ft.Colors.ORANGE_ACCENT}
        self.status_bar.content = ft.Text(message)
        self.status_bar.bgcolor = Colors_map.get(color, ft.Colors.BLUE_ACCENT)
        self.status_bar.open = True
        self.page.update()

    def on_success(self, inv_id):
        self.show_message(f"✅ تم حفظ الفاتورة بنجاح برقم {inv_id}", "green")
        self.clear_order()
        threading.Thread(target=self.update_invoice_id_label, daemon=True).start()

    def update_invoice_id_label(self):
        try:
            # استخدام count='exact' يمكن أن يكون أبطأ، نستخدم الطريقة الأسرع
            r = self.supabase.table('invoices').select('invoice_id').order('invoice_id', desc=True).limit(1).execute()
            n = r.data[0]['invoice_id'] + 1 if r.data else 1
            self.next_invoice_id_label.value = f"#{n}"
            if hasattr(self, 'page') and self.page: self.page.update()
        except: pass


# ==============================================================================
# 4. التطبيق الرئيسي (Main App Function)
# ==============================================================================

def main(page: ft.Page):
    page.title = "نظام إدارة الفواتير والمخزون"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.padding = 0

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        page.add(ft.Text(f"❌ فشل الاتصال بقاعدة البيانات: {e}", color=ft.Colors.RED))
        return

    invoice_manager = InvoiceTab(supabase)
    invoice_manager.page = page
    page.snack_bar = invoice_manager.status_bar

    main_tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="🧾 فاتورة جديدة", icon=ft.Icons.ADD_CARD, content=invoice_manager.build()
            ),
            ft.Tab(
                text="🗃️ تصدير وطباعة", icon=ft.Icons.PRINT, content=ft.Container(content=ft.Text("سيتم بناء هذه الواجهة لاحقاً", size=20), alignment=ft.alignment.center)
            ),
            ft.Tab(
                text="✏️ تعديل الفواتير", icon=ft.Icons.EDIT, content=ft.Container(content=ft.Text("سيتم بناء هذه الواجهة لاحقاً", size=20), alignment=ft.alignment.center)
            ),
             ft.Tab(
                text="📦 إدارة المخزون", icon=ft.Icons.INVENTORY, content=ft.Container(content=ft.Text("سيتم بناء هذه الواجهة لاحقاً", size=20), alignment=ft.alignment.center)
            ),
        ],
        expand=1,
    )

    page.add(main_tabs)
    page.update()
    
    invoice_manager.show_message("✅ تم الاتصال بقاعدة البيانات بنجاح", "green")


if __name__ == "__main__":
    ft.app(target=main)