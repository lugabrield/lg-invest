"""Trap Detection Engine — Ações (Sprint 26, Fase 3).

Detecta padrões fundamentalistas clássicos de "armadilha de valuation":
P/L baixo por lucro insustentável, P/VP baixo por retorno sobre capital
fraco, crescimento supervalorizado já embutido no preço, alavancagem
mascarada atrás de múltiplos aparentemente baratos, e dado fundamentalista
incompleto demais para sustentar qualquer leitura. Cada detector é puro
(sem I/O) e nunca gera recomendação de compra/venda — só reduz confiança
e explica o quê e por quê.
"""
