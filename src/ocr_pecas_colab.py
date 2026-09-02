#!/usr/bin/env python3
"""Exporta textos OCR de peças em PDF para uma pasta pronta.

Estrutura de saída:
    ocr_export/
      README.md
      manifest.json
      process_<NUMERO_DO_PROCESSO>/
        piece_0001_peca_12345678_documento.pdf.txt
        piece_0002_peca_87654321_outra_peca.pdf.txt

O script percorre todas as pastas de peças do dataset, realiza OCR dos PDFs
usando pytesseract + pdf2image, salva cada peça em um arquivo de texto
separado e registra tudo em um manifesto JSON.

Uso local (Windows):
    python ocr_pecas_colab.py --input "C:\\path\\to\\files" --output "C:\\path\\to\\ocr_export"
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytesseract
from pdf2image import convert_from_path

def _processo_worker(
    processo_id: str,
    pdf_paths: list[str],
    output_dir: str,
    dpi: int,
    lang: str,
) -> list[dict[str, Any]]:
    output_dir_path = Path(output_dir)

    pasta_processo = output_dir_path / f"process_{processo_id}"
    pasta_processo.mkdir(parents=True, exist_ok=True)

    manifest_local: list[dict[str, Any]] = []

    total = len(pdf_paths)

    for indice_peca, pdf_str in enumerate(pdf_paths, start=1):
        pdf_path = Path(pdf_str)

        print(
            f"[{processo_id}] {indice_peca}/{total} {pdf_path.name}",
            flush=True,
        )

        paginas = extrair_texto_pdf(
            pdf_path,
            dpi=dpi,
            lang=lang,
        )

        texto_final = "\n\n".join(paginas)

        nome_slug = sanitizar_nome(pdf_path.stem)

        nome_arquivo = (
            f"piece_{indice_peca:04d}_{nome_slug}.txt"
        )

        destino = pasta_processo / nome_arquivo

        destino.write_text(
            texto_final,
            encoding="utf-8",
        )

        manifest_local.append(
            {
                "processo_id": processo_id,
                "processo_folder": f"process_{processo_id}",
                "piece_index": indice_peca,
                "piece_file": nome_arquivo,
                "piece_source_pdf": str(pdf_path),
                "source_pdf_name": pdf_path.name,
                "ocr_output_txt": str(
                    destino.relative_to(output_dir_path)
                ),
                "num_paginas": len(paginas),
                "num_caracteres": len(texto_final),
            }
        )

    return manifest_local

def sanitizar_nome(texto: str) -> str:
    texto = texto.strip().lower()
    texto = re.sub(r"[\\/]+", "_", texto)
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto or "peca"

def descobrir_pdf_paths(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {base_dir}")
    return sorted(base_dir.glob("**/pecas/*.pdf"))


def extrair_texto_pdf(pdf_path: Path, dpi: int = 300, lang: str = "por") -> list[str]:
    """Extrai OCR das páginas de um PDF e retorna uma lista de textos por página."""
    try:
        imagens = convert_from_path(str(pdf_path), dpi=dpi)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Erro ao rasterizar PDF '{pdf_path}': {exc}") from exc

    paginas: list[str] = []
    for idx, imagem in enumerate(imagens, start=1):
        try:
            texto = pytesseract.image_to_string(
                imagem,
                lang=lang,
                config="--psm 6 --oem 3",
            )
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Erro no OCR da página {idx} do PDF '{pdf_path}': {exc}") from exc
        paginas.append((f"--- PAGINA {idx} ---\n{texto.strip()}\n").strip())

    if not paginas:
        paginas.append("OCR_NAO_GEROU_TEXTO")

    return paginas

def exportar_pecas(
    input_dir: Path,
    output_dir: Path,
    dpi: int = 300,
    lang: str = "por",
    workers: int | None = None,
) -> dict[str, Any]:

    pdfs = descobrir_pdf_paths(input_dir)

    if not pdfs:
        raise FileNotFoundError(
            f"Nenhum PDF de peça encontrado em: {input_dir}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    workers = max(1, workers or 4)

    processos: dict[str, list[Path]] = defaultdict(list)

    for pdf in pdfs:
        processo_id = pdf.parent.parent.name
        processos[processo_id].append(pdf)

    manifest: list[dict[str, Any]] = []

    if workers == 1:

        for processo_id, pdfs_processo in processos.items():

            manifest.extend(
                _processo_worker(
                    processo_id=processo_id,
                    pdf_paths=[
                        str(p) for p in pdfs_processo
                    ],
                    output_dir=str(output_dir),
                    dpi=dpi,
                    lang=lang,
                )
            )

    else:

        with ProcessPoolExecutor(
            max_workers=workers
        ) as executor:

            futures = {
                executor.submit(
                    _processo_worker,
                    processo_id,
                    [str(p) for p in pdfs_processo],
                    str(output_dir),
                    dpi,
                    lang,
                ): processo_id
                for processo_id, pdfs_processo
                in processos.items()
            }

            for future in as_completed(futures):

                processo_id = futures[future]

                try:
                    manifest.extend(
                        future.result()
                    )

                    print(
                        f"[OK] Processo {processo_id}",
                        flush=True,
                    )

                except Exception as exc:

                    print(
                        f"[ERRO] Processo {processo_id}: {exc}",
                        flush=True,
                    )
                    raise

    manifest.sort(
        key=lambda item: (
            item["processo_id"],
            item["piece_index"],
        )
    )

    manifest_path = output_dir / "manifest.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    readme = output_dir / "README.md"

    readme.write_text(
        "# OCR das peças dos processos\n\n"
        "Esta pasta foi gerada com o script `ocr_pecas_colab.py`.\n\n"
        "- Cada processo recebe uma pasta chamada `process_<numero_do_processo>`.\n"
        "- Cada peça recebe um arquivo `piece_<numero>_<nome_da_peca>.txt`.\n"
        "- O arquivo `manifest.json` lista todos os PDFs originais e seus textos OCR exportados.\n\n"
        "Para usar, basta copiar essa pasta inteira para o ambiente e carregar os arquivos `.txt` com o modelo LLM.\n",
        encoding="utf-8",
    )

    return {
        "total_processos": len(processos),
        "total_pecas": len(manifest),
        "output_dir": str(output_dir),
        "manifest": str(manifest_path),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    raiz = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--input",
        type=Path,
        default=raiz / "files",
        help="Diretório que contém as pastas de processos e subpastas 'pecas'.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=raiz / "ocr_export",
        help="Diretório de saída com os textos OCR e o manifesto.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Resolução de rasterização do PDF para OCR (padrão: 300).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="por",
        help="Idioma do Tesseract para OCR (padrão: por).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Número de threads paralelas para OCR. Se não informado, usa 4.",
    )
    args = parser.parse_args()

    resumo = exportar_pecas(args.input, args.output, dpi=args.dpi, lang=args.lang, workers=args.workers)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
