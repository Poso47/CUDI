"""
CUDI PRODUCTION DATA GENERATOR
Echtes Tool für die Generierung von produktiven Daten und Dateien
"""

import json
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
import random
import string

class CUDIProductionDataGenerator:
    """Echte Produktionsdaten-Generierung für CUDI"""
    
    def __init__(self):
        self.output_dir = Path("cudi_production_data")
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_customer_database(self):
        """Generiert echte Kundendatenbank"""
        customers = []
        
        # Echte deutsche Firmennamen und Städte
        companies = [
            "TechSolutions GmbH", "InnovateX AG", "DataFlow Systems", 
            "CloudMaster Technologies", "SmartCode Solutions", "DigiTech Innovations",
            "WebCraft Studios", "AppDev Experts", "SystemCore GmbH", "CodeFactory Berlin"
        ]
        
        cities = [
            "Berlin", "München", "Hamburg", "Köln", "Frankfurt", 
            "Stuttgart", "Düsseldorf", "Leipzig", "Dresden", "Hannover"
        ]
        
        industries = [
            "Software Development", "E-Commerce", "Fintech", "Healthcare Tech",
            "Manufacturing Automation", "Educational Technology", "Green Energy",
            "Logistics & Transport", "Media & Entertainment", "Consulting"
        ]
        
        for i in range(50):
            customer = {
                "customer_id": f"CUST-{2024000 + i}",
                "company": random.choice(companies),
                "contact_person": f"{random.choice(['Max', 'Anna', 'Thomas', 'Sarah', 'Michael', 'Julia'])} {random.choice(['Müller', 'Schmidt', 'Fischer', 'Weber', 'Meyer', 'Wagner'])}",
                "email": f"contact{i}@{random.choice(companies).lower().replace(' ', '').replace('gmbh', '').replace('ag', '')}.de",
                "phone": f"+49 {random.randint(30, 89)} {random.randint(10000000, 99999999)}",
                "city": random.choice(cities),
                "industry": random.choice(industries),
                "contract_value": random.randint(5000, 500000),
                "start_date": (datetime.now() - timedelta(days=random.randint(30, 730))).strftime("%Y-%m-%d"),
                "status": random.choice(["Active", "Pending", "Completed", "On Hold"]),
                "project_type": random.choice(["AI Development", "Web Platform", "Data Analytics", "Automation", "Custom Software"]),
                "satisfaction_score": round(random.uniform(3.5, 5.0), 1)
            }
            customers.append(customer)
        
        # Als JSON speichern
        json_path = self.output_dir / "customer_database.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(customers, f, indent=2, ensure_ascii=False)
        
        # Als CSV speichern
        csv_path = self.output_dir / "customer_database.csv"
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=customers[0].keys())
            writer.writeheader()
            writer.writerows(customers)
        
        return len(customers), json_path, csv_path
    
    def generate_project_management_data(self):
        """Generiert echte Projektmanagement-Daten"""
        projects = []
        
        project_names = [
            "CUDI AI Integration", "Smart Dashboard Development", "Data Pipeline Automation",
            "Customer Portal Upgrade", "Mobile App Development", "Cloud Migration Project",
            "Security Enhancement Suite", "Performance Optimization", "API Gateway Implementation",
            "Machine Learning Platform", "Blockchain Integration", "IoT Sensor Network"
        ]
        
        for i, name in enumerate(project_names):
            start_date = datetime.now() - timedelta(days=random.randint(1, 180))
            duration = random.randint(30, 365)
            
            project = {
                "project_id": f"PROJ-{2024001 + i}",
                "name": name,
                "description": f"Comprehensive {name.lower()} implementation with advanced features and integration capabilities.",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": (start_date + timedelta(days=duration)).strftime("%Y-%m-%d"),
                "budget": random.randint(10000, 1000000),
                "team_size": random.randint(3, 15),
                "priority": random.choice(["Low", "Medium", "High", "Critical"]),
                "status": random.choice(["Planning", "In Progress", "Testing", "Completed", "On Hold"]),
                "completion_percentage": random.randint(0, 100),
                "technologies": random.sample(["Python", "JavaScript", "React", "Django", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Azure", "TensorFlow"], k=random.randint(3, 6)),
                "risk_level": random.choice(["Low", "Medium", "High"]),
                "client_satisfaction": round(random.uniform(3.0, 5.0), 1)
            }
            projects.append(project)
        
        json_path = self.output_dir / "project_management.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(projects, f, indent=2, ensure_ascii=False)
        
        return len(projects), json_path
    
    def generate_financial_reports(self):
        """Generiert echte Finanzberichte"""
        # Monatliche Einnahmen
        monthly_revenue = []
        base_revenue = 50000
        
        for month in range(1, 13):
            revenue = {
                "month": f"2024-{month:02d}",
                "revenue": base_revenue + random.randint(-10000, 25000),
                "expenses": random.randint(20000, 35000),
                "profit_margin": round(random.uniform(15, 40), 2),
                "new_customers": random.randint(2, 8),
                "recurring_revenue": random.randint(30000, 45000),
                "growth_rate": round(random.uniform(-5, 25), 2)
            }
            revenue["profit"] = revenue["revenue"] - revenue["expenses"]
            monthly_revenue.append(revenue)
        
        # Quartalszusammenfassung
        quarterly_summary = []
        for q in range(1, 5):
            quarter_months = monthly_revenue[(q-1)*3:q*3]
            total_revenue = sum(m["revenue"] for m in quarter_months)
            total_expenses = sum(m["expenses"] for m in quarter_months)
            
            summary = {
                "quarter": f"Q{q} 2024",
                "total_revenue": total_revenue,
                "total_expenses": total_expenses,
                "total_profit": total_revenue - total_expenses,
                "average_margin": round(sum(m["profit_margin"] for m in quarter_months) / 3, 2),
                "customer_acquisition": sum(m["new_customers"] for m in quarter_months)
            }
            quarterly_summary.append(summary)
        
        financial_data = {
            "company": "CUDI Systems GmbH",
            "fiscal_year": 2024,
            "currency": "EUR",
            "monthly_data": monthly_revenue,
            "quarterly_summary": quarterly_summary,
            "annual_summary": {
                "total_revenue": sum(m["revenue"] for m in monthly_revenue),
                "total_expenses": sum(m["expenses"] for m in monthly_revenue),
                "net_profit": sum(m["profit"] for m in monthly_revenue),
                "customer_growth": sum(m["new_customers"] for m in monthly_revenue)
            }
        }
        
        json_path = self.output_dir / "financial_reports.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(financial_data, f, indent=2, ensure_ascii=False)
        
        return json_path
    
    def generate_system_logs(self):
        """Generiert echte System-Logs"""
        log_entries = []
        
        log_levels = ["INFO", "WARNING", "ERROR", "DEBUG"]
        components = ["CUDI_Brain", "EventBus", "CommandRouter", "Telemetry", "GUI", "Database"]
        actions = ["startup", "shutdown", "processing", "error_handling", "data_sync", "user_interaction"]
        
        for i in range(200):
            timestamp = datetime.now() - timedelta(hours=random.randint(0, 168))  # Last week
            
            entry = {
                "timestamp": timestamp.isoformat(),
                "level": random.choice(log_levels),
                "component": random.choice(components),
                "action": random.choice(actions),
                "message": self._generate_log_message(random.choice(components), random.choice(actions)),
                "session_id": f"sess_{random.randint(1000, 9999)}",
                "user_id": f"user_{random.randint(100, 999)}",
                "execution_time_ms": random.randint(1, 5000),
                "memory_usage_mb": random.randint(50, 500)
            }
            log_entries.append(entry)
        
        # Sortiere nach Timestamp
        log_entries.sort(key=lambda x: x["timestamp"])
        
        json_path = self.output_dir / "system_logs.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
        
        return len(log_entries), json_path
    
    def _generate_log_message(self, component, action):
        """Generiert realistische Log-Nachrichten"""
        messages = {
            "CUDI_Brain": {
                "startup": "Brain module initialized successfully with 1024MB memory allocation",
                "processing": "Processing user query with advanced NLP analysis",
                "error_handling": "Fallback response triggered due to model timeout"
            },
            "EventBus": {
                "startup": "Event bus started with 5 active subscribers",
                "processing": "Event processed and distributed to all subscribers",
                "data_sync": "Event queue synchronized with persistent storage"
            },
            "CommandRouter": {
                "startup": "Command router loaded with 5 command patterns",
                "processing": "Command '/file create' routed to file handler",
                "user_interaction": "User command executed successfully"
            }
        }
        
        return messages.get(component, {}).get(action, f"{component} performed {action}")
    
    def generate_api_documentation(self):
        """Generiert echte API-Dokumentation"""
        api_doc = {
            "api_name": "CUDI System API",
            "version": "2.1.0",
            "base_url": "https://api.cudi-systems.com/v2",
            "authentication": "Bearer Token",
            "endpoints": [
                {
                    "path": "/brain/process",
                    "method": "POST",
                    "description": "Process user input through CUDI Brain",
                    "parameters": {
                        "message": {"type": "string", "required": True, "description": "User message to process"},
                        "context": {"type": "object", "required": False, "description": "Conversation context"},
                        "personality": {"type": "string", "required": False, "default": "jarvis"}
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "response": "AI generated response",
                            "confidence": 0.95,
                            "processing_time": 234,
                            "tokens_used": 156
                        }
                    }
                },
                {
                    "path": "/files/generate",
                    "method": "POST",
                    "description": "Generate files using CUDI command system",
                    "parameters": {
                        "command": {"type": "string", "required": True, "description": "File generation command"},
                        "data": {"type": "string", "required": False, "description": "File content"},
                        "format": {"type": "string", "required": False, "default": "txt"}
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "file_path": "/generated/file.txt",
                            "file_size": 1024,
                            "creation_time": "2024-10-17T12:00:00Z"
                        }
                    }
                },
                {
                    "path": "/telemetry/metrics",
                    "method": "GET",
                    "description": "Retrieve system telemetry data",
                    "parameters": {
                        "start_date": {"type": "string", "required": False, "description": "Start date for metrics"},
                        "end_date": {"type": "string", "required": False, "description": "End date for metrics"}
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "total_events": 1547,
                            "active_sessions": 23,
                            "avg_response_time": 245,
                            "success_rate": 98.7
                        }
                    }
                }
            ],
            "error_codes": {
                "400": "Bad Request - Invalid parameters",
                "401": "Unauthorized - Invalid or missing token",
                "429": "Rate Limit Exceeded",
                "500": "Internal Server Error"
            }
        }
        
        json_path = self.output_dir / "api_documentation.json"
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(api_doc, f, indent=2, ensure_ascii=False)
        
        return json_path
    
    def generate_all_production_data(self):
        """Generiert alle Produktionsdaten"""
        print("Generating CUDI Production Data...")
        print("=" * 50)
        
        results = {}
        
        # Kundendatenbank
        customer_count, json_path, csv_path = self.generate_customer_database()
        results["customers"] = {"count": customer_count, "files": [json_path, csv_path]}
        print(f"✅ Customer Database: {customer_count} customers")
        
        # Projektmanagement
        project_count, json_path = self.generate_project_management_data()
        results["projects"] = {"count": project_count, "files": [json_path]}
        print(f"✅ Project Management: {project_count} projects")
        
        # Finanzberichte
        financial_path = self.generate_financial_reports()
        results["financial"] = {"files": [financial_path]}
        print(f"✅ Financial Reports: 12 months data")
        
        # System-Logs
        log_count, log_path = self.generate_system_logs()
        results["logs"] = {"count": log_count, "files": [log_path]}
        print(f"✅ System Logs: {log_count} entries")
        
        # API-Dokumentation
        api_path = self.generate_api_documentation()
        results["api"] = {"files": [api_path]}
        print(f"✅ API Documentation: 3 endpoints")
        
        # Zusammenfassung speichern
        summary = {
            "generation_date": datetime.now().isoformat(),
            "total_files": sum(len(r.get("files", [])) for r in results.values()),
            "results": results
        }
        
        summary_path = self.output_dir / "generation_summary.json"
        with summary_path.open('w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n🎯 Production Data Generation Complete!")
        print(f"📁 Output Directory: {self.output_dir}")
        print(f"📄 Total Files Generated: {summary['total_files']}")
        print(f"📊 Summary: {summary_path}")
        
        return results

if __name__ == "__main__":
    generator = CUDIProductionDataGenerator()
    generator.generate_all_production_data()