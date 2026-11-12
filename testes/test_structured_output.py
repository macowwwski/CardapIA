import _bootstrap  # noqa: F401

from src.ai_service import CardapioSchema
from src.services.ai_generator import criar_llm


def test_structured_output_schema_suportado():
    assert "semanas" in CardapioSchema.model_fields


if __name__ == "__main__":
    llm = criar_llm(temperature=0)
    llm_structured = llm.with_structured_output(CardapioSchema)

    res = llm_structured.invoke("""
Retorne EXATAMENTE este JSON:

{
  "mes_aplicacao": "teste",
  "semanas": [],
  "observacoes": "teste"
}
""")

    print(res)

