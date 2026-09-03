import os
import torch
import pandas as pd

from transformers import (
    AutoTokenizer,
    AutoModelForMaskedLM,
    BitsAndBytesConfig
)


# ------------------------------------------------------------
# 3. LOAD LEGALBERT-PT FP
# ------------------------------------------------------------

MODEL_NAME = "raquelsilveira/legalbertpt_fp"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

model = AutoModelForMaskedLM.from_pretrained(
    MODEL_NAME,
    device_map="auto"
)

model.eval()

print("Model loaded successfully.")
print("Memory footprint:", model.get_memory_footprint(), "bytes")


# ------------------------------------------------------------
# 4. DEVICE
# ------------------------------------------------------------

device = next(model.parameters()).device

print("Device:", device)


# ------------------------------------------------------------
# 5. PREDICT A CLASS USING [MASK]
# ------------------------------------------------------------

def predict_digit(text, allowed_digits):

    # Tokenize
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512 # Model max input length
    )

    # Move tensors to model device
    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    # Find MASK
    mask_positions = (
        inputs["input_ids"] == tokenizer.mask_token_id
    ).nonzero(as_tuple=True)

    if len(mask_positions[0]) == 0:
        print("ERROR: [MASK] token not found.")
        return None

    mask_position = mask_positions[1][0]

    # Run model
    with torch.no_grad():
        outputs = model(**inputs)

    # Logits corresponding to MASK
    logits = outputs.logits[0, mask_position]

    candidates = []

    for digit in allowed_digits:

        token_ids = tokenizer.encode(
            digit,
            add_special_tokens=False
        )

        # Digit must correspond to exactly one token
        if len(token_ids) == 1:

            token_id = token_ids[0]

            score = logits[token_id].item()

            candidates.append(
                (digit, score)
            )

    if not candidates:
        return None

    # Highest score
    candidates.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return candidates[0][0]


# ------------------------------------------------------------
# Helper function for chunking long documents
# ------------------------------------------------------------
def chunk_document(text, tokenizer, max_doc_length_tokens=256, overlap=50):
    """
    Chunks a long text into smaller segments based on token length, with optional overlap.
    Returns a list of decoded text chunks.
    """
    tokenized_input = tokenizer(text, truncation=False, add_special_tokens=False)
    input_ids = tokenized_input["input_ids"]

    chunks = []
    start = 0
    while start < len(input_ids):
        end = min(start + max_doc_length_tokens, len(input_ids))
        chunk_ids = input_ids[start:end]
        decoded_chunk = tokenizer.decode(chunk_ids, skip_special_tokens=True)
        if decoded_chunk.strip(): # Add only non-empty chunks
            chunks.append(decoded_chunk)

        if end == len(input_ids): # Reached the end of the input
            break

        start += max_doc_length_tokens - overlap
        # Ensure start does not go backwards or stay the same if max_doc_length_tokens <= overlap
        if max_doc_length_tokens - overlap <= 0 and start < len(input_ids): # Avoid infinite loop
             start += max_doc_length_tokens # Move by full chunk size if overlap is too large

    return chunks


# ------------------------------------------------------------
# 6. CLASSIFY ONE PROCESS
# ------------------------------------------------------------

def classify_process_text(text):

    # Lists to store results from each chunk
    all_media_digital_results = []
    all_impugnacao_digital_results = []
    all_classification_results = []

    # Chunk the document
    # Max document length for individual classification is 256 tokens.
    # The total model max_length is 512, so prompt + document = 512.
    # The prompt length is approx 250-260 tokens, leaving 256 for the document.
    document_chunks = chunk_document(text, tokenizer, max_doc_length_tokens=256, overlap=50)

    if not document_chunks:
        # Handle case where no chunks could be generated (e.g., empty text)
        print("No document chunks generated from the text. Returning None for all classifications.")
        return None, None, None

    for i, document_chunk in enumerate(document_chunks):
        # Skip empty chunks
        if not document_chunk.strip():
            continue

        # ========================================================
        # 1. MÍDIAS DIGITAIS
        # ========================================================

        prompt_media = f"""
Você está analisando um processo judicial brasileiro.

Determine se existem mídias ou evidências digitais nos documentos fornecidos.

Exemplos:
arquivos eletrônicos, conversas, mensagens, e-mails, registros de sistemas,
mídias de armazenamento, capturas de tela, vídeos, áudios, dados extraídos
de dispositivos ou serviços digitais.

Não faça inferências.
Considere exclusivamente o texto fornecido.

0 = Não há evidência de mídia digital.
1 = Há evidência de mídia digital.

Texto do processo:

{document_chunk}

Resposta: {tokenizer.mask_token}
"""

        media_digital = predict_digit(
            prompt_media,
            ["0", "1"]
        )
        all_media_digital_results.append(media_digital)


        # ========================================================
        # 2. IMPUGNAÇÃO DA PROVA DIGITAL
        # ========================================================

        prompt_impugnacao = f"""
Você está analisando um processo judicial brasileiro.

Determine se alguma das partes apresentou manifestação expressamente
questionando uma prova digital quanto à autenticidade, integridade, origem,
autoria, confiabilidade, cadeia de custódia ou veracidade.

Considere petições, manifestações, recursos, quesitos, pareceres técnicos
ou outros documentos.

A mera discordância sobre os fatos não é impugnação da prova digital.

Não faça inferências.
Considere exclusivamente o texto fornecido.

0 = Não há impugnação específica de prova digital.
1 = Há impugnação específica de prova digital.

Texto do processo:

{document_chunk}

Resposta: {tokenizer.mask_token}
"""

        impugnacao_digital = predict_digit(
            prompt_impugnacao,
            ["0", "1"]
        )
        all_impugnacao_digital_results.append(impugnacao_digital)


        # ========================================================
        # 3. CLASSIFICAÇÃO PRINCIPAL
        # ========================================================

        prompt_classificacao = f"""
Você é um especialista em provas digitais no processo judicial brasileiro.

Analise exclusivamente as informações presentes no texto.

Avalie:

- cadeia de custódia;
- origem e identificação da evidência;
- coleta ou extração;
- datas e responsáveis;
- preservação e armazenamento;
- transferências e acessos;
- cópias e análises;
- hashes e integridade;
- imagens forenses;
- metadados e logs;
- autenticidade;
- método e ferramentas utilizadas;
- documentação;
- auditabilidade;
- contraditório;
- inconsistências entre documentos.

Não faça inferências.

A ausência de documentação não significa automaticamente descumprimento.

Diferencie:
"não consta dos autos"
de
"foi demonstrado que não foi realizado".

Classificação:

1 = Potencialmente Segue.
Existem evidências suficientes de aderência aos parâmetros.

2 = Potencialmente Não Segue.
Existe evidência objetiva de descumprimento ou fragilidade relevante.

3 = Indecisivo.
As informações são insuficientes ou inconclusivas.

Baseie-se exclusivamente no texto fornecido.

Texto do processo:

{document_chunk}

Classificação: {tokenizer.mask_token}
"""

        classification = predict_digit(
            prompt_classificacao,
            ["1", "2", "3"]
        )
        all_classification_results.append(classification)


    # --- Aggregation Logic ---
    # For binary (0/1) classifications, if any chunk is '1', the whole document is '1'.
    final_media_digital = '0'
    if '1' in all_media_digital_results:
        final_media_digital = '1'

    final_impugnacao_digital = '0'
    if '1' in all_impugnacao_digital_results:
        final_impugnacao_digital = '1'

    # For 1/2/3 classification, prioritize '2' > '3' > '1'
    final_classification = None
    if '2' in all_classification_results:
        final_classification = '2'
    elif '3' in all_classification_results:
        final_classification = '3'
    elif '1' in all_classification_results:
        final_classification = '1'
    # If all were None or list was empty, it remains None

    print(
        "\n"
        f"MIDIAS_DIGITAIS: {final_media_digital}\n"
        f"IMPUGNACAO_DA_PROVA_DIGITAL: {final_impugnacao_digital}\n"
        f"CLASSIFICACAO: {final_classification}\n"
    )

    return (
        final_media_digital,
        final_impugnacao_digital,
        final_classification
    )


# ------------------------------------------------------------
# 7. FOLDERS / OUTPUT
# ------------------------------------------------------------

root_folder = "/content/drive/MyDrive/ocr_export"

output_csv_path = (
    "/content/drive/MyDrive/"
    "process_classification_results.csv"
)

batch_size = 10


# ------------------------------------------------------------
# 8. CHECK ROOT FOLDER
# ------------------------------------------------------------

if not os.path.exists(root_folder):

    print(
        f"ERROR: Folder not found:\n{root_folder}"
    )

else:

    # --------------------------------------------------------
    # LOAD EXISTING RESULTS
    # --------------------------------------------------------

    existing_results_df = pd.DataFrame()

    if os.path.exists(output_csv_path):

        existing_results_df = pd.read_csv(
            output_csv_path
        )

        print(
            f"Loaded "
            f"{len(existing_results_df)} "
            f"existing results."
        )


    # --------------------------------------------------------
    # PROCESSED IDS
    # --------------------------------------------------------

    if (
        not existing_results_df.empty
        and "Process ID" in existing_results_df.columns
    ):

        processed_ids = set(
            existing_results_df["Process ID"]
            .astype(str)
            .tolist()
        )

    else:

        processed_ids = set()


    # --------------------------------------------------------
    # FIND PROCESS FOLDERS
    # --------------------------------------------------------

    all_process_folders = [
        folder
        for folder in os.listdir(root_folder)
        if os.path.isdir(
            os.path.join(root_folder, folder)
        )
    ]

    unprocessed_folders = [
        folder
        for folder in all_process_folders
        if folder not in processed_ids
    ]


    print(
        f"Found {len(all_process_folders)} "
        f"total process folders."
    )

    print(
        f"{len(unprocessed_folders)} "
        f"are new/unprocessed."
    )


    # ========================================================
    # 9. PROCESS BATCHES
    # ========================================================

    for i in range(
        0,
        len(unprocessed_folders),
        batch_size
    ):

        batch_folders = unprocessed_folders[
            i:i + batch_size
        ]

        batch_results = []

        batch_number = (
            i // batch_size
        ) + 1

        total_batches = (
            len(unprocessed_folders)
            + batch_size
            - 1
        ) // batch_size

        print(
            "\n"
            f"====================================\n"
            f"BATCH {batch_number}/{total_batches}\n"
            f"===================================="
        )


        # ----------------------------------------------------
        # PROCESS EACH FOLDER
        # ----------------------------------------------------

        for process_folder_name in batch_folders:

            process_folder_path = os.path.join(
                root_folder,
                process_folder_name
            )

            print(
                f"\nProcessing: "
                f"{process_folder_name}"
            )


            # ------------------------------------------------
            # READ TXT FILES
            # ------------------------------------------------

            combined_text = []

            for file_name in os.listdir(
                process_folder_path
            ):

                if file_name.lower().endswith(".txt"):

                    file_path = os.path.join(
                        process_folder_path,
                        file_name
                    )

                    try:

                        with open(
                            file_path,
                            "r",
                            encoding="utf-8"
                        ) as f:

                            combined_text.append(
                                f.read()
                            )

                    except Exception as e:

                        print(
                            f"Error reading "
                            f"{file_path}: {e}"
                        )


            full_process_text = "\n".join(
                combined_text
            )


            # ------------------------------------------------
            # CLASSIFY
            # ------------------------------------------------

            if full_process_text.strip():

                try:

                    (
                        media_digital,
                        impugnacao_digital,
                        classification
                    ) = classify_process_text(
                        full_process_text
                    )

                except Exception as e:

                    print(
                        f"ERROR processing "
                        f"{process_folder_name}: {e}"
                    )

                    media_digital = None
                    impugnacao_digital = None
                    classification = None


                batch_results.append({

                    "Process ID":
                        process_folder_name,

                    "MIDIAS_DIGITAIS":
                        media_digital,

                    "IMPUGNACAO_DA_PROVA_DIGITAL":
                        impugnacao_digital,

                    "CLASSIFICACAO":
                        classification
                })


                print(
                    f"RESULT: "
                    f"{media_digital} | "
                    f"{impugnacao_digital} | "
                    f"{classification}"
                )


            # ------------------------------------------------
            # EMPTY PROCESS
            # ------------------------------------------------

            else:

                batch_results.append({

                    "Process ID":
                        process_folder_name,

                    "MIDIAS_DIGITAIS":
                        None,

                    "IMPUGNACAO_DA_PROVA_DIGITAL":
                        None,

                    "CLASSIFICACAO":
                        None
                })

                print(
                    "No text found. "
                    "Values set to NULL."
                )


        # ====================================================
        # 10. SAVE BATCH
        # ====================================================

        if batch_results:

            batch_df = pd.DataFrame(
                batch_results
            )

            file_exists = os.path.exists(
                output_csv_path
            )

            if not file_exists:

                batch_df.to_csv(
                    output_csv_path,
                    index=False,
                    mode="w"
                )

            else:

                batch_df.to_csv(
                    output_csv_path,
                    index=False,
                    mode="a",
                    header=False
                )

            print(
                f"\nBatch saved to:\n"
                f"{output_csv_path}"
            )


    # ========================================================
    # 11. FINAL RESULT
    # ========================================================

    if os.path.exists(
        output_csv_path
    ):

        final_df = pd.read_csv(
            output_csv_path
        )

        print(
            "\n===================================="
        )

        print(
            "PROCESSING COMPLETE"
        )

        print(
            f"Total rows: {len(final_df)}"
        )

        print(
            "Unique processes:",
            final_df["Process ID"].nunique()
        )

        print(
            "\nClassification counts:"
        )

        print(
            final_df["CLASSIFICACAO"]
            .value_counts(dropna=False)
        )

        print(
            "\nCSV:"
        )

        print(
            output_csv_path
        )

    else:

        print(
            "No CSV generated."
        )