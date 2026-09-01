# Jurimetria do BPC/LOAS na Justiça Federal

Este repositório implementa um pipeline de coleta, preservação e análise documental de processos do Benefício de Prestação Continuada (BPC/LOAS), com foco na presença de provas digitais, referências a mídias eletrônicas, documentos anexados e indicadores de cadeia de custódia em peças processuais públicas.

O fluxo atual combina:

1. coleta de metadados públicos do DataJud e do eSAJ;
2. preservação local dos PDFs das peças;
3. extração de texto por PDF e OCR para peças digitalizadas;
4. classificação por modelo de linguagem local, em modo conservador e auditável;
5. consolidação em relatórios e gráficos para análise jurimétrica.

## Estrutura do projeto

```text
bpc-jurimetria/
├── dados/
├── files/
├── paper/
├── src/
│   ├── coleta_datajud.py
│   ├── coleta_pecas.py
│   ├── analise_metricas.py
│   ├── ocr_pecas_colab.py
│   └── ...
├── README.md
├── requirements.txt
└── .gitignore
```

## Scripts principais

- `src/coleta_datajud.py`: consulta a API pública do DataJud e grava processos em JSONL.
- `src/coleta_pecas.py`: baixa e organiza as peças públicas por processo, preservando extratos e manifestos.
- `src/analise_metricas.py`: produz métricas, CSVs e imagens a partir dos dados coletados.
- `src/ocr_pecas_colab.py`: converte PDFs de peças em texto OCR para uso em ambiente Colab ou análise local.

## Dependências e instalação

Instale as dependências do projeto a partir da raiz:

```bash
python -m pip install -r requirements.txt
```

Dependências principais:

- `requests` para acesso à API pública do CNJ/DataJud;
- `pandas` e `matplotlib` para métricas e gráficos;
- `pytesseract` e `pdf2image` para OCR de peças;
- `nanojud` para consulta e download de peças do eSAJ;
- `transformers`, `torch`, `accelerate` e `sentencepiece` para o pipeline LLM local, quando usado.

## Execução

### 1. Coleta de processos

```bash
python src/coleta_datajud.py --saida dados/
```

### 2. Download das peças

```bash
python src/coleta_pecas.py dados/bpc_trf1.jsonl
```

### 3. OCR das peças

```bash
python src/ocr_pecas_colab.py --input files --output ocr_export --dpi 300 --lang por
```

### 4. Análise de métricas

```bash
python src/analise_metricas.py --entrada dados/ --saida dados/
```

## Organização de dados

A estrutura esperada para o armazenamento local é:

```text
files/
  00000000000000000000/
    extrato.json
    manifest.json
    pecas/
      peca_0001_arquivo.pdf
      peca_0002_arquivo.pdf
```

O OCR exporta a seguinte estrutura:

```text
ocr_export/
  manifest.json
  README.md
  process_00000000000000000000/
    piece_0001_arquivo.pdf.txt
    piece_0002_arquivo.pdf.txt
```

## LGPD e limitações

A API pública do DataJud expõe metadados processuais, não o conteúdo completo das decisões nem dados pessoais sensíveis. A coleta e o OCR das peças devem obedecer às regras de proteção de dados e ao uso autorizado dos arquivos públicos.

Limitações conhecidas:

- a amostra coletada não é necessariamente probabilística;
- o eSAJ pode bloquear ou exigir autenticação em alguns casos;
- o OCR pode falhar em imagens muito escaneadas ou com baixa legibilidade;
- a análise documental não substitui perícia forense ou valoração judicial.

## Observações finais

Este projeto é um pipeline de pesquisa e auditoria documental, com foco em reprodutibilidade e transparência metodológica. A classificação final é feita de forma conservadora e documentada, priorizando rastreabilidade e interpretação jurídica cautelosa sobre automações excessivas.
