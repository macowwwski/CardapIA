"""
Teste prático para conferir se os nomes dos alimentos batem certo com a Tabela TACO.

Verifica se termos comuns do dia a dia (como 'frango desfiado' ou 'suco de maracujá')
encontram o alimento correto e a quantidade recomendada por aluno.

Como executar:
    python testes/test_taco_resolver.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.taco_resolver import resolver_taco, resolver_per_capita

TERMOS = [
    ("iscas de carne bovina", "Carne, bovina"),
    ("filé de frango desfiado", "Frango, peito"),
    ("suco de maracujá", "Maracujá, suco"),
    ("arroz branco", "Arroz, tipo 1, cozido"),
    ("arroz integral", "Arroz, integral, cozido"),
    ("feijão carioca", "Feijão, carioca, cozido"),
    ("feijão preto", "Feijão, preto, cozido"),
    ("mandioquinha", "Batata, baroa, cozida"),
    ("carne moída", "Carne, bovina, acém, moído, cozido"),
    ("cubos de carne bovina", "Carne, bovina, acém"),
    ("peito de frango cozido", "Frango, peito, sem pele, cozido"),
    ("frango em cubos", "Frango, peito"),
    ("filé de peixe", "Pescada, filé"),
    ("alface americana", "Alface, americana"),
    ("alface crespa", "Alface, crespa"),
    ("alface", "Alface"),
    ("tomate", "Tomate"),
    ("cenoura cozida", "Cenoura, cozida"),
    ("cenoura ralada", "Cenoura"),
    ("beterraba cozida", "Beterraba, cozida"),
    ("abóbora cozida", "Abóbora, cabotian, cozida"),
    ("chuchu cozido", "Chuchu, cozido"),
    ("batata inglesa cozida", "Batata, inglesa, cozida"),
    ("batata doce cozida", "Batata, doce, cozida"),
    ("mandioca cozida", "Mandioca, cozida"),
    ("macarrão cozido", "Macarrão"),
    ("suco de laranja", "Laranja, pêra, suco"),
    ("suco de caju", "Caju, suco"),
    ("suco de uva", "Uva, suco"),
    ("banana prata", "Banana, prata"),
    ("maçã fuji", "Maçã, Fuji"),
    ("laranja pera", "Laranja, pêra"),
    ("melancia", "Melancia"),
    ("mamão", "Mamão"),
    ("abacaxi", "Abacaxi"),
    ("leite integral", "Leite, de vaca, integral"),
    ("iogurte natural", "Iogurte, natural"),
    ("ovo cozido", "Ovo, de galinha, inteiro, cozido"),
    ("pão francês", "Pão"),
    ("óleo de soja", "Óleo, de soja"),
    ("azeite de oliva", "Azeite, de oliva"),
]


def testar():
    """Percorre a lista de alimentos de teste e confere a taxa de acerto do sistema."""
    acertos = 0
    total = len(TERMOS)
    print(f"Testando a identificação de alimentos com {total} exemplos comuns...\n")

    for termo, esperado_parcial in TERMOS:
        m = resolver_taco(termo)
        if not m:
            print(f"[FALHA] {termo!r} -> Nenhum casamento encontrado!")
            continue

        pc = resolver_per_capita(termo, "creche", taco_id=m.taco_id)
        bateu = esperado_parcial.lower() in m.description.lower()
        if bateu:
            acertos += 1
            status = "[OK]"
        else:
            status = "[DIVERGENTE]"

        print(f"{status:13} {termo:25} -> {m.description:45} | per_capita: {pc}g")

    taxa = (acertos / total) * 100
    print(f"\nResultado Final: {acertos}/{total} acertos ({taxa:.1f}%)")
    assert taxa >= 98.0, f"Taxa de acertos ({taxa:.1f}%) abaixo da meta mínima de 98%!"


if __name__ == "__main__":
    testar()
