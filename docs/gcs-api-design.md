# Haskell から Google Cloud Storage API を呼び出す設計書

## 1. 背景と目的

### なぜ自前実装が必要か

Google Cloud Storage (GCS) を Haskell から利用するための公式 SDK は存在しない。
最も有力な候補である **gogol-storage** (Hackage) は JSON API v1 の自動生成バインディングだが、
以下の理由から採用を見送り、自前実装を選択する。

- ステータスが "experimental" のまま長期間メンテナンスされていない
- 2025年5月時点でビルド失敗の報告が複数あり、依存ライブラリとの互換性が不安定
- 内部実装が複雑で、障害発生時のデバッグが困難

Haskell のエコシステムには HTTP クライアント・JSON パース・JWT 署名の各領域に成熟したライブラリが揃っているため、
最小限のパッケージ構成で GCS JSON API を直接呼び出す実装が現実的かつ保守しやすい。

---

## 2. API オプション比較表

| 項目 | JSON API (REST) | XML API (S3互換) | gRPC API |
|------|----------------|-----------------|---------|
| 認証方式 | OAuth 2.0 Bearer Token | HMAC-SHA256 署名 | OAuth 2.0 Bearer Token |
| Haskell バインディング | wreq / req / http-client | amazonka (非互換問題あり) | 存在しない |
| 実装コスト | 低〜中 | 中（署名ロジック要自前実装） | 高（proto生成 + gRPCライブラリ統合） |
| JSON/XML パース | aeson（扱いやすい） | xml-conduit 等 | protobuf（自動生成） |
| 仕様の安定性 | 高（v1 は安定） | 中（S3との差異あり） | 高 |
| GCS 固有機能 | 完全対応 | 一部非対応（ACL・CORS 差異） | 完全対応（将来） |
| パフォーマンス | HTTP/1.1 | HTTP/1.1 | HTTP/2、ストリーミング対応 |
| 現状の採用可否 | **推奨** | 非推奨 | 将来の選択肢 |

### XML API を採用しない理由

- GCS の XML API は「S3互換」を謳うが、ACL・CORS・オブジェクトのバージョニング等で仕様差異が存在する
- Haskell の AWS SDK である **amazonka** はデフォルトで GCS との integrity check に非互換問題がある
- HMAC-SHA256 署名ロジックを自前実装する必要があり、OAuth2 より複雑

### gRPC API を採用しない理由

- GCS 用の Haskell gRPC バインディングが存在しない
- Protocol Buffers 定義からのコード生成と gRPC ライブラリ統合に実装コストが高い
- ただし **grapesy**（純 Haskell gRPC 実装）は成熟しつつあり、将来的な選択肢となりうる

---

## 3. 推奨方針: JSON API (REST) + 自前実装

### 選択根拠

1. **エコシステムの豊富さ**: wreq・req・http-client など HTTP クライアントライブラリの実装例が多い
2. **JSON の扱いやすさ**: aeson による型安全なパース・エンコードが可能
3. **OAuth2 実装の知見**: サービスアカウント JWT 認証の実装例が多数存在する
4. **仕様の安定性**: JSON API v1 は長期間安定して提供されている
5. **デバッグの容易さ**: curl 等で手動検証できるシンプルな REST インターフェース

### 全体フロー

```
[Service Account JSON]
    ↓ private_key を抽出
[JWT 生成 (jose: RS256署名)]
    ↓ assertion として POST
[OAuth2 Access Token 取得]
    (https://oauth2.googleapis.com/token)
    ↓ Bearer Token として付与
[wreq / http-client で GCS API リクエスト]
    ↓
[aeson でレスポンス JSON をパース]
    ↓
[GCS 操作完了]
```

---

## 4. 認証設計

### サービスアカウント鍵の取り扱い

GCS の認証には Google Cloud のサービスアカウント JSON キーファイルを使用する。

**抽出するフィールド:**

```json
{
  "client_email": "sa@project.iam.gserviceaccount.com",
  "private_key": "-----BEGIN PRIVATE KEY-----\n..."
}
```

- `client_email`: JWT の `iss`（issuer）クレームに使用
- `private_key`: RS256 署名に使用する PEM 形式の RSA 秘密鍵

**セキュリティ上の注意事項:**

- キーファイルはリポジトリにコミットしない（`.gitignore` に追加）
- 本番環境では環境変数または Secret Manager 経由で渡す
- 最小権限の原則に従い、用途に合った `scope` を選択する

### JWT クレームセット

| フィールド | 値 | 説明 |
|-----------|-----|------|
| `iss` | `client_email` の値 | トークン発行者（サービスアカウント） |
| `scope` | 後述の scope URI | 要求する権限スコープ |
| `aud` | `https://oauth2.googleapis.com/token` | トークンエンドポイント |
| `iat` | 現在の UNIX タイムスタンプ | トークン発行時刻 |
| `exp` | `iat + 3600` | トークン有効期限（最大1時間） |

**JWT ヘッダー:**

```json
{"alg": "RS256", "typ": "JWT"}
```

### スコープの選択

| スコープ | 用途 |
|---------|------|
| `https://www.googleapis.com/auth/devstorage.read_only` | オブジェクトの読み取りのみ |
| `https://www.googleapis.com/auth/devstorage.read_write` | オブジェクトの読み書き（IAM・メタデータ変更は不可） |
| `https://www.googleapis.com/auth/devstorage.full_control` | ACL を含む完全制御 |

最小権限の観点から、用途に応じて `read_only` または `read_write` を選択する。

### アクセストークン取得リクエスト

JWT を生成した後、以下のリクエストでアクセストークンを取得する。

```
POST https://oauth2.googleapis.com/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=<署名済みJWT>
```

**レスポンス:**

```json
{
  "access_token": "ya29.xxx",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### トークンのライフサイクル

- アクセストークンは **1時間有効**
- リフレッシュトークンは発行されない（サービスアカウント認証の仕様）
- 期限切れ後は新たに JWT を生成してトークンを再取得する
- 実装では `expires_in` を元にキャッシュ管理を行い、期限前に再取得する設計が望ましい

### jose ライブラリを使った JWT 生成の概要

```haskell
import Crypto.JWT
import Data.Aeson ((.=))

-- 1. JWK として PEM 秘密鍵をロード
-- 2. ClaimsSet を組み立て (iss, scope, aud, iat, exp)
buildClaims :: Text -> IO ClaimsSet
buildClaims email = do
  now <- getCurrentTime
  pure $ emptyClaimsSet
    & claimIss ?~ fromString (T.unpack email)
    & claimAud ?~ Audience [fromString "https://oauth2.googleapis.com/token"]
    & claimExp ?~ NumericDate (addUTCTime 3600 now)
    & claimIat ?~ NumericDate now
    & addClaim "scope" "https://www.googleapis.com/auth/devstorage.read_write"

-- 3. RS256 で署名
signJWT :: JWK -> ClaimsSet -> IO SignedJWT
signJWT jwk claims = runJOSE $ do
  alg <- bestJWSAlg jwk   -- RSA キーなら RS256 が選ばれる
  signClaims jwk (newJWSHeader ((), alg)) claims

-- 4. POST してアクセストークンを取得 (http-client + aeson)
-- 5. Authorization: Bearer <access_token> を GCS API リクエストに付与
```

---

## 5. 主要オペレーション一覧

ベースURI:
- API: `https://storage.googleapis.com/storage/v1`
- アップロード: `https://storage.googleapis.com/upload/storage/v1`
- ダウンロード: `https://storage.googleapis.com/download/storage/v1`

### オブジェクト操作

| オペレーション | HTTPメソッド | エンドポイント | 主なパラメータ |
|--------------|------------|--------------|--------------|
| オブジェクト一覧 | `GET` | `/b/{bucket}/o` | `prefix`, `delimiter`, `pageToken`, `maxResults` |
| メタデータ取得 | `GET` | `/b/{bucket}/o/{object}` | `fields`（部分取得） |
| オブジェクトダウンロード | `GET` | `/b/{bucket}/o/{object}?alt=media` | — |
| オブジェクトアップロード（シンプル） | `POST` | `/upload/storage/v1/b/{bucket}/o?uploadType=media` | `name`（クエリパラメータ） |
| オブジェクトアップロード（マルチパート） | `POST` | `/upload/storage/v1/b/{bucket}/o?uploadType=multipart` | メタデータ + ボディを multipart/related で送信 |
| オブジェクト削除 | `DELETE` | `/b/{bucket}/o/{object}` | `generation`（バージョン指定） |
| オブジェクトコピー | `POST` | `/b/{bucket}/o/{srcObject}/copyTo/b/{destBucket}/o/{destObject}` | — |

### 注意事項

- `{object}` にスラッシュを含む場合は URL エンコード (`/` → `%2F`) が必要
- アップロードタイプの選択:
  - **media**: 5MB 以下の小さいオブジェクト（メタデータなし）
  - **multipart**: メタデータと一緒にアップロードする場合
  - **resumable**: 5MB を超える大きなオブジェクト（推奨）
- レスポンスの `Object` リソースには `name`, `bucket`, `size`, `contentType`, `updated`, `md5Hash` 等が含まれる

---

## 6. 使用パッケージ

| パッケージ | 役割 | 備考 |
|-----------|------|------|
| `http-client` | HTTP リクエストの低レベル実装 | 接続管理・タイムアウト設定 |
| `http-client-tls` | TLS/HTTPS サポート | `newTlsManager` で TLS 対応マネージャーを作成 |
| `aeson` | JSON パース・エンコード | `FromJSON` / `ToJSON` インスタンスで型安全に扱う |
| `jose` | JWT 生成・RS256 署名 | `Crypto.JWT` モジュール。PEM 鍵の読み込みも対応 |
| `text` | `Text` 型の文字列処理 | JSON 文字列フィールドの扱い |
| `bytestring` | バイト列処理 | HTTP ボディ・PEM データの処理 |

### wreq vs http-client の選択

| | wreq | http-client |
|--|------|------------|
| 抽象度 | 高（使いやすい） | 低（細かい制御が可能） |
| lens 依存 | あり | なし |
| セッション管理 | 組み込み | 手動（Manager） |
| 推奨用途 | シンプルな用途 | 本番実装・細かい制御が必要な場合 |

本設計では `http-client` + `http-client-tls` をベースとする。
簡易スクリプト・プロトタイプ用途には `wreq` も選択肢となる。

---

## 7. 参考リンク

### 公式ドキュメント

| リソース | URL |
|---------|-----|
| GCS JSON API 概要 | https://cloud.google.com/storage/docs/json_api |
| GCS JSON API v1 リファレンス | https://cloud.google.com/storage/docs/json_api/v1 |
| Objects リソース | https://cloud.google.com/storage/docs/json_api/v1/objects |
| Objects: list | https://cloud.google.com/storage/docs/json_api/v1/objects/list |
| Objects: get | https://cloud.google.com/storage/docs/json_api/v1/objects/get |
| Objects: insert（アップロード） | https://cloud.google.com/storage/docs/json_api/v1/objects/insert |
| GCS API 一覧（Discovery Document） | https://cloud.google.com/storage/docs/apis |
| サービスアカウント認証 | https://cloud.google.com/iam/docs/service-account-creds |
| OAuth2 サーバー間認証 | https://developers.google.com/identity/protocols/oauth2/service-account |

### Hackage（Haskellパッケージ）

| パッケージ | URL |
|-----------|-----|
| jose | https://hackage.haskell.org/package/jose |
| http-client | https://hackage.haskell.org/package/http-client |
| http-client-tls | https://hackage.haskell.org/package/http-client-tls |
| aeson | https://hackage.haskell.org/package/aeson |
| wreq | https://hackage.haskell.org/package/wreq |
