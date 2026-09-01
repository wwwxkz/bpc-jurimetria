import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# 1. Setup Model (Using Qwen 2.5 3B as it is fast and efficient for Portuguese)
model_name = "Qwen/Qwen2.5-3B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

pipe = pipeline("text-generation", model=model, tokenizer=tokenizer)

# 2. Define the prompt for the model
import pandas as pd

def classify_process_text(text):
    prompt = f"""Você é um agente especializado em analisar provas digitais em processos judiciais, comparando os procedimentos documentados nos autos com as recomendações e parâmetros da minuta do CNJ sobre provas digitais.

Objetivo: analisar exclusivamente os documentos disponíveis no processo e determinar se os procedimentos relacionados às provas digitais demonstram aderência aos parâmetros da CNJ.
Classificação obrigatória: 1 — Potencialmente Segue; 2 — Potencialmente Não Segue; 3 — Indecisivo.
Cadeia de custódia: verifique origem, identificação, coleta/extração, data, responsável, preservação, armazenamento, transferências, acessos, cópias, análises e documentação do ciclo da evidência.
Integridade: verifique hashes, cópias/imagens forenses, metadados, logs e outros mecanismos que permitam verificar que a evidência analisada corresponde ao material originalmente obtido.
Autenticidade e confiabilidade: avalie origem, contexto, método de obtenção, características técnicas, possibilidade de alteração e documentação disponível.
Método técnico: identifique ferramentas, versões, procedimentos e responsáveis pela extração ou processamento, verificando se há documentação suficiente para auditoria ou reprodução.
Auditabilidade: verifique laudos, relatórios, arquivos, logs, hashes e demais elementos necessários para permitir a verificação independente do procedimento.
Contraditório: verifique se existem elementos indicando que a defesa teve acesso às informações necessárias para questionar a origem, integridade, autenticidade e confiabilidade da prova.
Inconsistências: identifique divergências entre laudos, relatórios, mídias, hashes, datas, horários, metadados ou outros documentos que possam afetar a confiabilidade da evidência.
Não faça inferências: não considere um procedimento realizado apenas porque é usual ou tecnicamente recomendável; diferencie “não consta dos autos” de “foi demonstrado que não foi realizado”.
Regra de decisão: classifique como 1 quando houver evidências suficientes de aderência; 2 quando houver evidência objetiva de descumprimento ou fragilidade relevante; 3 quando as informações forem insuficientes ou inconclusivas.
Regra de cautela: a simples ausência de documentação não implica automaticamente classificação 2; quando não for possível determinar se o requisito foi cumprido ou descumprido, classifique como 3.
Rastreabilidade: baseie a análise exclusivamente nas evidências encontradas nos autos, sem inventar informações ou utilizar fatos externos ao processo.

Avaliação preliminar das mídias digitais: antes da classificação principal, verifique se existem mídias ou evidências digitais nos autos que se enquadrem no escopo das diretrizes e recomendações do CNJ para tratamento de provas digitais (tais como arquivos eletrônicos, conversas, mensagens, e-mails, registros de sistemas, mídias de armazenamento, capturas de tela, vídeos, áudios, dados extraídos de dispositivos ou serviços digitais). Registre a resposta como "Sim" ou "Não".

Impugnação da prova digital: caso existam mídias digitais enquadradas no item anterior, verifique se há manifestação expressa de qualquer das partes questionando a autenticidade, integridade, origem, autoria, confiabilidade, cadeia de custódia ou veracidade dessas evidências digitais. Considere contestações apresentadas em petições, manifestações, recursos, quesitos, pareceres técnicos ou outros documentos constantes dos autos. Registre a resposta como "Sim" ou "Não". A mera discordância quanto ao mérito dos fatos não deve ser considerada impugnação da prova digital, salvo quando houver questionamento específico sobre a própria evidência ou seu processo de obtenção, preservação ou análise.

Texto do processo: {text[:2000]}

Saída obrigatória:
MIDIAS_DIGITAIS: Sim ou Não
IMPUGNACAO_DA_PROVA_DIGITAL: Sim ou Não
CLASSIFICACAO: 1, 2 ou 3"""
    
    messages = [{"role": "user", "content": prompt}]
    # Increase max_new_tokens to allow for the three lines of output (Sim/Não, Sim/Não, 1/2/3)
    result = pipe(prompt, max_new_tokens=50, num_return_sequences=1, do_sample=False)
    generated_text = result[0]['generated_text']
    
    # Parse the output, initializing to None for NULL fallback
    media_digital = None
    impugnacao_digital = None
    classification = None

    # Extract values based on the expected format
    for line in generated_text.split('\n'):
        if "MIDIAS_DIGITAIS:" in line:
            media_digital = line.split("MIDIAS_DIGITAIS:")[1].strip()
        elif "IMPUGNACAO_DA_PROVA_DIGITAL:" in line:
            impugnacao_digital = line.split("IMPUGNACAO_DA_PROVA_DIGITAL:")[1].strip()
        elif "CLASSIFICACAO:" in line:
            classification = line.split("CLASSIFICACAO:")[1].strip()

    return media_digital, impugnacao_digital, classification


# 2. Folder and File Classification
root_folder = '/content/drive/MyDrive/ocr_export'
output_csv_path = '/content/drive/MyDrive/process_classification_results.csv'

batch_size = 10  # Define batch size

# Ensure root folder exists
if not os.path.exists(root_folder):
    print(f"Root folder {root_folder} not found. Please ensure it exists and contains process folders.")
else:
    # Load existing results if the CSV already exists
    existing_results_df = pd.DataFrame()
    if os.path.exists(output_csv_path):
        existing_results_df = pd.read_csv(output_csv_path)
        print(f"Loaded {len(existing_results_df)} existing results from {output_csv_path}")

    processed_ids = set(existing_results_df['Process ID'].tolist()) if not existing_results_df.empty else set()

    all_process_folders = [f for f in os.listdir(root_folder) if os.path.isdir(os.path.join(root_folder, f))]
    unprocessed_folders = [f for f in all_process_folders if f not in processed_ids]
    
    print(f"Found {len(all_process_folders)} total process folders. {len(unprocessed_folders)} are new/unprocessed.")

    for i in range(0, len(unprocessed_folders), batch_size):
        batch_folders = unprocessed_folders[i:i + batch_size]
        batch_results = []
        
        print(f"\nProcessing batch {i//batch_size + 1}/{len(unprocessed_folders)//batch_size + 1} (Folders {i+1}-{min(i+batch_size, len(unprocessed_folders))})")

        for process_folder_name in batch_folders:
            process_folder_path = os.path.join(root_folder, process_folder_name)
            
            combined_text = []
            # Read all .txt files in the process folder
            for file_name in os.listdir(process_folder_path):
                if file_name.endswith('.txt'):
                    file_path = os.path.join(process_folder_path, file_name)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            combined_text.append(f.read())
                    except Exception as e:
                        print(f"Error reading file {file_path}: {e}")
            
            full_process_text = "\n".join(combined_text)
            
            if full_process_text:
                media_digital, impugnacao_digital, classification = classify_process_text(full_process_text)
                batch_results.append({
                    "Process ID": process_folder_name,
                    "MIDIAS_DIGITAIS": media_digital,
                    "IMPUGNACAO_DA_PROVA_DIGITAL": impugnacao_digital,
                    "CLASSIFICACAO": classification
                })
                print(f"  Process: {process_folder_name} | MIDIAS_DIGITAIS: {media_digital} | IMPUGNACAO_DA_PROVA_DIGITAL: {impugnacao_digital} | CLASSIFICACAO: {classification}")
            else:
                # If no text, set all values to None
                batch_results.append({
                    "Process ID": process_folder_name,
                    "MIDIAS_DIGITAIS": None,
                    "IMPUGNACAO_DA_PROVA_DIGITAL": None,
                    "CLASSIFICACAO": None
                }) 
                print(f"  Process {process_folder_name} has no content to classify. Values set to NULL.")

        # Append batch results to CSV
        if batch_results:
            batch_df = pd.DataFrame(batch_results)
            if not os.path.exists(output_csv_path) or existing_results_df.empty:
                # If CSV doesn't exist or was empty, write with header
                batch_df.to_csv(output_csv_path, index=False, mode='w')
            else:
                # If CSV exists and had data, append without header
                batch_df.to_csv(output_csv_path, index=False, mode='a', header=False)
            print(f"  Batch results saved/appended to {output_csv_path}")
        else:
            print("  No new results in this batch to save.")

    print("\nAll specified process folders have been processed.")
    # Final check and display
    if os.path.exists(output_csv_path):
        final_df = pd.read_csv(output_csv_path)
        print(f"Total unique classified processes: {len(final_df['Process ID'].unique())}")
    else:
        print("No CSV file generated as no processes were classified.")