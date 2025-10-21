const fs = require("fs");
const { spawn } = require("child_process");
const path = require("path");

console.log("🔍 CUDI Safe Start - Preflight Check...");

// Prüfe ob Diagnose-Datei existiert
const diagFile = "./cudi_diag.txt";
if (!fs.existsSync(diagFile)) {
  console.error("⛔ Keine Diagnose gefunden. Führe zuerst CUDI-Diagnose.ps1 aus!");
  process.exit(1);
}

const diag = fs.readFileSync(diagFile, "utf8");

// Prüfe auf kritische Fehler
const checks = [
  { pattern: /WRITE:\s*FAIL/i, message: "Schreibrechte-Fehler" },
  { pattern: /PING:\s*FAIL/i, message: "Ping-Test fehlgeschlagen" },
  { pattern: /SEARCH:\s*FAIL/i, message: "Search-Test fehlgeschlagen" },
  { pattern: /Python:\s*.*nicht gefunden/i, message: "Python nicht verfügbar" },
  { pattern: /ERROR|FATAL|CRITICAL/i, message: "Kritischer Systemfehler" }
];

const failures = [];
for (const check of checks) {
  if (check.pattern.test(diag)) {
    failures.push(check.message);
  }
}

if (failures.length > 0) {
  console.error("⛔ Start gestoppt – Preflight FAIL:");
  failures.forEach(fail => console.error(`  ❌ ${fail}`));
  console.error("\n📋 Öffne cudi_diag.txt für Details.");
  process.exit(1);
}

// Prüfe auf positive Indikatoren
const successChecks = [
  /WRITE:\s*OK/i,
  /Python:\s*Python\s+\d+\.\d+/i
];

const successCount = successChecks.filter(check => check.test(diag)).length;
if (successCount < 2) {
  console.warn("⚠️ Warnung: Nicht alle Basis-Checks erfolgreich");
}

console.log("✅ Preflight OK – starte CUDI...");

// CUDI starten
const cudiProcess = spawn("python", ["launch_cudi_perfect.py"], {
  stdio: "inherit",
  cwd: process.cwd()
});

cudiProcess.on("close", (code) => {
  console.log(`\n🎯 CUDI beendet mit Code: ${code}`);
});

cudiProcess.on("error", (err) => {
  console.error(`❌ CUDI Start-Fehler: ${err.message}`);
  process.exit(1);
});