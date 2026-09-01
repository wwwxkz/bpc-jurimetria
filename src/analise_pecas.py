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
def classify_process_text(text):
    prompt = f"""Você é um agente especializado em analisar provas digitais em processos judiciais, comparando os procedimentos documentados nos autos com as recomendações e parâmetros da minuta do CNJ sobre provas digitais.

Objetivo: analisar exclusivamente os documentos disponíveis no processo e determinar se os procedimentos relacionados às provas digitais demonstram aderência aos parâmetros da minuta do CNJ.
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
Saída obrigatória: responda somente com o número da classificação: 1, 2 ou 3.

Texto do processo: {text[:2000]}

Responda apenas o número da categoria:"""
    
    messages = [{"role": "user", "content": prompt}]
    result = pipe(prompt, max_new_tokens=2, num_return_sequences=1, do_sample=False)
    generated_text = result[0]['generated_text']
    classification = generated_text.strip()[-1] 
    if classification.isdigit():
        return classification
    else:
        for char in generated_text:
            if char.isdigit():
                return char
        return "3"

# 3. File Classification
file_path = '/home/test.txt' # The file specified by the user

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    if file_content:
        classification = classify_process_text(file_content)
        print(f"File: {file_path} | Classification: {classification}")
    else:
        print(f"File {file_path} is empty. Cannot classify.")
else:
    print(f"File {file_path} not found. Please ensure the file exists.")