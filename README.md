# MídiaBUDA

Ferramenta amigável de edição de vídeo/áudio baseada em FFmpeg.

## Funcionalidades

- **Cortar** — recortar vídeos com precisão (entre, antes, depois)
- **Converter** — converter entre formatos (MP4, MKV, MOV, AVI, WebM, GIF)
- **Mesclar** — juntar múltiplos arquivos de mídia
- **Extrair Áudio** — extrair faixa de áudio em MP3, WAV, FLAC ou AAC
- **Comprimir** — reduzir tamanho do arquivo com controle de qualidade
- **Capturas de Tela** — quadro único, intervalo ou folha de contato
- **Redimensionar/Girar** — predefinições (1080p, 720p, Instagram, TikTok) e transformações
- **Prévia em Tempo Real** — visualizar quadros antes de processar
- **Linha do Tempo** — marcadores de início/fim com scrubber de prévia
- **Fila de Lotes** — adicionar múltiplos trabalhos e executar em sequência
- **Configurações de Exportação** — codec de vídeo/áudio, CRF, preset, bitrate, contêiner
- **Atualização Automática** — verificar e baixar novas versões pelo GitHub
- **Download Automático do FFmpeg** — baixa o FFmpeg na primeira execução

## Requisitos

- Python 3.10+
- PyQt6
- Pillow
- FFmpeg (baixado automaticamente)

## Instalação (desenvolvimento)

```bash
pip install pyqt6 pillow
python APP/main.py
```

## Build — Windows

```bat
pip install pyinstaller pyqt6 pillow
APP\build_windows.bat
```

O executável será gerado em `dist\MediaBUDA.exe`.

## Build — macOS

```bash
pip install pyinstaller pyqt6 pillow
bash APP/build_macos.sh
```

O aplicativo será gerado em `dist/MediaBUDA.app`.

## Testes

```bash
pip install pytest hypothesis
python -m pytest APP/tests/ -v --tb=short
```

## Licença

MIT
