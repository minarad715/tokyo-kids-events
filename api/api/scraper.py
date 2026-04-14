name: 毎日イベント自動取得

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:
    inputs:
      region:
        description: '地域（all/tokyo/kanagawa/saitama/chiba）'
        required: false
        default: 'all'

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

      - name: Python 3.12 をセットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: 必要なライブラリをインストール
        run: pip install requests beautifulsoup4 lxml

      - name: スクレイピング実行
        run: python api/api/scraper.py ${{ github.event.inputs.region || 'all' }}

      - name: events.json をコミット・プッシュ
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -f events.json events_kanagawa.json events_saitama.json events_chiba.json 2>/dev/null || true
          git diff --staged --quiet || git commit -m "🔄 イベント情報を自動更新 $(date +'%Y-%m-%d')"
          git push
