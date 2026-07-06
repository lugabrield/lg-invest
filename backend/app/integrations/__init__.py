"""Integrações com fontes externas de dados (Sprint 23).

Camada separada dos engines/serviços internos: tudo que fala com um
site/API de terceiros (login, navegação, scraping, parsing de HTML)
vive aqui, nunca dentro de `engines/` ou `services/` — engines
continuam puros, e serviços continuam sem depender de bibliotecas de
automação de navegador.
"""
