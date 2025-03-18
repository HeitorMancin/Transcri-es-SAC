import os
import time
import threading
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import assemblyai as aai
from time import sleep

# Configurações
UPLOAD_FOLDER = "C://Users//hmancini//OneDrive - Biolab Sanus Farmaceutica Ltda//Área de Trabalho//uploads" 
#UPLOAD_FOLDER = "//ssac01//Gravacoes"
TRANSCRICOES_FOLDER = "C://Users//hmancini//OneDrive - Biolab Sanus Farmaceutica Ltda//Área de Trabalho//transcricoes"
API_KEY = "b32c5d8625d74cc4ade5ed68a37e255b"
LOG_FILE = "transcription_log.txt"
MAX_RETRIES = 3  # Número máximo de tentativas para cada etapa
RETRY_DELAY = 30  # Tempo de espera entre tentativas em segundos

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

# Dicionário para rastrear arquivos em processamento
arquivos_em_processamento = {}

def extrair_ramal_pasta(caminho_audio):
    caminho_absoluto = os.path.dirname(caminho_audio)
    ramal = os.path.basename(caminho_absoluto)
    return ramal if ramal.isdigit() else None

def arquivo_estavel(caminho_audio):
    try:
        if not os.path.exists(caminho_audio):
            return False
            
        tamanho_inicial = os.path.getsize(caminho_audio)
        time.sleep(80)
        
        if not os.path.exists(caminho_audio):
            return False
            
        tamanho_atual = os.path.getsize(caminho_audio)
        estavel = tamanho_inicial == tamanho_atual
        
        if estavel:
            logging.info(f"Arquivo estável, transcrevendo: {caminho_audio}")
        else:
            logging.info(f"Arquivo ainda em gravação: {caminho_audio}")
        
        return estavel
    except Exception as e:
        logging.error(f"Erro ao verificar estabilidade: {str(e)}")
        return False

def tentar_transcricao(transcriber, caminho_audio, config):
    for tentativa in range(MAX_RETRIES):
        try:
            return transcriber.transcribe(caminho_audio, config)
        except Exception as e:
            if tentativa < MAX_RETRIES - 1:
                logging.warning(f"Tentativa {tentativa + 1} falhou: {str(e)}. Tentando novamente...")
                sleep(RETRY_DELAY)
            else:
                raise

def transcrever_audio(caminho_audio, ramal):
    try:
        logging.info(f"Transcrevendo: {caminho_audio} (RAMAL: {ramal})")
        transcriber = aai.Transcriber()

        # Configuração básica para transcrição
        config = aai.TranscriptionConfig(
            language_code ="pt", 
            speaker_labels = True 
        )

        # Configuração de ortografia personalizada
        config.set_custom_spelling({
            "@": ["Arroba"],
            "Avert": ["Aberti", "Averti", "Aberte", "Averte", "Abilab"],
            "Farma": ["Pharma"],
            "Biolab": ["abelab"]
        })

        # Ativa LeMur com prompt padrão
        transcript = tentar_transcricao(transcriber, caminho_audio, config)
        prompt = """Faça um resumo e uma análise de sentimentos da transcrição,
                    Faça também um resumo dos sentimentos gerais de cada pessoa na ligação"""

        if transcript.status == aai.TranscriptStatus.error:
            logging.error(f"Erro na transcrição: {transcript.error}")
            return

        nome_arquivo_audio = os.path.basename(caminho_audio)
        nome_arquivo_transcricao = os.path.splitext(nome_arquivo_audio)[0] + ".txt"
        pasta_ramal = os.path.join(TRANSCRICOES_FOLDER, ramal)
        os.makedirs(pasta_ramal, exist_ok=True)
        caminho_transcricao = os.path.join(pasta_ramal, nome_arquivo_transcricao)

        if "vmail" in nome_arquivo_audio.lower():
            speaker_mapping = {"B": "Cliente"}
        else:
            speaker_mapping = {"A": "Atendente", "B": "Cliente"}

        with open(caminho_transcricao, "w", encoding='utf-8') as f:
            try:
                if hasattr(transcript, 'lemur') and transcript.lemur:
                    f.write("ANÁLISE LEMUR:\n")
                    result = transcript.lemur.task(
                        prompt, final_model=aai.LemurModel.claude3_5_sonnet
                    )
                    f.write(result.response + "\n")

            except Exception as lemur_error:
                logging.error(f"Erro ao processar Análise: {str(lemur_error)}")
                f.write("Não foi possível processar a análise para esta transcrição.\n\n")

            
            # Escreve a transcrição completa
            f.write("TRANSCRIÇÃO COMPLETA:\n")
            if hasattr(transcript, 'utterances') and transcript.utterances is not None:
                for utterance in transcript.utterances:
                    speaker_name = speaker_mapping.get(utterance.speaker, utterance.speaker)
                    f.write(f"{speaker_name}: {utterance.text}\n")
            else:
                f.write(transcript.text if hasattr(transcript, 'text') else "Nenhuma fala encontrada na transcrição.")

        logging.info(f"Transcrição salva: (RAMAL {ramal}) {caminho_transcricao}")
    except Exception as e:
        logging.error(f"Erro durante a transcrição: {str(e)}")
    finally:
        # Independente de sucesso ou falha, remove o arquivo da lista de processamento
        if caminho_audio in arquivos_em_processamento:
            del arquivos_em_processamento[caminho_audio]

def verificar_estabilidade_e_transcrever(caminho_audio, ramal):
    # Verifica estabilidade do arquivo em um loop
    for _ in range(3):  # Tenta verificar até 3 vezes
        if arquivo_estavel(caminho_audio):
            # Inicia a transcrição quando o arquivo estiver estável
            transcrever_audio(caminho_audio, ramal)
            return
        time.sleep(30)  # Espera 30 segundos antes de tentar novamente
    
    # Se chegou aqui, o arquivo não estabilizou após várias tentativas
    logging.warning(f"Arquivo não estabilizou após múltiplas tentativas: {caminho_audio}")
    if caminho_audio in arquivos_em_processamento:
        del arquivos_em_processamento[caminho_audio]

class AudioHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".wav"):
            try:
                # Verifica se o arquivo já está sendo processado
                if event.src_path in arquivos_em_processamento:
                    return
                
                file_name = os.path.basename(event.src_path)
                ramal = extrair_ramal_pasta(event.src_path)
                
                # Verifica se o arquivo atende aos critérios para transcrição
                if ramal and ("SAC BIOLAB" in file_name or "SAUDE ANIMAL" in file_name or "vmail" in file_name.lower()):
                    logging.info(f"Arquivo detectado: {event.src_path} (Ramal: {ramal})")
                    
                    # Marca o arquivo como em processamento
                    arquivos_em_processamento[event.src_path] = True
                    
                    # Inicia uma thread para verificar estabilidade e transcrever
                    thread = threading.Thread(
                        target=verificar_estabilidade_e_transcrever,
                        args=(event.src_path, ramal),
                        daemon=True
                    )
                    thread.start()
                else:
                    logging.info(f"Arquivo inválido: {file_name}")
            except Exception as e:
                logging.error(f"Erro ao processar novo arquivo: {str(e)}")

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