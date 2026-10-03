"""demo/ é a fixture: uma falha plantada por arquivo, e os controles passam limpos."""
import contagem


def test_contagem_exata_por_check():
    achados = contagem.contar()
    for check, arquivo in contagem.ESPERADO.items():
        assert sorted(achados[check]) == [arquivo], check


def test_nenhum_controle_reprova():
    achados = contagem.contar()
    reprovados = {a for c in contagem.ESPERADO for a in achados[c]}
    assert reprovados == set(contagem.ESPERADO.values())


def test_total_de_notas_e_isencao_do_inbox():
    achados = contagem.contar()
    assert achados["_total"] == contagem.TOTAL_NOTAS
    assert achados["_isentas"] == contagem.ISENTAS_ANEL


def test_nenhum_check_inesperado():
    achados = contagem.contar()
    assert set(achados) - {"_total", "_isentas"} == set(contagem.ESPERADO)
