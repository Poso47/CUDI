"""CUDI – persönlicher KI-Kollege mit Digitalem Gehirn.

Dieses Paket enthält den GUI-unabhängigen Kern:

* ``cudi.config``      Einstellungen und Protokollierung
* ``cudi.core``        Orchestrator, Absichtserkennung, Berechtigungen
* ``cudi.brain``       Digitales Gehirn (Gedächtnis, Projekte, Wissen, Verlauf)
* ``cudi.models``      Sprachmodell-Anbieter und Model Manager
* ``cudi.tools``       Werkzeuge, die CUDI tatsächlich ausführen kann
* ``cudi.diagnostics`` Selbstdiagnose

Einstieg: ``cudi.core.application.create_app()``.
"""

__version__ = "0.3.0"
