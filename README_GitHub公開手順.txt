GitHub 公開の最短手順

1. GitHub で空のリポジトリを作成
2. このフォルダ一式を配置
3. ターミナルで以下を実行

   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <GitHubのURL>
   git push -u origin main

4. API_KEY は絶対にコミットしない
5. 公開前に .env や secrets が含まれていないか確認
