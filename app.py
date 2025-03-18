import os
import time
import threading
import queue
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import assemblyai as aai
from time import sleep

# Configurações
UPLOAD_FOLDER = "" # Pasta que irá monitorar os áudios novos
TRANSCRICOES_FOLDER = "" # Pasta onde irá salvar as transcrições
API_KEY = "" # Sua chave de API aqui
LOG_FILE = "transcription_log.txt"
MAX_RETRIES = 3  # Número máximo de tentativas para cada etapa
RETRY_DELAY = 20  # Tempo de espera entre tentativas em segundos

# Configuração da API AssemblyAI
aai.settings.api_key = API_KEY

# Garante que a pasta de transcrições exista
os.makedirs(TRANSCRICOES_FOLDER, exist_ok=True)

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)

def extrair_ramal_pasta(caminho_audio):
    caminho_absoluto = os.path.dirname(caminho_audio)
    ramal = os.path.basename(caminho_absoluto)
    return ramal if ramal.isdigit() else None

def arquivo_estavel(caminho_audio):
    try:
        if not os.path.exists(caminho_audio):
            return False
            
        tamanho_inicial = os.path.getsize(caminho_audio)
        time.sleep(100)  # Pausa para verificar mudanças
        
        if not os.path.exists(caminho_audio):
            return False
            
        tamanho_atual = os.path.getsize(caminho_audio)
        return tamanho_inicial == tamanho_atual
    except Exception as e:
        logging.error(f"Erro ao verificar estabilidade do arquivo {caminho_audio}: {str(e)}")
        return False

def tentar_transcricao(transcriber, caminho_audio, config):
    #Função auxiliar para tentar transcrever com retentativas
    for tentativa in range(MAX_RETRIES):
        try:
            return transcriber.transcribe(caminho_audio, config)
        except Exception as e:
            if tentativa < MAX_RETRIES - 1:
                logging.warning(f"Tentativa {tentativa + 1} falhou. Erro: {str(e)}. Aguardando {RETRY_DELAY} segundos antes de tentar novamente...")
                sleep(RETRY_DELAY)
            else:
                raise

def transcrever_audio(caminho_audio, ramal):
    try:
        logging.info(f"Transcrevendo: {caminho_audio} (RAMAL: {ramal})")
        transcriber = aai.Transcriber()
        config = aai.TranscriptionConfig(language_code="pt", 
                                         speaker_labels=True)
        config.set_custom_spelling({
            "@": ["Arroba"],
        }) # Customização de ortografia

        # Ativa LeMur com prompt padrão
        transcript = tentar_transcricao(transcriber, caminho_audio, config)
        prompt = """Faça um resumo e uma análise de sentimentos da transcrição,
                    Faça também um resumo dos sentimentos de cada pessoa na ligação"""

        # Tenta transcrever com sistema de retentativas
        transcript = tentar_transcricao(transcriber, caminho_audio, config)

        if transcript.status == aai.TranscriptStatus.error:
            logging.error(f"Erro na transcrição: {transcript.error}")
            logging.warning(f"Arquivo {caminho_audio} foi pulado após falhas na transcrição.")
            return

        nome_arquivo_audio = os.path.basename(caminho_audio)
        nome_arquivo_transcricao = os.path.splitext(nome_arquivo_audio)[0] + ".txt"
        pasta_ramal = os.path.join(TRANSCRICOES_FOLDER, ramal)
        os.makedirs(pasta_ramal, exist_ok=True)
        caminho_transcricao = os.path.join(pasta_ramal, nome_arquivo_transcricao)

        if "vmail" in nome_arquivo_audio.lower(): # Áudios na caixa postal
            speaker_mapping = {"B":"Cliente"}
        else:
            speaker_mapping = {"A": "Atendente", "B": "Cliente"}

        with open(caminho_transcricao, "w", encoding='utf-8') as f:
            try:
                if hasattr(transcript, 'lemur') and transcript.lemur:
                    f.write("\n")
                    result = transcript.lemur.task(
                        prompt, final_model=aai.LemurModel.claude3_5_sonnet
                    )
                    f.write(result.response + "\n")

            except Exception as lemur_error:
                logging.error(f"Erro ao processar Análise: {str(lemur_error)}")
                f.write("Não foi possível processar a análise para esta transcrição.\n\n")

            # Escreve a transcrição completa
            f.write("\nTRANSCRIÇÃO COMPLETA:\n")
            if hasattr(transcript, 'utterances') and transcript.utterances is not None:
                for utterance in transcript.utterances:
                    speaker_name = speaker_mapping.get(utterance.speaker, utterance.speaker)
                    f.write(f"{speaker_name}: {utterance.text}\n")
            else:
                f.write(transcript.text if hasattr(transcript, 'text') else "Nenhuma fala encontrada na transcrição.")

            if transcript.utterances is not None:
                for utterance in transcript.utterances:
                    speaker_name = speaker_mapping.get(utterance.speaker, utterance.speaker)
                    f.write(f"{speaker_name}: {utterance.text}\n")
            else:
                f.write("Nenhuma fala encontrada na transcrição. Verifique o áudio e a configuração.")

        logging.info(f"Transcrição salva em: (RAMAL {ramal}) {caminho_transcricao}")
    except Exception as e:
        logging.error(f"Erro durante a transcrição do arquivo {caminho_audio}: {str(e)}")
        logging.warning(f"Arquivo {caminho_audio} foi pulado após falhas na transcrição.")

def monitorar_e_transcrever(caminho_audio, ramal):
    arquivo_em_mudanca = False
    while True:
        try:
            if arquivo_estavel(caminho_audio):
                logging.info(f"Arquivo estável detectado: {caminho_audio}")
                transcrever_audio(caminho_audio, ramal)
                break
            elif not arquivo_em_mudanca:
                logging.info(f"Arquivo ainda em gravação:{caminho_audio} (RAMAL: {ramal})")
                arquivo_em_mudanca = True
        except Exception as e:
            logging.error(f"Erro durante monitoramento do arquivo {caminho_audio}: {str(e)}")
            time.sleep(80)

class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".wav"):
            try:
                file_name = os.path.basename(event.src_path)
                ramal = extrair_ramal_pasta(event.src_path)
                if ramal and ("" in file_name or "" in file_name or "vmail" in file_name): # Filtro de árquivos
                    logging.info(f"Novo arquivo válido detectado: {event.src_path} (Ramal: {ramal})")
                    thread = threading.Thread(
                        target=monitorar_e_transcrever,
                        args=(event.src_path, ramal),
                        daemon=True
                    )
                    thread.start()
                else:
                    logging.info(f"Arquivo de áudio inválido ignorado: {file_name}")
            except Exception as e:
                logging.error(f"Erro ao processar novo arquivo {event.src_path}: {str(e)}")

if __name__ == "__main__":
    observer = Observer()
    observer.schedule(AudioHandler(), UPLOAD_FOLDER, recursive=True)
    observer.start()
    logging.info("Monitoramento iniciado...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Encerrando monitoramento...")
        observer.stop()
        observer.join()
        logging.info("Monitoramento encerrado...")
