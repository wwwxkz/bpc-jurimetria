# Jurimetria do BPC/LOAS na Justiça Federal

Protótipo de pipeline em Python para **coleta automatizada e análise jurimétrica de processos do Benefício de Prestação Continuada (BPC/LOAS)** nos cinco Tribunais Regionais Federais, a partir da API Pública do DataJud (CNJ).

Projeto de estudo em métodos computacionais aplicados a dados jurídicos, desenvolvido originalmente como complemento à formação do autor em mestrado acadêmico em Economia na UnB. Consulte o [projeto original](https://github.com/lucmolero/bpc-jurimetria-main).

Este fork é desenvolvido por **Marcelo Rodrigues Campos**, mestrando em Engenharia Informática e Tecnologia Web na *Universidade de Trás-os-Montes e Alto Douro*, e continua a integração do pipeline com a coleta e o armazenamento de peças processuais públicas.

## O que o pipeline faz

1. **Coleta** (`src/coleta_datajud.py`) — consulta os índices públicos do DataJud dos TRF1–TRF5, inclusive Juizados Especiais Federais, com paginação via `search_after`, recuo exponencial em erros transitórios e gravação em JSONL.
2. **Análise** (`src/analise_metricas.py`) — consolida os dados em `pandas` e calcula, por tribunal, ano e grau, volume de ajuizamentos, duração mediana e desfecho das sentenças de mérito. Gera CSVs e gráficos.
3. **Consulta e download de peças** (`src/coleta_pecas.py`) — recebe processos coletados, gera extratos estruturados e baixa peças públicas disponibilizadas pela fonte, organizando os arquivos por processo e mantendo manifestos para retomada.

## Identificação dos assuntos de BPC

A maioria dos registros do DataJud traz apenas o código do assunto, sem o nome. Os códigos relevantes são:

| Código TPU | Assunto | Observação |
|---|---|---|
| 6114 | Benefício Assistencial (Art. 203,V CF/88) | código-pai |
| 11946 | Deficiente | filho de 6114 |
| 11947 | Idoso | filho de 6114 |

## Instalação

A instalação pode ser feita diretamente no ambiente Python em uso:

```bash
python -m pip install -r requirements.txt
```

O `nanojud` é necessário para consultar o eSAJ e obter extratos estruturados:

```bash
python -m pip install nanojud
nanojud --help
```

## Sequência de execução

Execute os comandos a partir da pasta `bpc-jurimetria-main`.

### 1. Coleta

Consulte o DataJud e gere os arquivos JSONL:

```bash
python src/coleta_datajud.py --saida dados/
```

Por padrão, a coleta consulta TRF1 a TRF5. Os tribunais e a quantidade máxima de registros podem ser definidos com `--tribunais` e `--max-por-tribunal`.

### 2. Análise

Gere métricas, tabelas e figuras a partir dos dados coletados:

```bash
python src/analise_metricas.py --entrada dados/ --saida dados/
```

### 3. Extrato e download de peças

O downloader recebe qualquer arquivo JSONL produzido pela coleta e executa consulta e download em uma única etapa:

```bash
python src/coleta_pecas.py dados/bpc_trf1.jsonl
```

A execução é retomável. Processos com manifesto concluído não são refeitos. Cada processo ainda pendente é consultado novamente para obter tickets válidos da fonte. Documentos protegidos por senha, captcha ou outras restrições não são acessados.

## Organização das peças

```text
dados/baixados/
  manifest.json
  10024397720238260416/
    extrato.json
    manifest.json
    pecas/
      peca_96067722_*.pdf
```

O manifesto de cada processo registra os arquivos baixados e os documentos restritos ou que falharam. O manifesto geral é atualizado após cada processo, permitindo interromper e continuar a execução.

No eSAJ, o download usa a mesma sessão HTTP que gerou os tickets temporários da pasta digital. Copiar apenas `url_final` ou abrir o link em uma sessão nova pode retornar "documento não autorizado".

## Saídas

As etapas de análise geram em `dados/`: `processos_bpc.csv`, `metricas_resumo.csv`, `metricas_desfechos.csv`, `frequencia_movimentos.csv` e `figuras/*.png`.

## LGPD

A API pública do DataJud expõe metadados processuais pseudonimizados, como classe, assunto, órgão julgador e movimentos. Ela não fornece nomes de partes nem documentos pessoais ao pipeline de coleta.

O `nanojud` é usado para consultar o eSAJ e obter extratos estruturados. Quando a fonte disponibiliza peças públicas, o downloader pode salvar os PDFs correspondentes. Documentos protegidos por senha, captcha ou outras restrições de acesso não são contornados nem coletados; esses casos são registrados no manifesto.

Extratos e manifestos podem conter informações processuais mais detalhadas, inclusive nomes de partes e advogados quando fornecidos pela fonte. O armazenamento, uso, compartilhamento e eventual publicação desses dados devem observar a LGPD, as políticas do tribunal e a finalidade da pesquisa. Recomenda-se restringir o acesso à pasta de dados e evitar publicar identificadores pessoais sem base legal adequada.

## Limitações conhecidas

- O índice público reflete processos com movimentação recente e carga histórica heterogênea entre tribunais.
- A amostra coletada não é necessariamente probabilística; as métricas devem ser interpretadas de acordo com a cobertura da fonte.
- O eSAJ pode exigir senha, captcha ou bloquear temporariamente consultas. O manifesto registra esses casos sem tentar contornar a restrição.
- A API Pública do DataJud não fornece o inteiro teor das decisões.

## Próximos passos

- Raspagem do inteiro teor nas bases de jurisprudência dos TRFs.
- Armazenamento estruturado e vetorial para recuperação de documentos.
- Desagregação por tipo de representação e cruzamento com registros administrativos, observando a legislação aplicável.
