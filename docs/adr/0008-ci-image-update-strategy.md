# ADR-0008: CI によるイメージ更新戦略 (Terraform 外のデプロイ)

## 状態
確定

## 決定
コンテナイメージの更新デプロイは `terraform apply` を経由せず、CI (GitHub Actions) が `gcloud run jobs update --image` で直接実施する。Terraform はジョブ自体の初回 provision と構成 (SA, リソース制限等) を管理し、イメージ更新は管理しない。

## 根拠

### Cloud Run Jobs の `:latest` 挙動
Cloud Run Jobs はコンテナ参照が同じ `:latest` タグのままであっても、Artifact Registry にイメージが push されただけでは新イメージを自動的に再取得しない。明示的な更新操作が必要。

### 採用しなかった代替案

| 案 | 概要 | 却下理由 |
|---|---|---|
| **A: Terraform apply (CI 内)** | CI が SHA タグでビルドし、`terraform apply -var container_image=<sha>` を実行 | terraform plan/apply に 1〜2 分かかり CI が遅い。インフラと同期が取れるが、コード変更のたびに Terraform state を書き換えるのは重すぎる |
| **B: `:latest` push のみ (何もしない)** | push 後の再デプロイを行わない | 実際には古いイメージで動き続けるため目的を達成しない |

### 採用案: C — CI 内 `gcloud run jobs update`
```
Terraform   → ジョブ provision (初回のみ / 構成変更時)
GitHub Actions → イメージ build/push + gcloud run jobs update
```

- **シンプル**: Terraform state への書き込みなし
- **冪等**: `gcloud run jobs update` は何度実行しても安全
- **初回起動前の安全弁**: ジョブが未作成の場合 (`terraform apply` 前) は `gcloud run jobs describe` で検出してスキップし、CI が 404 エラーで失敗しない

### `:latest` タグについて
個人プロジェクトで実行回数も少なく、特定バージョンへのロールバック要件も現時点では存在しないため `:latest` で許容する。将来的に厳密なロールバックが必要になった場合は、コミット SHA タグ (`piyolog-importer:abc1234`) に切り替え `gcloud run jobs update --image sha-tagged-image` を利用することで対応できる。
