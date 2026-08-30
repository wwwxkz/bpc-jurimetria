"""Consulta processos do BPC e baixa pecas publicas em uma unica etapa."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from nanojud import esaj
from nanojud.exceptions import NanoJudError


def numero_formatado(numero: str) -> str:
    digitos = re.sub(r"\D", "", numero)
    if len(digitos) != 20:
        raise ValueError(f"Numero CNJ invalido: {numero}")
    return f"{digitos[:7]}-{digitos[7:9]}.{digitos[9:13]}.{digitos[13]}.{digitos[14:16]}.{digitos[16:]}"


def ler_processos(entrada: Path) -> list[str]:
    processos = []
    with entrada.open(encoding="utf-8") as arquivo:
        for linha in arquivo:
            if linha.strip():
                numero = json.loads(linha).get("numeroProcesso")
                if numero:
                    processos.append(numero_formatado(numero))
    return list(dict.fromkeys(processos))


def salvar_json(caminho: Path, dados: Any) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def extrato_existente(pasta: Path) -> dict | None:
    caminho = pasta / "extrato.json"
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def consultar_e_baixar(numero: str, pasta: Path, limite_inspecao: int) -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    destino_pecas = pasta / "pecas"
    destino_pecas.mkdir(exist_ok=True)
    # A consulta e o download precisam compartilhar a mesma sessao para que
    # os tickets temporarios da pasta digital continuem validos.
    extrato = esaj.montar_extrato(
        numero,
        session=esaj.criar_session(),
        inspecionar_pecas=True,
        limite_inspecao_pecas=limite_inspecao,
        baixar_pecas=True,
        limite_pecas=0,
        pasta_pecas=destino_pecas,
    )
    salvar_json(pasta / "extrato.json", extrato)
    return extrato


def criar_manifesto(numero: str, pasta: Path, extrato: dict) -> dict:
    documentos = extrato.get("documentos", {})
    baixados = documentos.get("baixados", [])
    pendentes = [
        documento
        for documento in documentos.get("publicos_candidatos_unicos", [])
        if documento.get("download_status") not in {"baixado", "existente"}
    ]
    manifesto = {
        "processo": numero,
        "extrato": str(pasta / "extrato.json"),
        "total_baixados_ou_existentes": len(baixados),
        "arquivos": baixados,
        "documentos_restritos_ou_com_erro": pendentes,
    }
    salvar_json(pasta / "manifest.json", manifesto)
    return manifesto


def executar_processo(numero: str, destino: Path, limite_inspecao: int) -> dict:
    pasta = destino / numero
    manifesto_path = pasta / "manifest.json"
    if manifesto_path.exists():
        try:
            manifesto = json.loads(manifesto_path.read_text(encoding="utf-8"))
            if not manifesto.get("documentos_restritos_ou_com_erro"):
                return manifesto
        except json.JSONDecodeError:
            pass
    extrato = consultar_e_baixar(numero, pasta, limite_inspecao)
    return criar_manifesto(numero, pasta, extrato)


def principal() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", type=Path, help="Arquivo JSONL gerado pelo DataJud")
    parser.add_argument("--saida", type=Path, default=Path("dados/baixados"))
    parser.add_argument("--limite-inspecao", type=int, default=0)
    args = parser.parse_args()
    processos = ler_processos(args.entrada)
    args.saida.mkdir(parents=True, exist_ok=True)
    resumo = {"entrada": str(args.entrada), "total": len(processos), "processos": []}
    caminho_resumo = args.saida / "manifest.json"
    for indice, numero in enumerate(processos, 1):
        print(f"[{indice}/{len(processos)}] {numero}", flush=True)
        try:
            resultado = executar_processo(numero, args.saida, args.limite_inspecao)
        except (NanoJudError, OSError, ValueError, json.JSONDecodeError) as erro:
            resultado = {"processo": numero, "erro": str(erro)}
            print(f"  ERRO: {erro}", file=sys.stderr, flush=True)
        else:
            print(f"  {resultado['total_baixados_ou_existentes']} peca(s) baixada(s) ou existente(s)", flush=True)
        resumo["processos"].append(resultado)
        salvar_json(caminho_resumo, resumo)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
