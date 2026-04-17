import re, unicodedata as ud

def normalizar(s):
    return ud.normalize('NFD', s.lower()).encode('ascii', 'ignore').decode()

PALAVRAS_NUM = {'dois': 2, 'tres': 3, 'quatro': 4, 'cinco': 5,
                'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10}

casos = [
    ('4 pneus', 4),
    ('quatro motos', 4),
    ('tres pneus', 3),
    ('tres motos diferentes', 3),
    ('quero 3 pneus', 3),
    ('preciso de 4', 4),
    ('comprar 3', 3),
    ('dez rodas', 10),
    ('dois pneus', 2),       # nao deve disparar handoff (< 3), mas qtd=2 OK
    ('sao 4 da tarde', 0),   # falso positivo - deve ser 0
    ('bom dia', 0),
    ('quero um pneu', 0),
    ('to querendo comprar 4 pneus pra minha moto', 4),
    ('uma CG uma Twister uma fazer e uma nmax', 0),  # sem numero, sem keyword pneu
    ('quero pneu para 3 motos', 3),
    ('3 pneus para 3 motos', 3),
]

ok_count = 0
for msg, esperado in casos:
    n = normalizar(msg)
    qtd = 0
    m = re.search(r'(\d+)\s*(?:pneus?|motos?|rodas?)', n)
    if m: qtd = max(qtd, int(m.group(1)))
    m2 = re.search(r'(?:quero|comprar|precis[ao]|pedir|colocar)\s+(?:de\s+)?(\d+)\b', n)
    if m2: qtd = max(qtd, int(m2.group(1)))
    for palavra, val in PALAVRAS_NUM.items():
        if re.search(rf'\b{palavra}\b\s*(?:pneus?|motos?|rodas?)', n): qtd = max(qtd, val)
    status = 'OK' if qtd == esperado else f'FAIL (got {qtd})'
    print(f'{status:20} [{esperado}] {msg}')
    if qtd == esperado:
        ok_count += 1

print(f'\n{ok_count}/{len(casos)} passaram')
