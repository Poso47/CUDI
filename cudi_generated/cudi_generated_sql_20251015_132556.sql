-- SQL Script generiert von CUDI
-- Basierend auf: sql datenbank erstellen
-- Domain: test
-- Erstellt: 2025-10-15 13:25:56

CREATE TABLE IF NOT EXISTS cudi_data (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    value INT DEFAULT 0,
    created_date DATE DEFAULT CURRENT_DATE,
    status ENUM('active', 'inactive') DEFAULT 'active',
    domain VARCHAR(100) DEFAULT 'test'
);

INSERT INTO cudi_data (name, value, status) VALUES 
('Beispiel 1', 100, 'active'),
('Beispiel 2', 200, 'inactive'),
('CUDI Generated', 999, 'active');

-- Abfrage für alle aktiven Einträge
SELECT * FROM cudi_data WHERE status = 'active';
