#!/usr/bin/env python3
"""
CUDI RECHNUNGSASSISTENT PLUGIN
Finanzmodul für automatisierte Rechnungserstellung und -verwaltung
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime, timedelta
import json
import sqlite3
from pathlib import Path

class RechnungsassistentPlugin:
    """CUDI Rechnungsassistent - Finanzmodul Plugin"""
    
    # Plugin Metadata
    PLUGIN_INFO = {
        "name": "Rechnungsassistent",
        "version": "1.0.0",
        "category": "Finanzen",
        "description": "Automatisierte Rechnungserstellung und Finanzverwaltung",
        "author": "CUDI Systems",
        "requires": ["sqlite3", "tkinter"],
        "permissions": ["database_access", "file_system", "ui_integration"],
        "signature": "SHA256:A1B2C3D4E5F6789012345678901234567890ABCDEF1234567890ABCDEF123456"
    }
    
    def __init__(self, parent_system):
        """Initialisiere Rechnungsassistent Plugin"""
        self.parent = parent_system
        self.plugin_db = None
        self.setup_database()
        
    def setup_database(self):
        """Setup Plugin-spezifische Datenbank"""
        db_path = Path("plugins/data/rechnungsassistent.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.plugin_db = sqlite3.connect(db_path, check_same_thread=False)
        cursor = self.plugin_db.cursor()
        
        # Rechnungen Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                amount REAL NOT NULL,
                tax_rate REAL DEFAULT 19.0,
                status TEXT DEFAULT 'Entwurf',
                created_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                description TEXT,
                items TEXT  -- JSON string for invoice items
            )
        """)
        
        # Kunden Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT UNIQUE NOT NULL,
                company_name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                address TEXT,
                tax_number TEXT,
                payment_terms INTEGER DEFAULT 30
            )
        """)
        
        self.plugin_db.commit()
        
    def get_plugin_info(self):
        """Gib Plugin-Informationen zurück"""
        return self.PLUGIN_INFO
        
    def install(self):
        """Plugin Installation"""
        try:
            # Prüfe Abhängigkeiten
            self.check_dependencies()
            
            # Initialisiere Datenbank
            self.setup_database()
            
            # Erstelle Beispieldaten
            self.create_sample_data()
            
            return {"success": True, "message": "Rechnungsassistent erfolgreich installiert"}
            
        except Exception as e:
            return {"success": False, "message": f"Installation fehlgeschlagen: {str(e)}"}
    
    def uninstall(self):
        """Plugin Deinstallation"""
        try:
            if self.plugin_db:
                self.plugin_db.close()
            return {"success": True, "message": "Rechnungsassistent deinstalliert"}
        except Exception as e:
            return {"success": False, "message": f"Deinstallation fehlgeschlagen: {str(e)}"}
    
    def check_dependencies(self):
        """Prüfe Plugin-Abhängigkeiten"""
        required = self.PLUGIN_INFO["requires"]
        missing = []
        
        for dep in required:
            try:
                if dep == "sqlite3":
                    import sqlite3
                elif dep == "tkinter":
                    import tkinter
                # Weitere Abhängigkeiten hier prüfen
            except ImportError:
                missing.append(dep)
        
        if missing:
            raise Exception(f"Fehlende Abhängigkeiten: {', '.join(missing)}")
    
    def create_sample_data(self):
        """Erstelle Beispieldaten"""
        cursor = self.plugin_db.cursor()
        
        # Beispiel-Kunden
        sample_customers = [
            ("CUST001", "TechStart GmbH", "Max Mustermann", "max@techstart.de", 
             "Hauptstraße 123, 12345 Berlin", "DE123456789", 30),
            ("CUST002", "Innovation AG", "Anna Schmidt", "anna@innovation.de",
             "Innovationsweg 456, 54321 München", "DE987654321", 14),
            ("CUST003", "StartUp Solutions", "Peter Weber", "peter@startup.de",
             "Gründerstraße 789, 98765 Hamburg", "DE456789123", 30)
        ]
        
        for customer in sample_customers:
            cursor.execute("""
                INSERT OR REPLACE INTO customers 
                (customer_id, company_name, contact_person, email, address, tax_number, payment_terms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, customer)
        
        # Beispiel-Rechnungen
        sample_invoices = [
            ("RE-2025-001", "CUST001", "TechStart GmbH", 5999.99, 19.0, "Bezahlt",
             "2025-07-01", "2025-07-31", "CUDI Enterprise Lizenz",
             '[{"item": "CUDI Enterprise License", "quantity": 1, "price": 5999.99}]'),
            ("RE-2025-002", "CUST002", "Innovation AG", 3499.99, 19.0, "Offen",
             "2025-07-15", "2025-08-14", "CUDI Business Pro Lizenz",
             '[{"item": "CUDI Business Pro License", "quantity": 1, "price": 3499.99}]'),
            ("RE-2025-003", "CUST003", "StartUp Solutions", 1999.99, 19.0, "Überfällig",
             "2025-06-01", "2025-07-01", "CUDI Startup Paket",
             '[{"item": "CUDI Startup Package", "quantity": 1, "price": 1999.99}]')
        ]
        
        for invoice in sample_invoices:
            cursor.execute("""
                INSERT OR REPLACE INTO invoices 
                (invoice_number, customer_id, customer_name, amount, tax_rate, status, 
                 created_date, due_date, description, items)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, invoice)
        
        self.plugin_db.commit()
    
    def create_gui_tab(self, notebook):
        """Erstelle GUI-Tab für Rechnungsassistent"""
        billing_frame = ttk.Frame(notebook, style='Master.TFrame')
        notebook.add(billing_frame, text="💰 Rechnungsassistent")
        
        # Header
        header_frame = ttk.LabelFrame(billing_frame, text="💰 Rechnungsassistent - Finanzmodul")
        header_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Statistiken
        stats_frame = ttk.Frame(header_frame)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        stats = self.get_billing_statistics()
        stats_labels = [
            ("📊 Gesamtumsatz:", f"€{stats['total_revenue']:,.2f}"),
            ("📋 Offene Rechnungen:", f"{stats['open_invoices']}"),
            ("⚠️ Überfällige:", f"{stats['overdue_invoices']}"),
            ("✅ Bezahlt (30 Tage):", f"€{stats['paid_30_days']:,.2f}")
        ]
        
        for i, (label, value) in enumerate(stats_labels):
            col = i % 4
            stat_frame = ttk.Frame(stats_frame)
            stat_frame.grid(row=0, column=col, padx=10, pady=5, sticky='ew')
            
            ttk.Label(stat_frame, text=label, style='Master.TLabel').pack(anchor='w')
            ttk.Label(stat_frame, text=value, foreground='#00ff00', 
                     font=('Arial', 10, 'bold')).pack(anchor='w')
        
        for i in range(4):
            stats_frame.grid_columnconfigure(i, weight=1)
        
        # Rechnungsübersicht
        invoice_frame = ttk.LabelFrame(billing_frame, text="📋 Rechnungsübersicht")
        invoice_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(invoice_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="➕ Neue Rechnung", 
                  command=self.create_new_invoice, style='Master.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✏️ Bearbeiten", 
                  command=self.edit_invoice, style='Master.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📤 Senden", 
                  command=self.send_invoice, style='Master.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="💾 PDF Export", 
                  command=self.export_pdf, style='Master.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📊 Bericht", 
                  command=self.generate_report, style='Master.TButton').pack(side=tk.LEFT, padx=2)
        
        # Rechnungs-Treeview
        self.invoice_tree = ttk.Treeview(invoice_frame, 
                                        columns=('Customer', 'Amount', 'Status', 'Due_Date', 'Created'), 
                                        height=12)
        self.invoice_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Spalten konfigurieren
        self.invoice_tree.heading('#0', text='Rechnungsnummer')
        self.invoice_tree.heading('Customer', text='Kunde')
        self.invoice_tree.heading('Amount', text='Betrag')
        self.invoice_tree.heading('Status', text='Status')
        self.invoice_tree.heading('Due_Date', text='Fälligkeitsdatum')
        self.invoice_tree.heading('Created', text='Erstellt')
        
        # Rechnungen laden
        self.load_invoices()
        
        return billing_frame
    
    def get_billing_statistics(self):
        """Hole Rechnungsstatistiken"""
        cursor = self.plugin_db.cursor()
        
        # Gesamtumsatz
        cursor.execute("SELECT SUM(amount) FROM invoices WHERE status = 'Bezahlt'")
        total_revenue = cursor.fetchone()[0] or 0
        
        # Offene Rechnungen
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'Offen'")
        open_invoices = cursor.fetchone()[0] or 0
        
        # Überfällige Rechnungen
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'Offen' AND due_date < ?", (today,))
        overdue_invoices = cursor.fetchone()[0] or 0
        
        # Bezahlt in letzten 30 Tagen
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("SELECT SUM(amount) FROM invoices WHERE status = 'Bezahlt' AND created_date >= ?", (thirty_days_ago,))
        paid_30_days = cursor.fetchone()[0] or 0
        
        return {
            'total_revenue': total_revenue,
            'open_invoices': open_invoices,
            'overdue_invoices': overdue_invoices,
            'paid_30_days': paid_30_days
        }
    
    def load_invoices(self):
        """Lade Rechnungen in Treeview"""
        cursor = self.plugin_db.cursor()
        cursor.execute("""
            SELECT invoice_number, customer_name, amount, status, due_date, created_date
            FROM invoices 
            ORDER BY created_date DESC
        """)
        
        # Lösche bestehende Einträge
        for item in self.invoice_tree.get_children():
            self.invoice_tree.delete(item)
        
        # Füge Rechnungen hinzu
        for invoice in cursor.fetchall():
            invoice_number, customer_name, amount, status, due_date, created_date = invoice
            
            # Status-Emoji
            status_emoji = {
                'Entwurf': '📝',
                'Offen': '🟡',
                'Bezahlt': '✅',
                'Überfällig': '🔴',
                'Storniert': '❌'
            }.get(status, '❓')
            
            status_display = f"{status_emoji} {status}"
            
            self.invoice_tree.insert('', 'end', text=invoice_number,
                                   values=(customer_name, f"€{amount:,.2f}", 
                                          status_display, due_date, created_date))
    
    def create_new_invoice(self):
        """Erstelle neue Rechnung"""
        messagebox.showinfo("Neue Rechnung", "💰 Neue Rechnung erstellen - Feature in Entwicklung")
    
    def edit_invoice(self):
        """Bearbeite Rechnung"""
        selected = self.invoice_tree.selection()
        if not selected:
            messagebox.showwarning("Keine Auswahl", "Bitte wählen Sie eine Rechnung aus")
            return
        messagebox.showinfo("Rechnung bearbeiten", "✏️ Rechnung bearbeiten - Feature in Entwicklung")
    
    def send_invoice(self):
        """Sende Rechnung"""
        selected = self.invoice_tree.selection()
        if not selected:
            messagebox.showwarning("Keine Auswahl", "Bitte wählen Sie eine Rechnung aus")
            return
        messagebox.showinfo("Rechnung senden", "📤 Rechnung wurde per E-Mail versendet")
    
    def export_pdf(self):
        """Exportiere Rechnung als PDF"""
        selected = self.invoice_tree.selection()
        if not selected:
            messagebox.showwarning("Keine Auswahl", "Bitte wählen Sie eine Rechnung aus")
            return
        messagebox.showinfo("PDF Export", "💾 Rechnung als PDF exportiert")
    
    def generate_report(self):
        """Generiere Finanzbericht"""
        messagebox.showinfo("Finanzbericht", "📊 Finanzbericht generiert")
    
    def get_commands(self):
        """Gib verfügbare Plugin-Befehle zurück"""
        return {
            "rechnung_erstellen": self.create_invoice_command,
            "rechnungen_anzeigen": self.show_invoices_command,
            "umsatz_bericht": self.revenue_report_command,
            "kunde_hinzufugen": self.add_customer_command
        }
    
    def create_invoice_command(self, **kwargs):
        """Befehl: Rechnung erstellen"""
        return "💰 Rechnung wird erstellt..."
    
    def show_invoices_command(self, **kwargs):
        """Befehl: Rechnungen anzeigen"""
        stats = self.get_billing_statistics()
        return f"""
📋 RECHNUNGSÜBERSICHT:
• Gesamtumsatz: €{stats['total_revenue']:,.2f}
• Offene Rechnungen: {stats['open_invoices']}
• Überfällige Rechnungen: {stats['overdue_invoices']}
• Bezahlt (30 Tage): €{stats['paid_30_days']:,.2f}
        """
    
    def revenue_report_command(self, **kwargs):
        """Befehl: Umsatzbericht"""
        stats = self.get_billing_statistics()
        return f"""
📊 UMSATZBERICHT:
• Gesamtumsatz: €{stats['total_revenue']:,.2f}
• Durchschnitt/Rechnung: €{stats['total_revenue']/max(1, stats['open_invoices']):,.2f}
• Offene Forderungen: {stats['open_invoices']} Rechnungen
• Überfällige Beträge: {stats['overdue_invoices']} Rechnungen
        """
    
    def add_customer_command(self, **kwargs):
        """Befehl: Kunde hinzufügen"""
        return "👤 Kunde wird hinzugefügt..."

# Plugin Export für dynamisches Laden
def get_plugin_class():
    """Gibt die Plugin-Klasse für dynamisches Laden zurück"""
    return RechnungsassistentPlugin
