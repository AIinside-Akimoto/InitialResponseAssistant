# 初動対応アシスタント

設備トラブルやインシデント発生時に、状況説明と関連ファイルをAIエージェントへ送信し、初動対応計画を表示する Streamlit アプリです。

## 特徴

- 設備種別を選択して問い合わせ可能
- ログ、スクリーンショット、設定ファイルなどの関連ファイルを添付可能
- AIエージェントの応答を以下の観点で整理して表示
  - 優先度
  - 想定原因
  - 初動対応案
  - 類似事例
  - エスカレーション
  - 根拠
- APIウォームアップにより初回レスポンス待ちを軽減

## 動作要件

- Python 3.10 以上推奨
- Windows / macOS / Linux
- 外部の AI エージェント API

## リポジトリ構成

```text
.
├─ app.py
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ LICENSE
├─ 初動対応アシスタント.bat
└─ .github/
   ├─ workflows/
   │  └─ python-smoke-test.yml
   ├─ ISSUE_TEMPLATE/
   │  ├─ bug_report.md
   │  └─ feature_request.md
   └─ pull_request_template.md
```

## セットアップ

### 1. クローン

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

### 2. 仮想環境の作成

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (cmd)**

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

## 環境変数

このアプリは以下の環境変数を使用します。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `API_BASE_URL` | 必須 | AIエージェントのベースURL |
| `API_KEY` | 必須 | `x-api-key` に設定するAPIキー |
| `API_TIMEOUT_SEC` | 任意 | APIタイムアウト秒数。未指定時は `120` |

`.env.example` を参考に設定してください。

### Windows の簡易実行

同梱の `初動対応アシスタント.bat` に `API_BASE_URL` と `API_KEY` を設定し、以下で起動できます。

```cmd
初動対応アシスタント.bat
```

## 起動方法

```bash
streamlit run app.py
```

起動後、ブラウザで Streamlit の画面が開きます。

## API 仕様の前提

アプリは以下のエンドポイントへ multipart/form-data でPOSTします。

- `POST {API_BASE_URL}/analyze-incident`

送信内容:

- `query`: テキスト
- `file`: 添付ファイル

## 想定レスポンス例

```json
{
  "priority": {
    "level": "重要",
    "reason": "生産影響が発生する可能性があるため"
  },
  "assumed_causes": {
    "technical": ["センサー異常", "通信断"],
    "operational": ["設定変更漏れ"]
  },
  "initial_response_plan": {
    "forbidden_actions": ["電源の即時再投入"],
    "immediate_actions": ["現場安全の確認"],
    "temporary_measures": ["代替ラインへの切り替え"],
    "parallel_investigations": ["直近ログの確認"]
  },
  "similar_cases_summary": {
    "summary": "過去に類似障害あり",
    "overview": "同型設備での発生事例",
    "cause_and_effect": "I/O接触不良が原因",
    "lessons_learned": ["配線固定の見直し"]
  },
  "escalation_point": {
    "role": "設備保全部門責任者",
    "trigger": "30分以内に復旧見込みが立たない場合"
  },
  "evidence": [
    {
      "source": "添付ログ",
      "detail": "E102 エラーが 10:31 に発生"
    }
  ]
}
```

## GitHub で公開する流れ

### 1. 新規リポジトリ作成

GitHub で空のリポジトリを作成します。

### 2. 初回コミット

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <YOUR_REPOSITORY_URL>
git push -u origin main
```

## セキュリティ上の注意

- `API_KEY` をコードへ直書きしないでください。
- `.env` や実運用用設定ファイルはコミットしないでください。
- 送信する添付ファイルに機密情報が含まれる場合は、公開リポジトリではなく社内限定運用を推奨します。

## ライセンス

このリポジトリには MIT License を同梱しています。必要に応じて自社ポリシーに合わせて変更してください。
