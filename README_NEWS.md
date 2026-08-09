Pipeline de notícias (IA + Bing ou DuckDuckGo gratuita)

Instruções rápidas:

1. Se quiser usar o Bing Search API, crie uma chave no Azure Cognitive Services.
2. Exporte a variável de ambiente:

```bash
export BING_API_KEY="sua_chave_aqui"
```

3. Instale dependências:

```bash
python3 -m pip install -r requirements.txt
```

4. Rode o coletor:

```bash
python3 scripts/fetch_bing_news.py
```

Se não houver chave `BING_API_KEY`, o script usará a pesquisa gratuita do DuckDuckGo como fallback.

Isso gerará `data/news.json` e colocará imagens em `assets/images/` quando disponíveis.

No frontend, `index.html` já tenta carregar `data/news.json` automaticamente.
