# Monitoramento e Transcrição de Áudio com AssemblyAI

Este projeto tem como objetivo monitorar uma pasta de uploads em busca de arquivos de áudio no formato `.wav` e realizar sua transcrição,análise de sentimento e resumos das ligações utilizando a API da AssemblyAI. O sistema verifica se o arquivo está estável (ou seja, se a gravação foi concluída) antes de iniciar a transcrição e organiza as transcrições em pastas baseadas no "ramal" extraído do caminho do arquivo.

## Funcionalidades

- **Monitoramento de Pasta:** Utiliza a biblioteca `watchdog` para detectar novos arquivos `.wav` na pasta de uploads.
- **Verificação de Estabilidade do Arquivo:** Aguarda e verifica se o arquivo de áudio está finalizado antes de iniciar a transcrição.
- **Transcrição com AssemblyAI:** Realiza a transcrição do áudio utilizando a API da AssemblyAI com configurações personalizadas, incluindo suporte para labels de locutores e correções de ortografia.
- **Resumos com IA:** Realiza através da transcrição feita, um resumo da ligação direcionada pelo prompt feito a IA.
- **Análise de sentimento:** Realiza uma análise direcionada pelo prompt, sobre os sentimentos do atendente e do cliente durante toda a conversa.
- **Retentativas Automatizadas:** Implementa um sistema de retentativas com delays configuráveis em caso de erros durante a transcrição.
- **Organização de Transcrições:** Salva as transcrições em arquivos `.txt`, organizando-os em subpastas com base no "ramal" (número extraído do diretório do arquivo de áudio).
- **Logs Detalhados:** Registra informações e erros tanto em um arquivo de log quanto no console.

## Pré-requisitos

- **Python 3.7+**
- **Bibliotecas Python:**
  - `watchdog`
  - `assemblyai`
  - Outras bibliotecas padrão (`os`, `time`, `threading`, `queue`, `logging`)

## Instalação

1. **Clone o repositório:**

   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd <NOME_DO_REPOSITORIO>
Crie e ative um ambiente virtual (opcional, mas recomendado):

bash
Copiar
Editar
python -m venv venv
# No Linux/MacOS:
source venv/bin/activate
# No Windows:
venv\Scripts\activate
Instale as dependências necessárias:
pip install watchdog assemblyai

# Tutorial
No início do script, configure os caminhos de Uploads e Transcrições:
UPLOAD_FOLDER = ""
TRANSCRICOES_FOLDER = ""
Certifique-se de que as pastas existem ou que o script tenha permissão para criá-las.

API Key da AssemblyAI:
Substitua a string "API_KEY" pela sua chave de API da AssemblyAI:
API_KEY = ""
**Para o funcionamento desse código, a análise de sentimento e resumos serão necessarios uma versão paga da API**.

Parâmetros de Retentativa:
Ajuste as variáveis conforme necessário:
MAX_RETRIES = 3      # Número máximo de tentativas para cada etapa
RETRY_DELAY = 30     # Tempo de espera (em segundos) entre as tentativas

Customização de Ortografia:
O código inclui uma configuração para corrigir interpretações errôneas de palavras (ex.: "Arroba" para "@", "Pharma" para "Farma", etc.):

config.set_custom_spelling({
    "@": ["Arroba"],
})

Enquanto o script estiver em execução:

Ele monitora a pasta definida em UPLOAD_FOLDER por novos arquivos .wav.
Ao detectar um arquivo válido (que contenha as pré-definições no nome), inicia um processo em background para:
Verificar se o arquivo está estável.
Realizar a transcrição, análise de sentimento e resumo via AssemblyAI.
Salvar a transcrição em um arquivo .txt dentro da pasta TRANSCRICOES_FOLDER, organizando por "ramal".
Para interromper o monitoramento, pressione Ctrl+C.
